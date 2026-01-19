import os
import json
import time
import uuid
import queue
import base64
import asyncio
import traceback
import websockets
from asyncio import Task

from config.logger import setup_logging
from core.providers.tts.base import TTSProviderBase
from core.providers.tts.dto.dto import SentenceType, ContentType, InterfaceType
from core.utils import opus_encoder_utils
from core.utils.tts import MarkdownCleaner
from core.utils.util import check_model_key

TAG = __name__
logger = setup_logging()


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)

        # 双向流式接口类型
        self.interface_type = InterfaceType.DUAL_STREAM

        # API 配置
        self.ws_url = config.get("ws_url") or config.get("api_url")  # 兼容两种字段名
        self.api_key = config.get("api_key")
        self.sample_rate = int(config.get("sample_rate", 24000))
        self.audio_coding = config.get("audio_coding") or config.get("encoding", "raw")  # 兼容 encoding 字段

        # 音色和语音参数
        self.voice = config.get("voice", "")  # 音色ID
        self.speed = config.get("speed", 1.0)  # 语速，1.0为正常
        self.volume = config.get("volume", 1.0)  # 音量，1.0为正常
        self.pitch = config.get("pitch", 1.0)  # 音调，1.0为正常

        # sessionParam 配置（可覆盖上面的参数）
        self.session_param = config.get("session_param", {})

        # 调试模式
        self.debug = str(config.get("debug", "false")).lower() in ("1", "true", "yes", "on")

        self.output_file = config.get("output_dir", "tmp/")
        self.audio_file_type = "wav"

        # 文本缓冲（用于按句子分段）
        self.text_buffer = ""
        # 句子分隔符
        self.sentence_punctuations = ("。", "！", "？", "!", "?", "；", ";", "\n")
        # 首句分隔符（更短的分段，让首句更快播放）- 不包含冒号，避免时间被拆分
        self.first_sentence_punctuations = ("，", ",", "。", "！", "？", "!", "?", "；", ";", "~", "\n")
        self.is_first_sentence = True

        # 句子队列（用于异步合成）
        self.sentence_queue = None  # 延迟初始化
        self._synthesize_task = None
        self._last_sent = False  # 标记是否已发送 LAST

        # Opus 编码器
        self.opus_encoder = opus_encoder_utils.OpusEncoderUtils(
            sample_rate=self.sample_rate, channels=1, frame_size_ms=60
        )

        # 验证必需参数
        model_key_msg = check_model_key("TTS", self.api_key)
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)

        if not self.ws_url:
            logger.bind(tag=TAG).warning("CMHK XTTS ws_url 未配置")

    def _normalize_session_param(self, session_param: dict) -> dict:
        """sessionParam 是 map<string,string>，确保所有键值都是字符串"""
        if not isinstance(session_param, dict):
            return {}
        normalized = {}
        for k, v in session_param.items():
            key = "" if k is None else str(k)
            if v is None:
                val = ""
            elif isinstance(v, bool):
                val = "true" if v else "false"
            else:
                val = str(v)
            normalized[key] = val
        return normalized

    def _build_session_param(self, session_id: str = None) -> dict:
        """构建 sessionParam"""
        sp = dict(self.session_param) if isinstance(self.session_param, dict) else {}
        if session_id:
            sp["sid"] = session_id
        elif "sid" not in sp:
            sp["sid"] = f"xiaozhi-{uuid.uuid4().hex}"
        if "sample_rate" not in sp:
            sp["sample_rate"] = str(self.sample_rate)
        if "audio_coding" not in sp:
            sp["audio_coding"] = str(self.audio_coding)
        return self._normalize_session_param(sp)

    def _extract_sentence(self) -> str:
        """从缓冲区提取一个完整的句子"""
        if not self.text_buffer:
            return None

        # 根据是否是第一句选择分隔符
        punctuations = self.first_sentence_punctuations if self.is_first_sentence else self.sentence_punctuations

        # 查找最早的分隔符位置
        earliest_pos = -1
        for punct in punctuations:
            pos = self.text_buffer.find(punct)
            if pos != -1:
                if earliest_pos == -1 or pos < earliest_pos:
                    earliest_pos = pos

        if earliest_pos != -1:
            # 提取句子（包含分隔符）
            sentence = self.text_buffer[:earliest_pos + 1]
            self.text_buffer = self.text_buffer[earliest_pos + 1:]
            if self.is_first_sentence:
                self.is_first_sentence = False
            return sentence.strip()

        return None

    async def _synthesize_one_sentence(self, sentence: str):
        """合成一个句子的音频（独立连接）- 边收边播流式"""
        if not sentence:
            return

        filtered_text = MarkdownCleaner.clean_markdown(sentence)
        if not filtered_text.strip():
            return

        start_time = time.time()
        logger.bind(tag=TAG).info(f"[耗时统计] 开始合成句子: {filtered_text[:30]}...")

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        ws = None
        first_audio_sent = False  # 标记是否已发送第一段音频
        first_audio_time = None  # 记录首个音频包到达时间
        
        try:
            ws = await asyncio.wait_for(
                websockets.connect(
                    self.ws_url,
                    additional_headers=headers,
                    ping_interval=None,
                    close_timeout=5,
                ),
                timeout=10  # 连接超时增加到 10 秒
            )
            logger.bind(tag=TAG).debug(f"[耗时统计] WebSocket连接建立: {time.time() - start_time:.3f}s")

            session_param = self._build_session_param()

            request = {
                "sessionParam": session_param,
                "text": filtered_text,
                "endFlag": True,
            }
            await ws.send(json.dumps(request))
            logger.bind(tag=TAG).debug(f"[耗时统计] 发送TTS请求: {time.time() - start_time:.3f}s")

            # 边收边播
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=30)  # 接收超时增加到 30 秒
                except asyncio.TimeoutError:
                    logger.bind(tag=TAG).warning("接收音频超时")
                    break

                data = json.loads(msg)

                result = data.get("result") if isinstance(data, dict) else data
                if not isinstance(result, dict):
                    result = data

                err_code = result.get("errCode")
                if err_code not in (None, 0, "0"):
                    err_str = result.get("errStr", "未知错误")
                    logger.bind(tag=TAG).error(f"TTS 合成错误: errCode={err_code}, errStr={err_str}")
                    break

                audio_data = result.get("data")
                end_flag = result.get("endFlag", False)

                if audio_data:
                    try:
                        if isinstance(audio_data, str):
                            audio_bytes = base64.b64decode(audio_data)
                        elif isinstance(audio_data, (list, tuple)):
                            audio_bytes = bytes(audio_data)
                        else:
                            audio_bytes = audio_data

                        # 第一段音频时发送 FIRST 通知
                        if not first_audio_sent:
                            first_audio_sent = True
                            first_audio_time = time.time() - start_time
                            logger.bind(tag=TAG).info(f"[耗时统计] TTS首个音频包返回: {first_audio_time:.3f}s")
                            self.tts_audio_queue.put((SentenceType.FIRST, [], filtered_text))

                        # 立即编码并推送（流式）
                        self.opus_encoder.encode_pcm_to_opus_stream(
                            audio_bytes, False, self.handle_opus
                        )
                    except Exception as e:
                        logger.bind(tag=TAG).error(f"处理音频数据失败: {e}")

                if end_flag:
                    logger.bind(tag=TAG).info(f"[耗时统计] 句子合成完成: {filtered_text[:30]}..., 总耗时: {time.time() - start_time:.3f}s")
                    break

        except asyncio.TimeoutError:
            logger.bind(tag=TAG).error(f"合成句子超时: {filtered_text[:20]}...")
        except Exception as e:
            logger.bind(tag=TAG).error(f"合成句子失败: {str(e)}")
        finally:
            if ws:
                try:
                    await ws.close()
                except:
                    pass

    async def _sentence_synthesize_loop(self):
        """句子合成循环 - 从队列中取句子并合成"""
        while True:
            try:
                if self.sentence_queue is None:
                    break
                    
                item = await self.sentence_queue.get()
                
                if item is None:  # 结束信号
                    break
                
                sentence, is_last = item
                
                # 检查是否被打断
                if self.conn and self.conn.client_abort:
                    logger.bind(tag=TAG).debug(f"句子被打断，跳过: {sentence[:20] if sentence else ''}...")
                    continue
                
                # 合成句子（空句子跳过合成但继续处理 is_last）
                if sentence:
                    await self._synthesize_one_sentence(sentence)
                
                # 再次检查打断状态，避免打断后还发送 LAST
                if self.conn and self.conn.client_abort:
                    continue
                
                # is_last 时调用 _process_before_stop_play_files，它内部会发送 LAST
                if is_last and not self._last_sent:
                    self._last_sent = True
                    self._process_before_stop_play_files()
                    
            except asyncio.CancelledError:
                logger.bind(tag=TAG).debug("句子合成循环被取消")
                break
            except Exception as e:
                logger.bind(tag=TAG).error(f"句子合成循环错误: {e}")

    def _stop_synthesize_task(self):
        """停止合成任务并清理队列"""
        # 取消正在执行的任务
        if self._synthesize_task:
            try:
                if hasattr(self._synthesize_task, 'cancel'):
                    self._synthesize_task.cancel()
            except:
                pass
            self._synthesize_task = None
        
        # 清空队列
        if self.sentence_queue:
            try:
                while True:
                    self.sentence_queue.get_nowait()
            except:
                pass
        self.sentence_queue = None

    async def close(self):
        """资源清理方法 - 连接关闭时调用"""
        self._stop_synthesize_task()
        logger.bind(tag=TAG).debug("TTS 资源已清理")

    def tts_text_priority_thread(self):
        """双向流式 TTS 文本处理线程 - 按句子分段合成"""
        while not self.conn.stop_event.is_set():
            try:
                message = self.tts_text_queue.get(timeout=1)
                logger.bind(tag=TAG).debug(
                    f"收到TTS任务｜{message.sentence_type.name} ｜ {message.content_type.name}"
                )

                if message.sentence_type == SentenceType.FIRST:
                    self.conn.client_abort = False
                    # 停止之前的合成任务
                    self._stop_synthesize_task()
                    # 重置状态
                    self.text_buffer = ""
                    self.is_first_sentence = True
                    self._last_sent = False
                    self.before_stop_play_files.clear()
                    
                    # 创建新的队列并启动合成循环
                    self.sentence_queue = asyncio.Queue()
                    self._synthesize_task = asyncio.run_coroutine_threadsafe(
                        self._sentence_synthesize_loop(),
                        loop=self.conn.loop,
                    )

                if self.conn.client_abort:
                    logger.bind(tag=TAG).info("收到打断信息，终止TTS文本处理")
                    self.text_buffer = ""
                    self._stop_synthesize_task()
                    continue

                # 处理文本内容
                if ContentType.TEXT == message.content_type:
                    if message.content_detail and self.sentence_queue:
                        # 添加到缓冲区
                        self.text_buffer += message.content_detail
                        logger.bind(tag=TAG).debug(f"收到文本片段: {message.content_detail[:20]}..., 当前缓冲区长度: {len(self.text_buffer)}")

                        # 尝试提取并合成完整的句子
                        while True:
                            sentence = self._extract_sentence()
                            if sentence and self.sentence_queue:
                                logger.bind(tag=TAG).info(f"[耗时统计] 提取到完整句子: {sentence[:30]}...")
                                # 放入句子队列
                                asyncio.run_coroutine_threadsafe(
                                    self.sentence_queue.put((sentence, False)),
                                    loop=self.conn.loop,
                                )
                            else:
                                break

                # 处理文件内容
                elif ContentType.FILE == message.content_type:
                    # 先处理缓冲区中剩余的文本
                    if self.text_buffer.strip() and self.sentence_queue:
                        asyncio.run_coroutine_threadsafe(
                            self.sentence_queue.put((self.text_buffer.strip(), False)),
                            loop=self.conn.loop,
                        )
                        self.text_buffer = ""

                    if message.content_file and os.path.exists(message.content_file):
                        self._process_audio_file_stream(
                            message.content_file,
                            callback=lambda audio_data: self.handle_audio_file(audio_data, message.content_detail)
                        )

                # 会话结束
                if message.sentence_type == SentenceType.LAST:
                    # 处理缓冲区中剩余的文本
                    remaining = self.text_buffer.strip()
                    self.text_buffer = ""
                    
                    if remaining and self.sentence_queue:
                        # 最后一个句子，标记为 is_last=True，由合成循环发送 LAST
                        asyncio.run_coroutine_threadsafe(
                            self.sentence_queue.put((remaining, True)),
                            loop=self.conn.loop,
                        )
                    elif self.sentence_queue:
                        # 没有剩余文本，但队列里可能还有句子在处理
                        # 发送一个空的 is_last=True 让合成循环发送 LAST
                        asyncio.run_coroutine_threadsafe(
                            self.sentence_queue.put(("", True)),
                            loop=self.conn.loop,
                        )
                    elif not self._last_sent:
                        # 队列都没了，直接发送结束信号
                        self._last_sent = True
                        self._process_before_stop_play_files()
                        self.tts_audio_queue.put((SentenceType.LAST, [], None))
                    
                    self.is_first_sentence = True

            except queue.Empty:
                continue
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"处理TTS文本失败: {str(e)}, 堆栈: {traceback.format_exc()}"
                )

    async def text_to_speak(self, text, output_file):
        """单次 TTS 合成（用于非流式场景）"""
        if not self.ws_url:
            raise ValueError("CMHK XTTS ws_url 未配置")

        filtered_text = MarkdownCleaner.clean_markdown(text)
        if not filtered_text.strip():
            return None

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        audio_chunks = []
        ws = None

        try:
            ws = await asyncio.wait_for(
                websockets.connect(
                    self.ws_url,
                    additional_headers=headers,
                    ping_interval=None,
                    close_timeout=2,
                ),
                timeout=5
            )

            session_param = self._build_session_param()

            request = {
                "sessionParam": session_param,
                "text": filtered_text,
                "endFlag": True,
            }
            await ws.send(json.dumps(request))

            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(msg)

                result = data.get("result") if isinstance(data, dict) else data
                if not isinstance(result, dict):
                    result = data

                err_code = result.get("errCode")
                if err_code not in (None, 0, "0"):
                    err_str = result.get("errStr", "未知错误")
                    raise Exception(f"TTS 合成失败: errCode={err_code}, errStr={err_str}")

                audio_data = result.get("data")
                end_flag = result.get("endFlag", False)

                if audio_data:
                    if isinstance(audio_data, str):
                        audio_bytes = base64.b64decode(audio_data)
                    elif isinstance(audio_data, (list, tuple)):
                        audio_bytes = bytes(audio_data)
                    else:
                        audio_bytes = audio_data
                    audio_chunks.append(audio_bytes)

                if end_flag:
                    break

        except Exception as e:
            logger.bind(tag=TAG).error(f"TTS 请求失败: {str(e)}")
            raise
        finally:
            if ws:
                try:
                    await ws.close()
                except:
                    pass

        if not audio_chunks:
            raise Exception("TTS 返回空音频数据")

        pcm_bytes = b"".join(audio_chunks)

        # 封装为 WAV
        if pcm_bytes[:4] == b"RIFF":
            wav_bytes = pcm_bytes
        else:
            import wave
            from io import BytesIO
            wav_buf = BytesIO()
            with wave.open(wav_buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(pcm_bytes)
            wav_bytes = wav_buf.getvalue()

        if output_file:
            with open(output_file, "wb") as f:
                f.write(wav_bytes)
            return None
        else:
            return wav_bytes

    def to_tts(self, text: str) -> list:
        """非流式 TTS 处理，返回 Opus 编码的音频数据列表"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            audio_data = []

            async def _generate():
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"

                ws = await asyncio.wait_for(
                    websockets.connect(
                        self.ws_url,
                        additional_headers=headers,
                        ping_interval=None,
                        close_timeout=2,
                    ),
                    timeout=5
                )

                try:
                    filtered_text = MarkdownCleaner.clean_markdown(text)
                    session_param = self._build_session_param()

                    request = {
                        "sessionParam": session_param,
                        "text": filtered_text,
                        "endFlag": True,
                    }
                    await ws.send(json.dumps(request))

                    while True:
                        msg = await asyncio.wait_for(ws.recv(), timeout=10)
                        data = json.loads(msg)

                        result = data.get("result") if isinstance(data, dict) else data
                        if not isinstance(result, dict):
                            result = data

                        err_code = result.get("errCode")
                        if err_code not in (None, 0, "0"):
                            err_str = result.get("errStr", "未知错误")
                            raise Exception(f"TTS 合成失败: errCode={err_code}, errStr={err_str}")

                        audio_part = result.get("data")
                        end_flag = result.get("endFlag", False)

                        if audio_part:
                            if isinstance(audio_part, str):
                                audio_bytes = base64.b64decode(audio_part)
                            elif isinstance(audio_part, (list, tuple)):
                                audio_bytes = bytes(audio_part)
                            else:
                                audio_bytes = audio_part

                            self.opus_encoder.encode_pcm_to_opus_stream(
                                audio_bytes,
                                end_of_stream=False,
                                callback=lambda opus: audio_data.append(opus)
                            )

                        if end_flag:
                            break
                finally:
                    try:
                        await ws.close()
                    except:
                        pass

            loop.run_until_complete(_generate())
            loop.close()

            return audio_data

        except Exception as e:
            logger.bind(tag=TAG).error(f"生成音频数据失败: {str(e)}")
            return []
