# GitHub Actions CI/CD 说明

## 概述

本项目使用 GitHub Actions 实现持续集成和持续部署（CI/CD），自动构建 Docker 镜像并推送到容器镜像仓库。

## 关于镜像仓库

### GitHub Container Registry (ghcr.io)

**ghcr.io 是什么？**

- **ghcr.io** 是 **GitHub Container Registry** 的域名
- 这是 **GitHub 官方提供的容器镜像仓库服务**（类似于 Docker Hub）
- 它是 GitHub 自己的服务，不是第三方
- 镜像存储在您的 GitHub 账户/组织下，与您的 GitHub 仓库关联

**为什么使用 ghcr.io？**

✅ **免费**：对公开仓库完全免费  
✅ **集成**：与 GitHub 深度集成，无需额外配置  
✅ **安全**：使用 GitHub 的权限系统  
✅ **便捷**：在 GitHub 上可以直接查看和管理镜像

**镜像地址格式：**
```
ghcr.io/<GitHub用户名或组织名>/<仓库名>:<标签>
例如：ghcr.io/xinnan-tech/xiaozhi-esp32-server:server-base
```

### 其他镜像仓库选项

如果您想使用其他镜像仓库，可以修改 workflow 配置：

1. **Docker Hub** (`docker.io`)
   - 需要创建 Docker Hub 账号
   - 在 GitHub Secrets 中添加 `DOCKER_USERNAME` 和 `DOCKER_PASSWORD`

2. **阿里云容器镜像服务** (`registry.cn-hangzhou.aliyuncs.com`)
   - 国内访问速度快
   - 需要阿里云账号

3. **私有镜像仓库**
   - 可以搭建自己的私有仓库
   - 需要配置相应的认证信息

## 工作流程

### 触发条件

Workflow 会在以下情况自动触发：

1. **推送到主分支** (`main` 或 `master`)
   - 当相关文件发生变化时（`main/xiaozhi-server/**`, `main/manager-api/**`, `main/manager-web/**`, Dockerfile 文件等）

2. **Pull Request**
   - 当 PR 涉及相关文件时，会构建镜像用于测试（不会覆盖生产标签）

3. **创建 Release**
   - 当创建新的 GitHub Release 时，会使用版本号作为标签

4. **手动触发**
   - 可以在 GitHub Actions 页面手动触发 workflow

### 构建的镜像

Workflow 会构建三个 Docker 镜像：

1. **server-base** - Python 基础镜像
   - 包含系统依赖和 Python 包
   - 标签：`server-base`, `server-base-<sha>`, `<branch>`, `pr-<number>` 等

2. **server** - 应用服务镜像
   - 基于 server-base，包含应用代码
   - 标签：`server`, `server-<sha>`, `<branch>`, `pr-<number>` 等

3. **web** - Web 管理界面镜像
   - 包含 Vue 前端和 Java 后端
   - 标签：`web`, `web-<sha>`, `<branch>`, `pr-<number>` 等

### 镜像标签策略

- **默认分支（main/master）**：
  - `server-base`, `server`, `web` - 最新稳定版本
  - `server-base-<sha>`, `server-<sha>`, `web-<sha>` - 基于 commit SHA 的版本

- **其他分支**：
  - `<branch-name>` - 分支名作为标签

- **Pull Request**：
  - `pr-<number>` - PR 编号作为标签

- **Release**：
  - `<version>` - 版本号（如 v1.0.0）
  - `<major>.<minor>` - 主次版本号（如 1.0）

### 使用构建的镜像

#### 从 GitHub Container Registry 拉取镜像

```bash
# 登录到 GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# 拉取最新镜像
docker pull ghcr.io/xinnan-tech/xiaozhi-esp32-server:server-base
docker pull ghcr.io/xinnan-tech/xiaozhi-esp32-server:server
docker pull ghcr.io/xinnan-tech/xiaozhi-esp32-server:web
```

#### 使用特定版本

```bash
# 使用特定 commit 的镜像
docker pull ghcr.io/xinnan-tech/xiaozhi-esp32-server:server-base-abc1234
docker pull ghcr.io/xinnan-tech/xiaozhi-esp32-server:server-abc1234

# 使用特定版本的镜像（Release）
docker pull ghcr.io/xinnan-tech/xiaozhi-esp32-server:server-base-v1.0.0
docker pull ghcr.io/xinnan-tech/xiaozhi-esp32-server:server-v1.0.0
```

### 权限要求

Workflow 需要以下权限：
- `contents: read` - 读取仓库内容
- `packages: write` - 推送镜像到 GitHub Container Registry

这些权限会自动通过 `GITHUB_TOKEN` 提供，无需额外配置。

### 查看构建状态

1. 访问 GitHub 仓库的 **Actions** 标签页
2. 选择 **Build and Push Docker Images** workflow
3. 查看构建日志和结果

### 缓存优化

Workflow 使用 GitHub Actions 缓存来加速构建：
- Docker layer 缓存
- 构建缓存会在多次运行之间共享

### 故障排查

如果构建失败：

1. 检查 Actions 日志中的错误信息
2. 确认 Dockerfile 语法正确
3. 检查依赖项是否可用
4. 验证文件路径是否正确

### 本地构建

如果需要本地构建镜像，可以使用项目中的构建脚本：

```bash
# Linux/Mac
./build-local.sh

# Windows
build-local.bat
```

或者直接使用 Docker：

```bash
# 构建 server-base
docker build -t xiaozhi-esp32-server:server-base -f Dockerfile-server-base .

# 构建 server
docker build -t xiaozhi-esp32-server:server -f Dockerfile-server .

# 构建 web
docker build -t xiaozhi-esp32-server:web -f Dockerfile-web .
```

