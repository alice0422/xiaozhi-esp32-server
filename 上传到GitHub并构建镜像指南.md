# 上传项目到 GitHub 并构建镜像完整指南

## 📋 准备工作

### 1. 确认您的 GitHub 仓库信息

根据您提供的信息：
- GitHub 用户名：`Alice0422`
- 仓库地址：`https://github.com/Alice0422`

**请确认您的仓库名称**（例如：`xiaozhi-esp32-server` 或其他名称）

### 2. 配置文件说明

✅ **好消息**：配置文件已经自动适配，无需手动修改！

- **`.github/workflows/docker-build.yml`** - 已配置为自动使用当前仓库名称
- **`Dockerfile-server`** - 构建时会自动替换基础镜像名称

**您只需要：**
1. 确保您的 GitHub 仓库名称正确（例如：`xiaozhi-esp32-server`）
2. 直接上传代码即可

## 📤 上传项目到 GitHub

### ⚠️ 重要：先创建 GitHub 仓库

**在执行 Git 命令之前，您需要先在 GitHub 上创建仓库！**

### 步骤 1：在 GitHub 上创建仓库

1. **登录 GitHub**
   - 访问：https://github.com
   - 使用您的账号 `Alice0422` 登录

2. **创建新仓库**
   - 点击右上角的 **+** 号 → 选择 **New repository**
   - 或者直接访问：https://github.com/new

3. **填写仓库信息**
   - **Repository name**: `xiaozhi-esp32-server`（或您想要的其他名称）
   - **Description**: 可选，例如：`小智ESP32后端服务`
   - **Visibility**: 
     - ✅ **Public**（公开）- 推荐，GitHub Container Registry 对公开仓库免费
     - ⚠️ **Private**（私有）- 如果选择私有，需要确保 Token 有访问私有仓库的权限
   - **不要勾选**以下选项（因为您要上传现有代码）：
     - ❌ Add a README file
     - ❌ Add .gitignore
     - ❌ Choose a license
   - 点击 **Create repository**

4. **复制仓库地址**
   - 创建成功后，GitHub 会显示仓库地址
   - 例如：`https://github.com/Alice0422/xiaozhi-esp32-server.git`
   - **保存这个地址，下一步会用到**

### 步骤 2：使用 Git 命令行上传代码

1. **初始化 Git 仓库**（如果还没有）
```bash
cd E:\Packages\XIAOZHI\xiaozhi-esp32-server-0.8.8
git init
```

2. **添加远程仓库**
```bash
# 使用刚才创建的仓库地址（替换为您的实际仓库名）
git remote add origin https://github.com/Alice0422/xiaozhi-esp32-server.git

# 或者使用 SSH（如果您配置了 SSH key）
# git remote add origin git@github.com:Alice0422/xiaozhi-esp32-server.git
```

**⚠️ 注意**：如果仓库名不是 `xiaozhi-esp32-server`，请替换为您实际创建的仓库名。

3. **检查 .gitignore 文件**
确保 `.gitignore` 文件存在且包含以下内容（项目已包含）：
- `node_modules/`
- `target/` (Java 编译输出)
- `.env` 文件
- `__pycache__/`
- 其他构建产物

4. **添加文件并提交**
```bash
# 查看将要提交的文件（确保没有敏感信息）
git status

# 添加所有文件
git add .

# 提交
git commit -m "Initial commit: xiaozhi-esp32-server v0.8.8"
```

5. **推送到 GitHub**
```bash
# 如果您的默认分支是 main
git branch -M main
git push -u origin main

# 或者如果是 master
git branch -M master
git push -u origin master
```

### 方法二：使用 GitHub Desktop 或 VS Code

1. **先在 GitHub 网页上创建新仓库**（参考上面的步骤 1）
2. 使用 GitHub Desktop 或 VS Code 的 Git 功能上传代码

## 🔐 配置 GitHub Secrets

上传代码后，需要配置 GitHub Personal Access Token：

### 1. 创建 Personal Access Token

1. 访问：https://github.com/settings/tokens
2. 点击 **Generate new token** → **Generate new token (classic)**
3. 填写 Token 名称（如：`xiaozhi-docker-build`）
4. 选择过期时间
5. **勾选权限**：
   - ✅ `write:packages` - 推送镜像到 GitHub Container Registry
   - ✅ `read:packages` - 读取镜像
   - ✅ `delete:packages` - 删除镜像（可选）
6. 点击 **Generate token**
7. **立即复制 Token**（只显示一次！）

### 2. 添加到仓库 Secrets

1. 进入您的仓库页面：`https://github.com/Alice0422/您的仓库名`
2. 点击仓库顶部的 **Settings** 标签
3. 左侧菜单找到 **Secrets and variables** → 点击 **Actions**
4. 点击右上角的 **New repository secret**
5. 填写：
   - **Name**: `TOKEN`
   - **Value**: 粘贴刚才复制的 Token
6. 点击 **Add secret**

## 🚀 触发构建

### 方法一：自动触发（推送代码后）

推送代码到 `main` 或 `master` 分支后，GitHub Actions 会自动触发构建。

### 方法二：手动触发

1. 进入仓库的 **Actions** 标签页
2. 选择 **Build and Push Docker Images** workflow
3. 点击 **Run workflow** 按钮
4. 选择分支（通常是 `main` 或 `master`）
5. 点击 **Run workflow**

## 📦 查看构建结果

### 1. 查看构建日志

- 进入 **Actions** 标签页
- 点击最新的 workflow run
- 查看各个 job 的构建日志

### 2. 查看构建的镜像

构建成功后，镜像会推送到：
```
ghcr.io/Alice0422/您的仓库名:server-base
ghcr.io/Alice0422/您的仓库名:server
ghcr.io/Alice0422/您的仓库名:web
```

查看方式：
1. 在仓库页面右侧找到 **Packages** 链接
2. 或访问：`https://github.com/Alice0422/您的仓库名/pkgs/container/您的仓库名`

## ⚠️ 注意事项

### 1. 不需要上传的文件

根据 `.gitignore`，以下文件/目录**不会**被上传：
- ✅ `node_modules/` - Node.js 依赖（会在构建时安装）
- ✅ `target/` - Java 编译输出（会在构建时编译）
- ✅ `.env` - 环境变量文件（包含敏感信息）
- ✅ `__pycache__/` - Python 缓存
- ✅ `main/xiaozhi-server/data/` - 运行时数据
- ✅ `main/manager-api/target/` - Java 编译输出
- ✅ 其他构建产物和临时文件

### 2. 可能冲突的文件

检查以下文件是否包含需要修改的内容：
- ✅ `.github/workflows/docker-build.yml` - **必须修改** `IMAGE_PREFIX`
- ✅ `Dockerfile-server` - 会在构建时自动处理，无需手动修改
- ⚠️ 文档中的链接 - 包含原项目的 GitHub 链接，不影响构建

### 3. 构建时间

首次构建可能需要较长时间（20-40 分钟），因为需要：
- 下载基础镜像
- 安装所有依赖
- 编译 Java 代码
- 构建前端资源

后续构建会使用缓存，速度会快很多。

## 🔍 故障排查

### 问题 1：构建失败 - "Login to Container Registry" 失败

**原因**：Token 配置错误或权限不足

**解决**：
1. 检查 Secrets 中的 `TOKEN` 是否正确
2. 确认 Token 有 `write:packages` 权限
3. 重新生成 Token 并更新 Secrets

### 问题 2：构建失败 - 镜像名称错误

**原因**：仓库名称不正确

**解决**：
1. 确认您的 GitHub 仓库名称正确
2. Workflow 会自动使用 `github.repository` 变量，格式为：`用户名/仓库名`
3. 如果仓库名包含特殊字符，建议使用简单的名称（如：`xiaozhi-esp32-server`）

### 问题 3：构建失败 - Dockerfile 找不到文件

**原因**：文件路径错误

**解决**：
1. 检查 Dockerfile 中的 `COPY` 命令
2. 确保所有需要的文件都已提交到仓库
3. 检查 `.gitignore` 是否误忽略了必要文件

### 问题 4：推送镜像失败 - 权限不足

**原因**：Token 权限不足或仓库设置为私有

**解决**：
1. 确认 Token 有 `write:packages` 权限
2. 如果仓库是私有的，确保 Token 有访问私有仓库的权限
3. 检查仓库的 Packages 设置

## 📝 验证清单

上传前请确认：

- [ ] 已确认仓库名称正确（例如：`xiaozhi-esp32-server`）
- [ ] 已检查 `.gitignore` 文件
- [ ] 已确认没有敏感信息（API keys、密码等）被提交
- [ ] 已创建 GitHub Personal Access Token
- [ ] 已在仓库 Secrets 中添加 `TOKEN`
- [ ] 已推送代码到 GitHub
- [ ] 已触发构建或等待自动构建

## 🎉 完成

构建成功后，您就可以使用以下命令拉取镜像：

```bash
# 登录到 GitHub Container Registry
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u Alice0422 --password-stdin

# 拉取镜像
docker pull ghcr.io/Alice0422/您的仓库名:server-base
docker pull ghcr.io/Alice0422/您的仓库名:server
docker pull ghcr.io/Alice0422/您的仓库名:web
```

祝您构建顺利！🚀

