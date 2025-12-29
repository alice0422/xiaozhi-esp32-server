# 使用 GitHub Container Registry 镜像部署说明

## 📦 镜像地址

修改后的 `docker-compose_all.yml` 使用以下镜像：

- **Server 镜像**：`ghcr.io/alice0422/xiaozhi-esp32-server:server`
- **Web 镜像**：`ghcr.io/alice0422/xiaozhi-esp32-server:web`

## 🔐 使用前准备：登录 GitHub Container Registry

**重要**：使用 GitHub Container Registry 的镜像前，必须先登录！

### 步骤 1：创建 GitHub Personal Access Token

1. 访问：https://github.com/settings/tokens
2. 点击 **Generate new token** → **Generate new token (classic)**
3. 填写 Token 名称（如：`docker-login`）
4. 选择过期时间
5. **勾选权限**：
   - ✅ `read:packages` - 读取镜像（必须）
   - ✅ `write:packages` - 推送镜像（如果需要推送，可选）
6. 点击 **Generate token**
7. **立即复制 Token**（只显示一次！）

### 步骤 2：登录到 GitHub Container Registry

```bash
# 使用您的 GitHub Token 登录
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u alice0422 --password-stdin
```

**示例**：
```bash
# 将 YOUR_GITHUB_TOKEN 替换为实际的 Token
echo "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" | docker login ghcr.io -u alice0422 --password-stdin
```

**成功后会显示**：
```
Login Succeeded
```

## 🚀 部署步骤

### 1. 确保已登录

```bash
# 检查是否已登录
docker login ghcr.io
```

### 2. 拉取镜像（可选，docker-compose 会自动拉取）

```bash
# 拉取最新镜像
docker pull ghcr.io/alice0422/xiaozhi-esp32-server:server
docker pull ghcr.io/alice0422/xiaozhi-esp32-server:web
```

### 3. 启动服务

```bash
cd main/xiaozhi-server
docker-compose -f docker-compose_all.yml up -d
```

### 4. 查看服务状态

```bash
docker-compose -f docker-compose_all.yml ps
```

## 🔄 更新镜像

### 方法 1：使用最新标签（推荐）

`docker-compose_all.yml` 中使用的是 `server` 和 `web` 标签，这些标签会**自动指向最新版本**。

当 GitHub Actions 构建新镜像后，只需：

```bash
# 拉取最新镜像
docker-compose -f docker-compose_all.yml pull

# 重启服务
docker-compose -f docker-compose_all.yml up -d
```

### 方法 2：使用特定版本

如果想使用特定 commit 的镜像，可以修改 `docker-compose_all.yml`：

```yaml
# 使用特定 commit 的镜像
image: ghcr.io/alice0422/xiaozhi-esp32-server:server-acf8893
```

## ⚠️ 注意事项

### 1. Token 过期

GitHub Token 可能会过期，如果拉取镜像失败，需要：
1. 重新生成 Token
2. 重新登录：`docker login ghcr.io`

### 2. 私有镜像

如果您的仓库是私有的，确保：
- Token 有 `read:packages` 权限
- 镜像设置为私有（默认情况下，私有仓库的镜像是私有的）

### 3. 镜像标签

- `server` / `web` - 最新稳定版本（推荐使用）
- `server-acf8893` / `web-acf8893` - 特定 commit 的版本
- `main` - 主分支标签

### 4. 网络问题

如果拉取镜像速度慢，可以考虑：
- 使用镜像加速器
- 或者先手动拉取镜像，再启动服务

## 🔍 故障排查

### 问题 1：拉取镜像失败 - "unauthorized"

**原因**：未登录或 Token 无效

**解决**：
```bash
# 重新登录
docker login ghcr.io
```

### 问题 2：拉取镜像失败 - "not found"

**原因**：镜像名称错误或镜像不存在

**解决**：
1. 检查镜像名称是否正确（小写：`alice0422`）
2. 确认镜像已成功构建（查看 GitHub Actions）
3. 检查镜像标签是否存在

### 问题 3：拉取镜像很慢

**原因**：网络问题

**解决**：
1. 使用镜像加速器
2. 或者先手动拉取，再启动服务

## 📝 完整部署命令

```bash
# 1. 登录（首次使用）
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u alice0422 --password-stdin

# 2. 进入目录
cd main/xiaozhi-server

# 3. 拉取最新镜像
docker-compose -f docker-compose_all.yml pull

# 4. 启动服务
docker-compose -f docker-compose_all.yml up -d

# 5. 查看日志
docker-compose -f docker-compose_all.yml logs -f
```

## 🎯 总结

- ✅ 使用 GitHub Container Registry 的镜像，无需本地构建
- ✅ 镜像会自动更新到最新版本
- ✅ 需要先登录 `ghcr.io`
- ✅ 使用 `server` 和 `web` 标签获取最新版本

现在您可以直接使用 GitHub Actions 构建的镜像了！🚀











