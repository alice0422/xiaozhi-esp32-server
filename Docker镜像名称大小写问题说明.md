# Docker 镜像名称大小写问题说明

## 🔍 问题现象

构建 `server` 镜像时出现错误：

```
ERROR: failed to build: failed to solve: failed to parse stage name 
"ghcr.io/Alice0422/xiaozhi-esp32-server:server-base": 
invalid reference format: repository name (Alice0422/xiaozhi-esp32-server) 
must be lowercase
```

## ❓ 问题原因

### Docker 镜像名称规则

**Docker 镜像名称必须全部使用小写字母**，这是 Docker 的硬性要求。

### 具体问题

1. **GitHub 用户名包含大写字母**
   - 您的 GitHub 用户名是 `Alice0422`（包含大写字母 `A`）
   - `github.repository` 返回：`Alice0422/xiaozhi-esp32-server`
   - 但 Docker 要求：`alice0422/xiaozhi-esp32-server`

2. **镜像名称格式**
   - ❌ 错误：`ghcr.io/Alice0422/xiaozhi-esp32-server:server-base`
   - ✅ 正确：`ghcr.io/alice0422/xiaozhi-esp32-server:server-base`

## ✅ 解决方案

### 已实施的修复

我已经修改了 `.github/workflows/docker-build.yml`，在每个构建 job 中添加了**自动转换为小写**的步骤：

```yaml
- name: Set image prefix (lowercase)
  id: set-image-prefix
  run: |
    # 将仓库名称转换为小写，因为 Docker 镜像名称必须全部小写
    IMAGE_PREFIX=$(echo "${{ github.repository }}" | tr '[:upper:]' '[:lower:]')
    echo "IMAGE_PREFIX=${IMAGE_PREFIX}" >> $GITHUB_ENV
```

### 修复内容

1. **在所有构建 job 中添加小写转换**
   - `build-server-base`
   - `build-server`
   - `build-web`

2. **确保所有镜像引用都使用小写**
   - 基础镜像引用
   - 镜像标签
   - 推送目标

## 📦 修复后的镜像地址

修复后，所有镜像将使用小写名称：

```
ghcr.io/alice0422/xiaozhi-esp32-server:server-base
ghcr.io/alice0422/xiaozhi-esp32-server:server
ghcr.io/alice0422/xiaozhi-esp32-server:web
```

## 🔄 下一步操作

1. **提交并推送修改**
   ```bash
   git add .github/workflows/docker-build.yml
   git commit -m "修复：将 Docker 镜像名称转换为小写"
   git push
   ```

2. **重新触发构建**
   - 推送代码后会自动触发
   - 或在 Actions 页面手动触发

3. **验证构建**
   - 检查构建日志，确认镜像名称都是小写
   - 确认构建成功

## 📝 注意事项

### GitHub Container Registry 的镜像名称

- ✅ **镜像名称**：必须小写（`alice0422/xiaozhi-esp32-server`）
- ✅ **GitHub 仓库名**：可以包含大写（`Alice0422/xiaozhi-esp32-server`）
- ✅ **自动转换**：Workflow 会自动处理大小写转换

### 拉取镜像时

使用小写名称拉取镜像：

```bash
# 登录
echo "YOUR_TOKEN" | docker login ghcr.io -u alice0422 --password-stdin

# 拉取镜像（使用小写）
docker pull ghcr.io/alice0422/xiaozhi-esp32-server:server-base
docker pull ghcr.io/alice0422/xiaozhi-esp32-server:server
docker pull ghcr.io/alice0422/xiaozhi-esp32-server:web
```

## 🎯 总结

- ✅ **问题**：Docker 镜像名称必须小写，但 GitHub 用户名包含大写字母
- ✅ **解决**：在 workflow 中自动将仓库名称转换为小写
- ✅ **效果**：所有镜像名称自动使用小写，构建成功

现在可以正常构建镜像了！🚀

