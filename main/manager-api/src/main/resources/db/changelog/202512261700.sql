-- 添加 CMHK 讯飞流式 ASR / CMHK XTTS 供应器与默认模型配置

-- ===============================
-- 1) CMHK 讯飞流式 ASR
-- ===============================

delete from `ai_model_provider` where id = 'SYSTEM_ASR_CMHKXunfeiStreamASR';
INSERT INTO `ai_model_provider` (
  `id`, `model_type`, `provider_code`, `name`, `fields`, `sort`, `creator`, `create_date`, `updater`, `update_date`
) VALUES (
  'SYSTEM_ASR_CMHKXunfeiStreamASR',
  'ASR',
  'cmhk_xunfei_stream',
  'CMHK讯飞流式语音识别',
  '[{"key":"api_key","label":"API Key","type":"string"},{"key":"gateway_url","label":"网关地址","type":"string"},{"key":"api_path","label":"接口路径","type":"string"},{"key":"biz_id","label":"biz_id","type":"string"},{"key":"app_id","label":"app_id","type":"string"},{"key":"final_wait_timeout","label":"最终句等待秒数","type":"number"},{"key":"output_dir","label":"输出目录","type":"string"}]',
  15,
  1,
  NOW(),
  1,
  NOW()
);

-- 默认模型配置

delete from `ai_model_config` where id = 'ASR_CMHKXunfeiStreamASR';
INSERT INTO `ai_model_config` VALUES (
  'ASR_CMHKXunfeiStreamASR',
  'ASR',
  'CMHKXunfeiStreamASR',
  'CMHK讯飞流式语音识别',
  0,
  1,
  '{"type": "cmhk_xunfei_stream", "api_key": "", "gateway_url": "https://opensseapi.cmhk.com/CMHK-LMMP-PRD_ws_iflytek_ast/CMHK-LMMP-PRD", "api_path": "/tuling/ast/v3", "biz_id": "XiaoZhi", "app_id": "", "final_wait_timeout": 2.0, "output_dir": "tmp/"}',
  NULL,
  NULL,
  15,
  NULL,
  NULL,
  NULL,
  NULL
);

-- ===============================
-- 2) CMHK XTTS
-- ===============================

delete from `ai_model_provider` where id = 'SYSTEM_TTS_CMHKXTTS';
INSERT INTO `ai_model_provider` (
  `id`, `model_type`, `provider_code`, `name`, `fields`, `sort`, `creator`, `create_date`, `updater`, `update_date`
) VALUES (
  'SYSTEM_TTS_CMHKXTTS',
  'TTS',
  'cmhk_xtts',
  'CMHK讯飞XTTS',
  '[{"key":"api_url","label":"API地址","type":"string"},{"key":"api_key","label":"API Key","type":"string"},{"key":"sample_rate","label":"采样率","type":"number"},{"key":"audio_coding","label":"编码","type":"string"},{"key":"output_dir","label":"输出目录","type":"string"},{"key":"debug","label":"调试日志","type":"boolean"},{"key":"session_param","label":"session_param","type":"dict","dict_name":"session_param"}]',
  24,
  1,
  NOW(),
  1,
  NOW()
);

-- 默认模型配置

delete from `ai_model_config` where id = 'TTS_CMHKXTTS';
INSERT INTO `ai_model_config` VALUES (
  'TTS_CMHKXTTS',
  'TTS',
  'CMHKXTTS',
  'CMHK讯飞XTTS',
  0,
  1,
  '{"type": "cmhk_xtts", "api_url": "https://opensseapi.cmhk.com/CMHK-LMMP-PRD_ws_iflytek_xtts/CMHK-LMMP-PRD/createRec", "api_key": "", "sample_rate": 24000, "audio_coding": "raw", "output_dir": "tmp/", "debug": false, "session_param": {"native_voice_name": "yezi", "read_number": 3, "read_english": 2, "text_type": 1, "speed": 30, "volume": 20, "pitch": 0}}',
  NULL,
  NULL,
  24,
  NULL,
  NULL,
  NULL,
  NULL
);
