import base64
import json
import uuid
import wave
from io import BytesIO

import requests

from config.logger import setup_logging
from core.providers.tts.base import TTSProviderBase
from core.utils.util import check_model_key

TAG = __name__
logger = setup_logging()


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        self.api_url = config.get("api_url")
        self.api_key = config.get("api_key")
        self.sample_rate = int(config.get("sample_rate", 24000))
        self.audio_coding = config.get("audio_coding", "raw")
        self.session_param = config.get("session_param", {})
        self.debug = str(config.get("debug", "false")).lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        self.output_file = config.get("output_dir", "tmp/")
        self.audio_file_type = "wav"

        model_key_msg = check_model_key("TTS", self.api_key)
        if model_key_msg:
            logger.bind(tag=TAG).error(model_key_msg)

    def _build_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _normalize_session_param(self, session_param: dict) -> dict:
        """sessionParam is map<string,string> (proto). Ensure all keys/values are strings."""
        if not isinstance(session_param, dict):
            return {}
        normalized = {}
        for k, v in session_param.items():
            key = "" if k is None else str(k)
            if v is None:
                val = ""
            elif isinstance(v, bool):
                # JSON boolean would break Go's string unmarshal
                val = "true" if v else "false"
            else:
                val = str(v)
            normalized[key] = val
        return normalized

    def _wrap_pcm_to_wav(self, pcm_bytes: bytes) -> bytes:
        wav_buf = BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm_bytes)
        return wav_buf.getvalue()

    def _decode_result_data(self, data):
        if data is None:
            return b""
        if isinstance(data, str):
            return base64.b64decode(data)
        if isinstance(data, (list, tuple)):
            return bytes(data)
        raise TypeError(f"Unsupported result.data type: {type(data).__name__}")

    def _process_one_response_obj(self, obj, audio_chunks):
        result = obj.get("result") if isinstance(obj, dict) else None
        if result is None and isinstance(obj, dict):
            result = obj
        if not isinstance(result, dict):
            return False

        err_code = result.get("errCode")
        if err_code not in (None, 0, "0"):
            err_str = result.get("errStr")
            raise Exception(f"CMHK XTTS error: errCode={err_code}, errStr={err_str}")

        audio_part = self._decode_result_data(result.get("data"))
        if audio_part:
            audio_chunks.append(audio_part)

        return bool(result.get("endFlag"))

    def _parse_streaming_json(self, resp) -> bytes:
        try:
            data = resp.json()
            audio_chunks = []
            self._process_one_response_obj(data, audio_chunks)
            return b"".join(audio_chunks)
        except Exception:
            pass

        decoder = json.JSONDecoder()
        buffer = ""
        audio_chunks = []

        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            buffer += line
            while buffer:
                buffer_l = buffer.lstrip()
                if not buffer_l:
                    buffer = ""
                    break
                try:
                    obj, idx = decoder.raw_decode(buffer_l)
                except json.JSONDecodeError:
                    break

                end_flag = self._process_one_response_obj(obj, audio_chunks)
                buffer = buffer_l[idx:]
                if end_flag:
                    return b"".join(audio_chunks)

        if buffer.strip():
            try:
                obj = json.loads(buffer)
                self._process_one_response_obj(obj, audio_chunks)
            except Exception:
                pass

        return b"".join(audio_chunks)

    async def text_to_speak(self, text, output_file):
        if not self.api_url:
            raise ValueError("CMHK XTTS api_url is required")

        session_param = dict(self.session_param) if isinstance(self.session_param, dict) else {}
        if "sid" not in session_param:
            session_param["sid"] = f"xiaozhi-{uuid.uuid4().hex}"
        if "sample_rate" not in session_param:
            session_param["sample_rate"] = str(self.sample_rate)
        if "audio_coding" not in session_param:
            session_param["audio_coding"] = str(self.audio_coding)

        session_param = self._normalize_session_param(session_param)

        if self.debug:
            logger.bind(tag=TAG).info(f"CMHK XTTS sessionParam: {session_param}")

        def _request_once(sp: dict):
            payload = {
                "sessionParam": sp,
                "text": text,
                "endFlag": True,
            }
            resp = requests.post(
                self.api_url,
                json=payload,
                headers=self._build_headers(),
                stream=True,
                timeout=10,
            )

            if resp.status_code != 200:
                raise Exception(
                    f"CMHK XTTS request failed: {resp.status_code} - {resp.text}"
                )
            return self._parse_streaming_json(resp)

        try:
            audio_bytes = _request_once(session_param)
        except Exception as e:
            msg = str(e)
            if "errCode=32002" in msg and "bridgeISEMSetParam" in msg:
                sp2 = dict(session_param)
                if "emotion" in sp2 or "emotion_scale" in sp2:
                    sp2.pop("emotion", None)
                    sp2.pop("emotion_scale", None)
                    audio_bytes = _request_once(sp2)
                else:
                    raise
            else:
                raise
        if not audio_bytes:
            raise Exception("CMHK XTTS empty audio data")

        if audio_bytes[:4] == b"RIFF":
            wav_bytes = audio_bytes
        else:
            wav_bytes = self._wrap_pcm_to_wav(audio_bytes)

        if output_file:
            with open(output_file, "wb") as f:
                f.write(wav_bytes)
        else:
            return wav_bytes
