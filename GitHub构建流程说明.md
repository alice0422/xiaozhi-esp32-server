# GitHub Actions 构建流程说明

## 生成时间
2026-01-26

---

## ⚠️ 重要说明：0.8.8 vs 0.8.11 构建流程差异

### 版本对比

| 项目 | 0.8.8 (alice0422) | 0.8.11 (xinnan-tech) |
|------|-------------------|----------------------|
| **GitHub仓库** | alice0422/xiaozhi-esp32-server | xinnan-tech/xiaozhi-esp32-server |
| **工作流文件** | docker-build.yml | docker-image.yml |
| **镜像仓库** | ghcr.io/alice0422/xiaozhi-esp32-server | ghcr.io/xinnan-tech/xiaozhi-esp32-server |
| **触发条件** | push/PR/release/手动 | 仅标签/手动/基础镜像完成 |
| **构建策略** | 三个独立job并行构建 | 两个镜像顺序构建 |
| **镜像标签** | 多种标签策略（branch/pr/sha/semver） | 仅版本号和latest |
| **Dependabot** | 跳过Dependabot PR | 无特殊处理 |

---

## 一、0.8.8 构建流程（alice0422个人仓库）

### 1.1 工作流配置

**文件：** `.github/workflows/docker-build.yml`

**触发条件：**
```yaml
on:
  push:
    branches: [main, master]
    paths: [代码和Dockerfile变化]
  pull_request:
    branches: [main, master]
  release:
    types: [created]
  workflow_dispatch:
```

**特点：**
- ✅ 支持push触发（代码变化时自动构建）
- ✅ 支持PR触发（拉取请求时构建测试）
- ✅ 支持release触发
- ✅ 支持手动触发
- ⚠️ 自动跳过Dependabot PR（避免secrets访问问题）

### 1.2 构建流程图

```
推送代码/PR/Release
    ↓
GitHub Actions 触发 (docker-build.yml)
    ↓
┌─────────────────────────────────────┐
│  Job 1: build-server-base           │
│  - 自动转换仓库名为小写              │
│  - 构建: Dockerfile-server-base     │
│  - 标签: server-base, server-base-{sha} │
│  - 推送到: ghcr.io/alice0422/...   │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Job 2: build-server (依赖Job 1)    │
│  - 动态确定基础镜像标签              │
│  - 更新Dockerfile引用               │
│  - 构建: Dockerfile-server          │
│  - 标签: server, server-{sha}       │
│  - 推送到: ghcr.io/alice0422/...   │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Job 3: build-web (独立并行)        │
│  - 构建: Dockerfile-web             │
│  - 标签: web, web-{sha}             │
│  - 推送到: ghcr.io/alice0422/...   │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Job 4: summary (汇总)              │
│  - 生成构建摘要                     │
│  - 显示所有镜像标签                 │
└─────────────────────────────────────┘
```

### 1.3 镜像标签策略

**0.8.8使用的标签类型：**
```yaml
tags: |
  type=ref,event=branch        # 分支名（如 main）
  type=ref,event=pr            # PR编号（如 pr-123）
  type=semver,pattern={{version}}      # 版本号（如 1.0.0）
  type=semver,pattern={{major}}.{{minor}}  # 主次版本（如 1.0）
  type=raw,value=server-base   # 固定标签
  type=raw,value=server-base-{{sha}}  # 带commit SHA
```

**生成的镜像示例：**
```
ghcr.io/alice0422/xiaozhi-esp32-server:main
ghcr.io/alice0422/xiaozhi-esp32-server:pr-123
ghcr.io/alice0422/xiaozhi-esp32-server:server-base
ghcr.io/alice0422/xiaozhi-esp32-server:server-base-abc1234
ghcr.io/alice0422/xiaozhi-esp32-server:server
ghcr.io/alice0422/xiaozhi-esp32-server:server-abc1234
ghcr.io/alice0422/xiaozhi-esp32-server:web
ghcr.io/alice0422/xiaozhi-esp32-server:web-abc1234
```

### 1.4 关键特性

**1. 自动小写转换**
```bash
# 将仓库名称转换为小写（Docker要求）
IMAGE_PREFIX=$(echo "${{ github.repository }}" | tr '[:upper:]' '[:lower:]')
# alice0422/XiaoZhi-ESP32-Server → alice0422/xiaozhi-esp32-server
```

**2. 动态基础镜像引用**
```bash
# 根据触发类型确定基础镜像标签
if [ "${{ github.event_name }}" = "pull_request" ]; then
  echo "base-image=ghcr.io/alice0422/xiaozhi-esp32-server:pr-${PR_NUMBER}"
elif [ "${{ github.ref }}" = "refs/heads/main" ]; then
  echo "base-image=ghcr.io/alice0422/xiaozhi-esp32-server:server-base"
else
  echo "base-image=ghcr.io/alice0422/xiaozhi-esp32-server:${BRANCH_NAME}"
fi
```

**3. Dependabot保护**
```yaml
if: github.actor != 'dependabot[bot]'
# 跳过Dependabot的PR，因为无法访问secrets
```

---

## 二、0.8.11 构建流程（xinnan-tech官方仓库）

### 2.1 工作流配置

**文件：** `.github/workflows/docker-image.yml`

**触发条件：**
```yaml
on:
  push:
    tags:
      - 'v*.*.*'  # 只在打标签时触发
  workflow_dispatch:  # 手动触发
  workflow_run:
    workflows: ["Build Base Image"]
    types: [completed]  # 基础镜像完成后触发
```

**特点：**
- ⚠️ 不支持push触发（代码变化不会自动构建）
- ⚠️ 不支持PR触发
- ✅ 仅在打标签时自动构建
- ✅ 支持手动触发
- ✅ 基础镜像完成后自动触发

### 2.2 构建流程图

```
打标签 (v0.8.11) / 手动触发 / 基础镜像完成
    ↓
GitHub Actions 触发 (docker-image.yml)
    ↓
┌─────────────────────────────────────┐
│  单个Job: release                   │
│  1. 清理磁盘空间                    │
│  2. 提取版本号                      │
│  3. 构建 xiaozhi-server             │
│     - 标签: server_{version}, server_latest │
│  4. 构建 manager-web                │
│     - 标签: web_{version}, web_latest │
│  5. 推送到: ghcr.io/xinnan-tech/... │
└─────────────────────────────────────┘
```

### 2.3 镜像标签策略

**0.8.11使用的标签：**
```yaml
# 如果是版本标签（v0.8.11）
tags: |
  ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_0.8.11
  ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_latest

# 如果不是版本标签（手动触发）
tags: |
  ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_latest
```

**生成的镜像示例：**
```
ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_0.8.11
ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_latest
ghcr.io/xinnan-tech/xiaozhi-esp32-server:web_0.8.11
ghcr.io/xinnan-tech/xiaozhi-esp32-server:web_latest
```

### 2.4 关键特性

**1. 版本提取**
```bash
if [[ "$GITHUB_REF" =~ ^refs/tags/v([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
  echo "VERSION=${BASH_REMATCH[1]}"  # 提取 0.8.11
  echo "IS_VERSION=true"
else
  echo "VERSION=latest"
  echo "IS_VERSION=false"
fi
```

**2. 磁盘空间管理**
```bash
# 构建前清理
docker system prune -af
docker builder prune -af
```

**3. 简化的标签策略**
```yaml
# 使用条件表达式生成标签
tags: |
  ${{ env.IS_VERSION == 'true' && format('ghcr.io/{0}:server_{1},ghcr.io/{0}:server_latest', github.repository, env.VERSION) || format('ghcr.io/{0}:server_latest', github.repository) }}
```

---

## 三、详细差异对比

### 3.1 触发机制差异

| 触发类型 | 0.8.8 (alice0422) | 0.8.11 (xinnan-tech) |
|---------|-------------------|----------------------|
| **代码推送** | ✅ 自动触发 | ❌ 不触发 |
| **Pull Request** | ✅ 自动触发 | ❌ 不触发 |
| **打标签** | ✅ 通过release触发 | ✅ 直接触发 |
| **手动触发** | ✅ 支持 | ✅ 支持 |
| **基础镜像完成** | ❌ 不支持 | ✅ 自动触发 |

### 3.2 构建策略差异

| 项目 | 0.8.8 (alice0422) | 0.8.11 (xinnan-tech) |
|------|-------------------|----------------------|
| **Job数量** | 4个（base, server, web, summary） | 1个（release） |
| **并行构建** | ✅ base→server, web并行 | ❌ 顺序构建 |
| **依赖关系** | server依赖base | 无依赖 |
| **构建时间** | 更快（并行） | 较慢（顺序） |

### 3.3 镜像标签差异

| 标签类型 | 0.8.8 (alice0422) | 0.8.11 (xinnan-tech) |
|---------|-------------------|----------------------|
| **分支标签** | ✅ main, master | ❌ 无 |
| **PR标签** | ✅ pr-123 | ❌ 无 |
| **SHA标签** | ✅ server-abc1234 | ❌ 无 |
| **版本标签** | ✅ 1.0.0, 1.0 | ✅ server_0.8.11 |
| **latest标签** | ❌ 无 | ✅ server_latest |
| **固定标签** | ✅ server-base, server, web | ❌ 无 |

### 3.4 镜像仓库差异

| 项目 | 0.8.8 (alice0422) | 0.8.11 (xinnan-tech) |
|------|-------------------|----------------------|
| **仓库地址** | ghcr.io/alice0422/xiaozhi-esp32-server | ghcr.io/xinnan-tech/xiaozhi-esp32-server |
| **所有者** | 个人账户 | 组织账户 |
| **访问权限** | 个人控制 | 团队控制 |
| **镜像可见性** | 公开 | 公开 |

---

## 四、使用建议

### 4.1 0.8.8 (alice0422) 适用场景

**优势：**
- ✅ 开发友好：每次push都自动构建
- ✅ PR测试：拉取请求自动构建测试镜像
- ✅ 多标签：可以通过不同标签追踪不同版本
- ✅ 灵活：支持多种触发方式

**适用于：**
- 个人开发和测试
- 快速迭代
- 需要PR测试的场景
- 多分支开发

**使用示例：**
```bash
# 拉取最新main分支镜像
docker pull ghcr.io/alice0422/xiaozhi-esp32-server:main

# 拉取特定PR的测试镜像
docker pull ghcr.io/alice0422/xiaozhi-esp32-server:pr-123

# 拉取特定commit的镜像
docker pull ghcr.io/alice0422/xiaozhi-esp32-server:server-abc1234
```

### 4.2 0.8.11 (xinnan-tech) 适用场景

**优势：**
- ✅ 稳定：仅在打标签时发布
- ✅ 版本管理：清晰的版本号标签
- ✅ 官方：组织账户，更正式
- ✅ 简洁：标签策略简单明了

**适用于：**
- 生产环境部署
- 正式版本发布
- 需要版本追溯
- 团队协作

**使用示例：**
```bash
# 拉取最新稳定版
docker pull ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_latest

# 拉取特定版本
docker pull ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_0.8.11

# 使用国内加速
docker pull ghcr.nju.edu.cn/xinnan-tech/xiaozhi-esp32-server:server_latest
```


---

## 五、如何发布新版本

### 5.1 0.8.8 (alice0422) 发布流程

**方式1：推送代码自动构建**
```bash
# 修改代码
git add .
git commit -m "feat: 添加新功能"
git push origin main

# 自动触发构建，生成镜像：
# - ghcr.io/alice0422/xiaozhi-esp32-server:main
# - ghcr.io/alice0422/xiaozhi-esp32-server:server
# - ghcr.io/alice0422/xiaozhi-esp32-server:web
```

**方式2：创建Release**
```bash
# 1. 在GitHub上创建Release
# 2. 自动触发构建，生成带版本号的镜像
```

**方式3：手动触发**
```bash
# 在GitHub Actions页面手动触发 docker-build.yml
```

### 5.2 0.8.11 (xinnan-tech) 发布流程

**方式1：打标签发布（推荐）**
```bash
# 1. 修改代码并提交
git add .
git commit -m "feat: 添加新功能"
git push origin main

# 2. 打版本标签
git tag v0.8.11
git push origin v0.8.11

# 3. 自动触发构建，生成镜像：
# - ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_0.8.11
# - ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_latest
# - ghcr.io/xinnan-tech/xiaozhi-esp32-server:web_0.8.11
# - ghcr.io/xinnan-tech/xiaozhi-esp32-server:web_latest
```

**方式2：手动触发**
```bash
# 在GitHub Actions页面手动触发 docker-image.yml
# 仅生成 latest 标签
```

---

## 六、常见问题

### 6.1 为什么0.8.8有这么多标签？

**原因：**
- 0.8.8使用`docker/metadata-action`自动生成多种标签
- 支持开发、测试、生产等多种场景
- 方便追踪不同分支、PR、commit的镜像

**示例场景：**
```bash
# 开发环境：使用main分支最新镜像
docker-compose.yml:
  image: ghcr.io/alice0422/xiaozhi-esp32-server:main

# 测试PR：使用PR专用镜像
docker-compose.yml:
  image: ghcr.io/alice0422/xiaozhi-esp32-server:pr-123

# 回滚：使用特定commit的镜像
docker-compose.yml:
  image: ghcr.io/alice0422/xiaozhi-esp32-server:server-abc1234
```

### 6.2 为什么0.8.11只有latest和版本号标签？

**原因：**
- 0.8.11是官方仓库，强调稳定性
- 仅在打标签时发布，避免频繁构建
- 简化标签策略，便于生产环境使用

**设计理念：**
```
开发 → 测试 → 打标签 → 发布
         ↓
    在0.8.8测试
         ↓
    合并到0.8.11
         ↓
    打标签发布
```

### 6.3 如何在0.8.8和0.8.11之间迁移？

**从0.8.8迁移到0.8.11：**
```bash
# 1. 修改docker-compose.yml
# 旧配置（0.8.8）
services:
  xiaozhi-server:
    image: ghcr.io/alice0422/xiaozhi-esp32-server:main

# 新配置（0.8.11）
services:
  xiaozhi-server:
    image: ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_latest
    # 或使用国内加速
    # image: ghcr.nju.edu.cn/xinnan-tech/xiaozhi-esp32-server:server_latest

# 2. 拉取新镜像
docker-compose pull

# 3. 重启服务
docker-compose up -d
```

**从0.8.11回退到0.8.8：**
```bash
# 修改docker-compose.yml，使用0.8.8镜像
services:
  xiaozhi-server:
    image: ghcr.io/alice0422/xiaozhi-esp32-server:server

# 拉取并重启
docker-compose pull
docker-compose up -d
```

### 6.4 Dependabot为什么会失败？

**问题：**
- Dependabot创建的PR无法访问仓库的secrets
- 导致无法登录到ghcr.io推送镜像
- 构建失败

**0.8.8的解决方案：**
```yaml
# 在每个job中添加条件
if: github.actor != 'dependabot[bot]'
```

**效果：**
- Dependabot的PR会跳过构建
- 不会因为无法访问secrets而失败
- 合并后会正常构建

**0.8.11的处理：**
- 不支持PR触发，所以没有这个问题

### 6.5 如何查看构建日志？

**步骤：**
```
1. 访问GitHub仓库
2. 点击 "Actions" 标签
3. 选择对应的工作流：
   - 0.8.8: "Build and Push Docker Images"
   - 0.8.11: "Docker Image CI"
4. 点击具体的运行记录
5. 查看各个job的日志
```

**日志内容：**
- 构建步骤
- 错误信息
- 镜像标签
- 推送结果

---

## 七、最佳实践

### 7.1 开发阶段

**使用0.8.8 (alice0422)：**
```bash
# 1. 创建功能分支
git checkout -b feature/new-function

# 2. 开发并提交
git add .
git commit -m "feat: 新功能"
git push origin feature/new-function

# 3. 创建PR
# 自动构建测试镜像: pr-123

# 4. 测试
docker pull ghcr.io/alice0422/xiaozhi-esp32-server:pr-123
docker run ...

# 5. 合并到main
# 自动构建main镜像
```

### 7.2 发布阶段

**使用0.8.11 (xinnan-tech)：**
```bash
# 1. 确保代码在0.8.8测试通过

# 2. 合并到0.8.11的main分支
git checkout main
git merge feature/new-function
git push origin main

# 3. 打版本标签
git tag v0.8.11
git push origin v0.8.11

# 4. 自动构建并发布
# 生成: server_0.8.11, server_latest

# 5. 更新生产环境
docker-compose pull
docker-compose up -d
```

### 7.3 生产环境

**推荐配置：**
```yaml
# docker-compose.yml
services:
  xiaozhi-server:
    # 使用特定版本（推荐）
    image: ghcr.nju.edu.cn/xinnan-tech/xiaozhi-esp32-server:server_0.8.11
    
    # 或使用latest（自动更新）
    # image: ghcr.nju.edu.cn/xinnan-tech/xiaozhi-esp32-server:server_latest
    
    restart: always
    
  xiaozhi-web:
    image: ghcr.nju.edu.cn/xinnan-tech/xiaozhi-esp32-server:web_0.8.11
    restart: always
```

**更新策略：**
```bash
# 方式1：手动更新到新版本
# 修改docker-compose.yml中的版本号
# server_0.8.11 → server_0.8.12
docker-compose pull
docker-compose up -d

# 方式2：使用latest自动更新
# 定期拉取最新镜像
docker-compose pull
docker-compose up -d
```

---

## 八、总结

### 8.1 核心差异

**0.8.8 (alice0422)：**
- 🎯 定位：开发测试仓库
- 🚀 特点：自动化、灵活、多标签
- 👥 适用：个人开发、快速迭代
- 📦 镜像：ghcr.io/alice0422/xiaozhi-esp32-server

**0.8.11 (xinnan-tech)：**
- 🎯 定位：官方发布仓库
- 🚀 特点：稳定、版本化、简洁
- 👥 适用：生产环境、团队协作
- 📦 镜像：ghcr.io/xinnan-tech/xiaozhi-esp32-server

### 8.2 工作流程建议

```
开发 (0.8.8)
  ↓
测试 (0.8.8)
  ↓
合并 (0.8.11)
  ↓
打标签 (0.8.11)
  ↓
发布 (0.8.11)
  ↓
部署 (生产环境)
```

### 8.3 镜像选择指南

| 场景 | 推荐镜像 | 原因 |
|------|---------|------|
| **本地开发** | alice0422:main | 最新开发版本 |
| **功能测试** | alice0422:pr-123 | PR专用镜像 |
| **集成测试** | alice0422:server | 稳定开发版 |
| **预发布环境** | xinnan-tech:server_latest | 最新稳定版 |
| **生产环境** | xinnan-tech:server_0.8.11 | 特定版本 |
| **回滚** | xinnan-tech:server_0.8.10 | 上一个版本 |

---

**文档生成时间：** 2026-01-26  
**适用版本：** 0.8.8 (alice0422) / 0.8.11 (xinnan-tech)  
**状态：** ✅ 完整说明，包含详细差异对比
