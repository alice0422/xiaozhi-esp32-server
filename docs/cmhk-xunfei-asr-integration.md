# 集团内部讯飞ASR服务接入说明

## 概述

本文档说明如何接入应用市场集团大模型服务中的讯飞ASR服务（版本：ws_iflytek_ast）。

## 服务信息

- **服务版本**: ws_iflytek_ast
- **外网网关地址**: `https://opensseapi.cmhk.com/CMHK-LMMP-PRD_ws_iflytek_ast/CMHK-LMMP-PRD`
- **接口类型**: WebSocket流式接口
- **Provider名称**: `cmhk_xunfei_stream`

## 配置说明

### 基础配置

在配置文件中添加以下配置：

```yaml
ASR:
  cmhk_xunfei_stream:
    type: cmhk_xunfei_stream
    gateway_url: https://opensseapi.cmhk.com/CMHK-LMMP-PRD_ws_iflytek_ast/CMHK-LMMP-PRD
    api_key: Njk4YTRlOGQtZDI3Mi00NGM0LWFmMjUtMDVhYjg3N2I3N777
    auth_method: token  # 或 "hmac"（如果提供api_secret）
    output_dir: tmp/
    
    # 可选配置（如果服务需要）
    app_id: ""  # 可选，如果服务需要app_id
    api_secret: ""  # 可选，如果使用HMAC认证
    
    # 识别参数（保持与讯飞标准接口兼容）
    domain: slm
    language: zh_cn
    accent: mandarin
    dwa: wpgs
```

### 配置参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 固定值：`cmhk_xunfei_stream` |
| `gateway_url` | string | 否 | 网关地址，默认使用提供的地址 |
| `api_key` | string | 是 | API密钥 |
| `auth_method` | string | 否 | 认证方式：`token`（默认）或 `hmac` |
| `app_id` | string | 否 | 应用ID（如果服务需要） |
| `api_secret` | string | 否 | API密钥（如果使用HMAC认证） |
| `domain` | string | 否 | 识别领域，默认：`slm` |
| `language` | string | 否 | 识别语言，默认：`zh_cn` |
| `accent` | string | 否 | 方言，默认：`mandarin` |
| `dwa` | string | 否 | 动态修正，默认：`wpgs` |
| `output_dir` | string | 否 | 输出目录，默认：`tmp/` |

### 认证方式

#### Token认证（默认）

如果只提供 `api_key`，使用简单的Token认证方式：

```yaml
ASR:
  cmhk_xunfei_stream:
    type: cmhk_xunfei_stream
    api_key: Njk4YTRlOGQtZDI3Mi00NGM0LWFmMjUtMDVhYjg3N2I3N777
    auth_method: token
```

API Key会通过以下方式传递：
- URL参数：`?api_key=xxx`
- HTTP Header：`X-API-Key: xxx`

#### HMAC认证

如果提供了 `api_key` 和 `api_secret`，可以使用HMAC-SHA256认证（类似标准讯飞接口）：

```yaml
ASR:
  cmhk_xunfei_stream:
    type: cmhk_xunfei_stream
    api_key: your_api_key
    api_secret: your_api_secret
    auth_method: hmac
```

## 使用方式

### 1. 在配置文件中启用

在 `config.yaml` 中设置：

```yaml
selected_module:
  ASR: cmhk_xunfei_stream
```

### 2. 完整配置示例

```yaml
ASR:
  cmhk_xunfei_stream:
    type: cmhk_xunfei_stream
    gateway_url: https://opensseapi.cmhk.com/CMHK-LMMP-PRD_ws_iflytek_ast/CMHK-LMMP-PRD
    api_key: Njk4YTRlOGQtZDI3Mi00NGM0LWFmMjUtMDVhYjg3N2I3N777
    auth_method: token
    domain: slm
    language: zh_cn
    accent: mandarin
    dwa: wpgs
    output_dir: tmp/

selected_module:
  ASR: cmhk_xunfei_stream
```

## 技术实现

### 实现特点

1. **基于WebSocket流式接口**：支持实时语音识别
2. **兼容讯飞协议**：使用与标准讯飞ASR相同的消息格式
3. **灵活认证**：支持Token和HMAC两种认证方式
4. **音频格式**：支持Opus编码，自动解码为PCM（16kHz, 单声道）

### 工作流程

1. 检测到语音输入时，建立WebSocket连接
2. 发送首帧音频数据
3. 持续发送音频帧进行实时识别
4. 接收并处理识别结果（中间结果和最终结果）
5. 语音停止时发送最后一帧，获取最终识别结果

## 注意事项

1. **认证方式**：根据实际服务要求选择合适的认证方式
   - 如果服务只接受API Key，使用 `auth_method: token`
   - 如果服务需要HMAC签名，提供 `api_secret` 并使用 `auth_method: hmac`

2. **网关地址**：确保网关地址正确，系统会自动将 `https://` 转换为 `wss://` 用于WebSocket连接

3. **网络连接**：确保服务器能够访问外网网关地址

4. **错误处理**：如果连接失败，检查：
   - API Key是否正确
   - 网关地址是否可访问
   - 认证方式是否匹配服务要求

## 故障排查

### 连接失败

- 检查网关地址是否正确
- 检查API Key是否有效
- 检查网络连接是否正常
- 查看日志中的详细错误信息

### 认证失败

- 确认使用的认证方式（token/hmac）是否正确
- 如果使用HMAC认证，确认 `api_secret` 是否正确
- 查看日志中的认证相关错误

### 识别结果为空

- 检查音频格式是否正确（16kHz, 单声道, PCM）
- 检查识别参数（domain, language等）是否合适
- 查看日志中的识别结果信息

## 参考文档

- [应用市场集团大模型服务接口调用文档](https://dcc.cm-worklink.com/docs/Wr3DVzzLVWUEdJkJ/)
- 标准讯飞ASR接口文档（用于协议参考）




