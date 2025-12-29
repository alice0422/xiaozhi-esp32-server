
### 1) 先点“供应器”那个下拉框

### 2) 选完供应器后，下方“调用信息”会自动出现一堆字段

- **base_url / 基础URL**
  - `https://opensseapi.cmhk.com/CMHK-LMMP-PRD_Qwen2_5_72B/CMHK-LMMP-PRD/v1`
  - **必须以 `/v1` 结尾**（不要填到 `/chat/completions`）

- **model_name / 模型名称**
  - `Qwen2.5-72B`

- **api_key / API密钥**
  - 你自己的 key

- **（可选）temperature / max_tokens / top_p**
  - 先不填也行；想填就：
    - `temperature`: `0.7`
    - `max_tokens`: `1024`
    - `top_p`: `1`

### 3) “模型信息”区域（上面那块）建议这样填
- **模型ID**：`LLM_CMHKQwen72B`（建议只用字母/数字/下划线）
- **模型名称**：`CMHK Qwen2.5-72B`
- **模型编码**：`CMHKQwen72B`
- **排序号**：随意（默认 1）
- **文档地址**：可不填
- **备注**：可写 `CMHK OpenAI-compatible`

### 4) 点“保存”
保存成功后，你会在 LLM 列表里看到这一条。
