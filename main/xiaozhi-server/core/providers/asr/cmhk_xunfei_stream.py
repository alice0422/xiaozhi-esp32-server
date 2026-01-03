import asyncio
import base64
import json
from datetime import datetime
from time import mktime
import threading
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

import opuslib_next
import websockets
from config.logger import setup_logging
from core.providers.asr.base import ASRProviderBase
from core.providers.asr.dto.dto import InterfaceType
from wsgiref.handlers import format_date_time

TAG = __name__
logger = setup_logging()

# 帧状态常量
STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识


def _safe_json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def _join_paths(base_path: str, api_path: str) -> str:
    base_path = base_path or ""
    api_path = api_path or ""

    if not base_path:
        return api_path

    if not api_path:
        return base_path

    if base_path.endswith("/") and api_path.startswith("/"):
        return base_path + api_path[1:]
    if (not base_path.endswith("/")) and (not api_path.startswith("/")):
        return base_path + "/" + api_path
    return base_path + api_path


def _deep_find_first_text(payload: Any) -> Optional[str]:
    """尽量从任意结构里找到第一个像文本的字段。

    优先匹配常见key: text/content/result/answer。
    """

    if payload is None:
        return None

    # 注意：CMHK讯飞AST返回里会出现很多“非文本字段”，比如：
    # - metadata.msgtype: "sentence"/"progressive"
    # - sc: "0.00"（置信度）以及一堆时间戳字段
    # 这些都不是识别文本，不能当结果返回。
    priority_keys = {"text", "content", "answer", "asr", "transcript"}

    def _is_bad_marker(s: str) -> bool:
        s = s.strip()
        if not s:
            return True
        if s in {"success", "sentence", "progressive", "ok", "true", "false"}:
            return True
        # 过滤纯数字/小数（常见是 sc: 0.00 被误选为文本）
        if re.fullmatch(r"[0-9.]+", s):
            return True
        # 过滤类似 IP 的数字点串（例如 0.0.0 或 0.0.0.0）
        if re.fullmatch(r"(?:\d{1,3}\.){2,3}\d{1,3}", s):
            return True
        return False

    # BFS
    queue: List[Any] = [payload]
    visited = 0
    while queue and visited < 5000:
        cur = queue.pop(0)
        visited += 1

        if isinstance(cur, str):
            s = cur.strip()
            if s and not _is_bad_marker(s):
                return s
            continue

        if isinstance(cur, dict):
            # 先看优先key
            for k in list(cur.keys()):
                if k in priority_keys and isinstance(cur.get(k), str) and cur.get(k).strip():
                    val = cur.get(k).strip()
                    if not _is_bad_marker(val):
                        return val
            # 再遍历所有
            ignored_string_keys = {
                "msgtype",
                "metadata",
                "sc",
                "sf",
                "wb",
                "wc",
                "we",
                "wp",
                "bg",
                "ed",
                "sn",
                "segId",
                "sid",
            }
            for k, v in cur.items():
                if isinstance(v, str) and k in ignored_string_keys:
                    continue
                queue.append(v)
            continue

        if isinstance(cur, list):
            queue.extend(cur)
            continue

    return None


class ASRProvider(ASRProviderBase):
    """CMHK 网关下的讯飞 AST(ws_iflytek_ast) 流式 ASR。

    - 网关鉴权：x-gateway-apikey: Bearer <api_key>
    - URL：<gateway_url路径> + <api_path>（文档接口列表中 ws_iflytek_ast 为 /tuling/ast/v3）
    - 额外必填字段：header.bizId

    注意：返回包结构可能与标准讯飞 IAT 不一致，因此解析做了容错与原始包日志输出。
    """

    def __init__(self, config: dict, delete_audio_file: bool):
        super().__init__()
        self.interface_type = InterfaceType.STREAM
        self.config = config

        self.text = ""
        self.best_text = ""
        self.has_final_result = False

        self.decoder = opuslib_next.Decoder(16000, 1)

        self.asr_ws = None
        self.forward_task = None
        self.is_processing = False
        self.server_ready = False
        self.last_frame_sent = False
        self._start_frame_sent = False
        # 用于等待“最终识别结果”（跨线程安全：父类handle_voice_stop会在线程里调用speech_to_text）
        self._final_event = threading.Event()

        # iFlytek IAT wpgs（动态修正）合并缓存：sn -> 文本片段
        self._wpgs_parts: Dict[int, str] = {}

        # ===== CMHK 网关配置 =====
        self.gateway_url = config.get(
            "gateway_url",
            "https://opensseapi.cmhk.com/CMHK-LMMP-PRD_ws_iflytek_ast/CMHK-LMMP-PRD",
        )
        # 文档接口列表：ws_iflytek_ast -> /tuling/ast/v3
        self.api_path = config.get("api_path", "/tuling/ast/v3")

        self.api_key = config.get("api_key")
        if not self.api_key:
            raise ValueError("必须提供api_key")

        # 文档：请求头 x-gateway-apikey，Api key前面要加Bearer
        self.api_key_header_format = config.get("api_key_header_format", "x-gateway-apikey")

        # bizId 必填（网关返回 schema validation 要求 header.bizId）
        self.biz_id = config.get("biz_id") or (self.api_key[:8] if self.api_key else "default")

        # 可选：有些后端也会校验 app_id
        self.app_id = config.get("app_id", "")

        # 是否使用自定义路径（调试用）
        self.use_custom_path = bool(config.get("use_custom_path", False))
        self.custom_path = config.get("custom_path", "")
        self.path_suffix = config.get("path_suffix", "")

        # ===== 讯飞参数（沿用项目内 xunfei_stream 结构） =====
        self.iat_params = {
            "domain": config.get("domain", "slm"),
            "language": config.get("language", "zh_cn"),
            "accent": config.get("accent", "mandarin"),
            "dwa": config.get("dwa", "wpgs"),
            "result": {"encoding": "utf8", "compress": "raw", "format": "plain"},
        }

        self.output_dir = config.get("output_dir", "tmp/")
        self.delete_audio_file = delete_audio_file

    def create_url(self) -> str:
        parsed = urlparse(self.gateway_url)

        # scheme
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        host = parsed.netloc

        # base path
        base_path = parsed.path

        # 清理 query 里可能混入的 apikey
        query = ""
        if parsed.query:
            params = parse_qs(parsed.query)
            for k in list(params.keys()):
                kl = k.lower()
                if "api" in kl or "key" in kl or "auth" in kl:
                    params.pop(k, None)
            if params:
                query = urlencode(params, doseq=True)

        # path 选择
        if self.use_custom_path and self.custom_path:
            path = self.custom_path
            logger.bind(tag=TAG).info(f"使用自定义路径: {path}")
        else:
            path = _join_paths(base_path, self.api_path)
            logger.bind(tag=TAG).info(
                f"组合路径: 基础路径={base_path}, API路径={self.api_path}, 最终路径={path}"
            )

        if self.path_suffix:
            path = _join_paths(path, self.path_suffix)

        url = f"{ws_scheme}://{host}{path}"
        if query:
            url = url + "?" + query

        logger.bind(tag=TAG).info(f"生成的WebSocket URL: {url}")
        return url

    def _get_headers(self) -> Optional[Dict[str, str]]:
        fmt = (self.api_key_header_format or "").lower()

        # 文档标准
        if fmt in {"x-gateway-apikey", "gateway"}:
            return {"x-gateway-apikey": f"Bearer {self.api_key}"}

        # 兼容其它（调试）
        if fmt == "authorization":
            return {"Authorization": f"Bearer {self.api_key}"}
        if fmt == "authentication":
            return {"Authentication": f"Bearer {self.api_key}"}
        if fmt == "x-api-key":
            return {"X-API-Key": self.api_key}

        # 默认回退到文档标准
        return {"x-gateway-apikey": f"Bearer {self.api_key}"}

    async def open_audio_channels(self, conn):
        await super().open_audio_channels(conn)

    async def receive_audio(self, conn, audio, audio_have_voice):
        await super().receive_audio(conn, audio, audio_have_voice)

        # 存储音频数据用于声纹识别
        if not hasattr(conn, "asr_audio_for_voiceprint"):
            conn.asr_audio_for_voiceprint = []
        conn.asr_audio_for_voiceprint.append(audio)

        if audio_have_voice and self.asr_ws is None and not self.is_processing:
            try:
                await self._start_recognition(conn)
                # 注意：_start_recognition 会发送首帧并 flush 一段缓存音频。
                # 这里直接返回，避免同一包音频既作为首帧又作为 continue 帧重复发送。
                return
            except Exception as e:
                logger.bind(tag=TAG).error(f"建立ASR连接失败: {e}")
                await self._cleanup(conn)
                return

        if self.asr_ws and self.is_processing and audio:
            # 连接建立后，如果之前没有成功发送首帧，则使用当前音频作为首帧并立即进入实时流式发送
            if not self._start_frame_sent:
                try:
                    pcm_frame = self.decoder.decode(audio, 960)
                    await self._send_audio_frame(pcm_frame, STATUS_FIRST_FRAME)
                    self._start_frame_sent = True
                    self.server_ready = True
                    logger.bind(tag=TAG).info("已补发首帧，开始实时识别")
                    await asyncio.sleep(0.05)
                except Exception as e:
                    logger.bind(tag=TAG).warning(f"补发首帧失败: {e}")
                    await self._cleanup(conn)
                return

            # 首帧后立即发送后续音频，保证实时性
            if self.server_ready:
                try:
                    pcm_frame = self.decoder.decode(audio, 960)
                    await self._send_audio_frame(pcm_frame, STATUS_CONTINUE_FRAME)
                except Exception as e:
                    logger.bind(tag=TAG).warning(f"发送音频数据时发生错误: {e}")
                    await self._cleanup(conn)

    async def _start_recognition(self, conn):
        self.is_processing = True
        self._final_event.clear()
        self._start_frame_sent = False
        self._wpgs_parts.clear()

        ws_url = self.create_url()
        headers = self._get_headers()

        if headers:
            # 只打出部分内容，避免泄露
            safe_headers = {}
            for k, v in headers.items():
                if isinstance(v, str) and len(v) > 18:
                    safe_headers[k] = f"{v[:10]}...{v[-5:]}"
                else:
                    safe_headers[k] = v
            logger.bind(tag=TAG).info(f"使用headers: {safe_headers}")

        self.asr_ws = await websockets.connect(
            ws_url,
            additional_headers=headers,
            max_size=1000000000,
            ping_interval=None,
            ping_timeout=None,
            close_timeout=10,
        )

        logger.bind(tag=TAG).info("ASR WebSocket连接已建立")

        self.server_ready = False
        self.last_frame_sent = False
        self.best_text = ""
        self.has_final_result = False

        self.forward_task = asyncio.create_task(self._forward_results(conn))

        # 发送首帧：必须确保音频非空，否则网关会报 schema 校验失败并导致后续 10004 未启动
        # 重要：按时间顺序发送。首帧必须是“最早的一段音频”，后续再按顺序发送缓存，避免乱序导致识别反复/偏差。
        buffered: List[bytes] = []
        if getattr(conn, "asr_audio", None):
            for pkt in conn.asr_audio[-10:]:
                if pkt:
                    buffered.append(pkt)

        if buffered:
            first_audio = buffered[0]
            pcm_frame = self.decoder.decode(first_audio, 960)
            await self._send_audio_frame(pcm_frame, STATUS_FIRST_FRAME)
            self._start_frame_sent = True
            self.server_ready = True
            logger.bind(tag=TAG).info("已发送首帧，开始实时识别")

            # 发送缓存（跳过空包，保持顺序）
            await asyncio.sleep(0.05)
            for cached_audio in buffered[1:]:
                try:
                    pcm_frame = self.decoder.decode(cached_audio, 960)
                    await self._send_audio_frame(pcm_frame, STATUS_CONTINUE_FRAME)
                except Exception as e:
                    logger.bind(tag=TAG).warning(f"发送缓存音频失败: {e}")
                    break
        else:
            # 没有有效音频就先不启动，等 receive_audio 进来再发首帧
            logger.bind(tag=TAG).warning("未找到有效首帧音频，等待后续音频包再启动")
            self.server_ready = False

    async def _send_audio_frame(self, audio_data: bytes, status: int):
        if not self.asr_ws:
            return

        # CMHK 网关 schema 要求 payload.audio.audio 至少 1 个字符（空音频会被拒绝）
        # 因此如果出现空音频，使用 1 字节静音占位（AA==），避免首帧/末帧被拒导致 10004 未启动。
        if not audio_data:
            audio_data = b"\x00\x00"

        audio_b64 = base64.b64encode(audio_data).decode("utf-8")

        # app_id 为空时用 api_key 前8位占位
        app_id_value = self.app_id or self.api_key[:8]

        frame_data = {
            "header": {
                "status": status,
                "app_id": app_id_value,
                "bizId": self.biz_id,
            },
            "parameter": {"iat": self.iat_params},
            "payload": {
                "audio": {"audio": audio_b64, "sample_rate": 16000, "encoding": "raw"}
            },
        }

        await self.asr_ws.send(json.dumps(frame_data, ensure_ascii=False))

        if status == STATUS_LAST_FRAME:
            self.last_frame_sent = True
            logger.bind(tag=TAG).info("标记最终帧已发送")

    def _extract_text(self, result: Dict[str, Any]) -> Tuple[str, int, int]:
        """返回 (text, code, status)"""
        header = result.get("header") or {}
        payload = result.get("payload")

        code = 0
        status = 0
        try:
            code = int(header.get("code", 0))
        except Exception:
            code = 0
        try:
            status = int(header.get("status", 0))
        except Exception:
            status = 0

        # 讯飞AST（CMHK网关）常见：payload.result.ws[].cw[].w 直接给词
        if isinstance(payload, dict):
            res = payload.get("result")
            if isinstance(res, dict):
                # 尽量用 ls 判断是否最后一句（有些场景header.status未必是2）
                try:
                    if res.get("ls") is True:
                        status = 2
                except Exception:
                    pass

                ws_list = res.get("ws")
                if isinstance(ws_list, list):
                    out: List[str] = []
                    for seg in ws_list:
                        if not isinstance(seg, dict):
                            continue
                        cw_list = seg.get("cw")
                        if not isinstance(cw_list, list):
                            continue
                        for cw in cw_list:
                            if isinstance(cw, dict):
                                w = cw.get("w")
                                if isinstance(w, str) and w:
                                    out.append(w)
                    joined = "".join(out).strip()
                    if joined:
                        return joined, code, status
                    # 明确存在 ws 结构但没有任何 w 文本：不要 fallback 去捡 sc=0.00 等字段
                    return "", code, status

        # 其次走标准讯飞：payload.result.text base64
        if isinstance(payload, dict):
            res = payload.get("result")
            if isinstance(res, dict) and "text" in res:
                text_data = res.get("text")
                if isinstance(text_data, str) and text_data:
                    # 有些服务返回不是base64，这里兜底
                    try:
                        decoded = base64.b64decode(text_data).decode("utf-8")
                        text_json = json.loads(decoded)
                        ws = text_json.get("ws", [])
                        out = []
                        for i in ws:
                            for j in i.get("cw", []):
                                out.append(j.get("w", ""))
                        return "".join(out).strip(), code, status
                    except Exception:
                        return text_data.strip(), code, status

        # 其它结构兜底（避免返回 sentence/progressive 等标记）
        text = _deep_find_first_text(payload)
        return (text or ""), code, status

    @staticmethod
    def _try_get_result_obj(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        payload = result.get("payload")
        if not isinstance(payload, dict):
            return None
        res = payload.get("result")
        if isinstance(res, dict):
            return res
        return None

    def _apply_wpgs_merge(self, res: Dict[str, Any], text: str) -> str:
        """按讯飞 IAT 的 wpgs 协议合并文本。

        - pgs=apd: 追加
        - pgs=rpl: 替换 rg 范围内的 sn 片段
        """
        if not isinstance(res, dict):
            return text

        pgs = res.get("pgs")
        rg = res.get("rg")
        sn_raw = res.get("sn")
        msgtype = res.get("msgtype")
        ls_flag = res.get("ls")

        try:
            sn = int(sn_raw)
        except Exception:
            sn = None

        # 最终句（ls=true 或 msgtype=sentence）在部分网关下会返回“完整句子”而不是增量分片。
        # 为避免把 progressive 片段拼进来导致“两句叠加”，这里直接把最终句视为全文替换。
        try:
            if (ls_flag is True) or (isinstance(msgtype, str) and msgtype.lower() == "sentence"):
                if isinstance(text, str) and text.strip() and sn is not None:
                    final_text = text.strip()
                    self._wpgs_parts = {sn: final_text}
                    return final_text
        except Exception:
            pass

        # rpl：根据 rg 删除旧片段
        if pgs == "rpl" and isinstance(rg, str):
            m = re.fullmatch(r"\s*(\d+)\s*-\s*(\d+)\s*", rg)
            if m:
                start_sn = int(m.group(1))
                end_sn = int(m.group(2))
                for k in range(start_sn, end_sn + 1):
                    self._wpgs_parts.pop(k, None)

        # 写入当前片段
        if sn is not None and isinstance(text, str) and text:
            self._wpgs_parts[sn] = text

        # 合并输出
        if not self._wpgs_parts:
            return text

        # 有些网关返回的 sn 对应的是“累计全文”，而不是“增量分片”。
        # 若最新 sn 的文本已包含此前合并结果，则直接以最新文本为准并重置缓存，避免重复叠句。
        keys = sorted(self._wpgs_parts.keys())
        if len(keys) >= 2:
            last_k = keys[-1]
            last_text = (self._wpgs_parts.get(last_k) or "").strip()
            prev_text = "".join((self._wpgs_parts.get(k) or "") for k in keys[:-1]).strip()
            if last_text and prev_text and (last_text.startswith(prev_text) or prev_text in last_text):
                self._wpgs_parts = {last_k: last_text}
                return last_text

            # 数字/大小写/标点等格式化会导致不满足 startswith/in，但仍然是同一句“全文替换”。
            # 用公共前缀长度做一个宽松判断：公共前缀足够长则认为是同一句。
            if last_text and prev_text:
                common = 0
                for a, b in zip(last_text, prev_text):
                    if a != b:
                        break
                    common += 1
                if common >= 8 or (len(prev_text) > 0 and common >= int(len(prev_text) * 0.4)):
                    # 认为 last_text 是对 prev_text 的“修正/格式化后的全文”，用 last 覆盖
                    self._wpgs_parts = {last_k: last_text}
                    return last_text

        # 增量分片模式：按 sn 顺序拼接，但要做“重叠去重”，避免网关返回部分累计导致叠句。
        merged = ""
        for k in keys:
            part = (self._wpgs_parts.get(k) or "").strip()
            if not part:
                continue
            if not merged:
                merged = part
                continue

            # 如果当前 part 本身就是更完整的累计文本，则直接替换 merged
            if part.startswith(merged) or (merged in part):
                merged = part
                continue
            # 如果 part 是 merged 的子串，则忽略这个 part
            if part in merged:
                continue

            # 计算 merged 的后缀与 part 的前缀最大重叠
            max_overlap = min(len(merged), len(part))
            overlap = 0
            for i in range(max_overlap, 0, -1):
                if merged[-i:] == part[:i]:
                    overlap = i
                    break
            merged = (merged + part[overlap:]).strip()

        return merged

    @staticmethod
    def _is_punct_only(text: str) -> bool:
        if not text:
            return False
        s = text.strip()
        if not s:
            return True
        punct_chars = set(
            "，,。.!！？?;；:：…~、\"'“”‘’（）()[]【】<>《》-—"
        )
        return all((ch in punct_chars) for ch in s)

    @staticmethod
    def _merge_trailing_punct(base: str, punct: str) -> str:
        if not punct:
            return (base or "").strip()
        if not base:
            return punct.strip()

        base_s = base.rstrip()
        punct_s = punct.strip()
        if not base_s:
            return punct_s

        punct_chars = set(
            "，,。.!！？?;；:：…~、\"'“”‘’（）()[]【】<>《》-—"
        )

        if punct_s and base_s[-1] in punct_chars:
            return base_s[:-1] + punct_s
        return base_s + punct_s

    async def _forward_results(self, conn):
        try:
            while self.asr_ws and not conn.stop_event.is_set():
                try:
                    timeout = 3.0 if self.last_frame_sent else 30.0
                    raw = await asyncio.wait_for(self.asr_ws.recv(), timeout=timeout)
                    result = json.loads(raw)

                    # 关键：把原始包打出来（便于你对照文档/讯飞协议）
                    logger.bind(tag=TAG).info(f"收到ASR结果: {_safe_json_dumps(result)}")

                    text, code, status = self._extract_text(result)
                    res_obj = self._try_get_result_obj(result)

                    # wpgs 动态修正：把 text 合并成更稳定的完整句
                    effective_text = text
                    if isinstance(res_obj, dict):
                        pgs = res_obj.get("pgs")
                        rg = res_obj.get("rg")
                        sn_raw = res_obj.get("sn")
                        # CMHK 网关的最终包可能只有 sn/ls 而没有 pgs/rg，仍然需要合并。
                        should_merge = False
                        if pgs in {"apd", "rpl"}:
                            should_merge = True
                        if rg:
                            should_merge = True
                        try:
                            if sn_raw is not None:
                                int(sn_raw)
                                should_merge = True
                        except Exception:
                            pass

                        if should_merge:
                            effective_text = self._apply_wpgs_merge(res_obj, text)

                    if code != 0:
                        header = result.get("header") or {}
                        logger.bind(tag=TAG).error(
                            f"识别错误，错误码: {code}, 消息: {header.get('message', header.get('msg', ''))}"
                        )
                        continue

                    if effective_text:
                        # best_text 用作“候选最长文本”，但只有在真正最终结果(status==2/ls==true)时才标记为final
                        if status != 2:
                            self.text = effective_text
                            if not self.has_final_result and len(effective_text) > len(self.best_text):
                                self.best_text = effective_text
                            logger.bind(tag=TAG).info(
                                f"实时更新识别文本: {self.text} (status={status}, 最终帧={self.last_frame_sent})"
                            )

                    if status == 2:
                        # 优先使用 wpgs 合并后的结果（更权威）。若最终包只有标点，则把标点拼到已有文本上。
                        final_text = effective_text or self.best_text or self.text
                        if self._is_punct_only(text):
                            base = final_text
                            if self.best_text and not self._is_punct_only(self.best_text):
                                base = self.best_text
                            elif self.text and not self._is_punct_only(self.text):
                                base = self.text
                            final_text = self._merge_trailing_punct(base, text)
                        else:
                            # 某些网关最终包会“回滚变短”，这里优先选择更完整的版本，避免丢尾字
                            if (
                                self.best_text
                                and not self._is_punct_only(self.best_text)
                                and len(self.best_text) > len(final_text)
                            ):
                                final_text = self.best_text

                        self.text = (final_text or "").strip()
                        self.best_text = self.text
                        self.has_final_result = True
                        logger.bind(tag=TAG).info(f"获取到最终完整文本: {self.text}")
                        self._final_event.set()
                        conn.reset_vad_states()
                        break

                except asyncio.TimeoutError:
                    if self.last_frame_sent:
                        if self.best_text and len(self.best_text) > len(self.text):
                            self.text = self.best_text
                        logger.bind(tag=TAG).info(f"最终帧后超时，使用结果: {self.text}")
                        break
                    continue
                except websockets.ConnectionClosed:
                    logger.bind(tag=TAG).info("ASR服务连接已关闭")
                    break
                except Exception as e:
                    logger.bind(tag=TAG).error(f"处理ASR结果时发生错误: {e}")
                    break
        finally:
            if self.asr_ws:
                await self.asr_ws.close()
                self.asr_ws = None
            self.is_processing = False

    async def handle_voice_stop(self, conn, asr_audio_task: List[bytes]):
        try:
            if self.asr_ws and self.is_processing:
                # 如果还未成功发送首帧，尽量用最后一段音频补发首帧，避免后续直接发末帧触发 NOT_START
                if not self._start_frame_sent:
                    first_pkt = None
                    for pkt in reversed(asr_audio_task or []):
                        if pkt:
                            first_pkt = pkt
                            break
                    if first_pkt:
                        pcm_frame = self.decoder.decode(first_pkt, 960)
                        await self._send_audio_frame(pcm_frame, STATUS_FIRST_FRAME)
                        self._start_frame_sent = True
                        self.server_ready = True
                        await asyncio.sleep(0.05)

                last_frame = b""
                if asr_audio_task:
                    last_audio = asr_audio_task[-1]
                    last_frame = self.decoder.decode(last_audio, 960)
                await self._send_audio_frame(last_frame, STATUS_LAST_FRAME)
                
                # 等待最终识别结果，避免把中间结果提前送入LLM
                # 超时时间可配置，默认3秒（增加默认值以确保完整识别）
                # 使用 or 确保空值、None、0 都会使用默认值
                raw_timeout = self.config.get("final_wait_timeout")
                wait_timeout = float(raw_timeout) if raw_timeout else 3.0
                logger.bind(tag=TAG).info(f"等待最终识别结果，超时时间: {wait_timeout}s (配置值: {raw_timeout})")
                
                try:
                    # 使用 asyncio 友好的方式等待
                    waited = 0.0
                    check_interval = 0.1
                    while waited < wait_timeout:
                        if self._final_event.is_set():
                            logger.bind(tag=TAG).info(f"收到最终结果信号，等待了 {waited:.2f}s")
                            break
                        await asyncio.sleep(check_interval)
                        waited += check_interval
                    
                    if not self._final_event.is_set():
                        logger.bind(tag=TAG).warning(f"等待最终结果超时 ({wait_timeout}s)，使用当前最佳结果")
                except Exception as e:
                    logger.bind(tag=TAG).warning(f"等待最终结果时发生异常: {e}")
                
                # 确保使用最佳文本作为最终结果
                # 优先级：has_final_result 的 best_text > 最长的 best_text > 当前 text
                if self.has_final_result and self.best_text:
                    self.text = self.best_text
                    logger.bind(tag=TAG).info(f"使用最终识别结果: {self.text}")
                elif self.best_text and len(self.best_text) > len(self.text):
                    self.text = self.best_text
                    logger.bind(tag=TAG).info(f"使用最佳中间结果: {self.text}")
                else:
                    logger.bind(tag=TAG).info(f"使用当前结果: {self.text}")

            await super().handle_voice_stop(conn, asr_audio_task)
        except Exception as e:
            logger.bind(tag=TAG).error(f"处理语音停止失败: {e}")

    def stop_ws_connection(self):
        if self.asr_ws:
            asyncio.create_task(self.asr_ws.close())
            self.asr_ws = None
        self.is_processing = False

    async def _cleanup(self, conn):
        try:
            # 不要在cleanup里发送空音频的末帧（会触发 schema 校验失败）
            # 如果需要结束，由 handle_voice_stop 发送带音频的末帧。
            if self.asr_ws and self.is_processing:
                await asyncio.sleep(0.05)
        except Exception:
            pass

        self.is_processing = False
        self.server_ready = False
        self.last_frame_sent = False
        self.best_text = ""
        self.has_final_result = False
        self._final_event.clear()
        self._start_frame_sent = False
        self._wpgs_parts.clear()

        if self.forward_task and not self.forward_task.done():
            self.forward_task.cancel()
            try:
                await asyncio.wait_for(self.forward_task, timeout=1.0)
            except Exception:
                pass
            self.forward_task = None

        if self.asr_ws:
            try:
                await asyncio.wait_for(self.asr_ws.close(), timeout=2.0)
            except Exception:
                pass
            self.asr_ws = None

        if conn:
            if hasattr(conn, "asr_audio_for_voiceprint"):
                conn.asr_audio_for_voiceprint = []
            if hasattr(conn, "asr_audio"):
                conn.asr_audio = []
            if hasattr(conn, "has_valid_voice"):
                conn.has_valid_voice = False

    async def speech_to_text(self, opus_data, session_id, audio_format):
        result = self.text
        self.text = ""
        return result, None

    async def close(self):
        if self.asr_ws:
            await self.asr_ws.close()
            self.asr_ws = None
        if self.forward_task:
            self.forward_task.cancel()
            try:
                await self.forward_task
            except Exception:
                pass
            self.forward_task = None
        self.is_processing = False
