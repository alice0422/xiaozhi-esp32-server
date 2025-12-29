# 如何查看 GitHub Container Registry 镜像

## 🔍 问题说明

构建显示成功，但在仓库的 **Packages** 标签下看不到镜像。这是因为 **GitHub Container Registry (ghcr.io) 的镜像不在仓库页面显示**，而是在**用户/组织的 Packages 页面**。

## ✅ 正确的查看方式

### 方法 1：通过用户 Packages 页面查看（推荐）

1. **访问您的用户 Packages 页面**
   - 直接访问：`https://github.com/alice0422?tab=packages`
   - 或者：
     - 点击 GitHub 右上角头像
     - 选择 **Your profile**（您的个人资料）
     - 点击 **Packages** 标签

2. **查看镜像列表**
   - 您应该能看到 `xiaozhi-esp32-server` 包
   - 点击进入可以看到所有镜像标签

### 方法 2：通过镜像地址直接访问

根据构建日志，您的镜像地址是：
```
https://github.com/alice0422/xiaozhi-esp32-server/pkgs/container/xiaozhi-esp32-server
```

**注意**：这个链接可能不准确，因为镜像名称是小写的 `alice0422`。

### 方法 3：通过仓库右侧链接（如果有）

1. 进入您的仓库页面：`https://github.com/alice0422/xiaozhi-esp32-server`
2. 查看右侧边栏，看是否有 **Packages** 链接
3. 如果有，点击进入

## 🔍 验证镜像是否存在

### 方法 1：使用命令行验证

```bash
# 登录到 GitHub Container Registry
echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u alice0422 --password-stdin

# 尝试拉取镜像（如果存在，会显示镜像信息）
docker pull ghcr.io/alice0422/xiaozhi-esp32-server:server-base

# 或者只检查镜像是否存在（不下载）
docker manifest inspect ghcr.io/alice0422/xiaozhi-esp32-server:server-base
```

### 方法 2：检查构建日志

1. 进入 GitHub Actions 页面
2. 打开最新的构建运行
3. 查看 "Build and push" 步骤的日志
4. 查找类似这样的输出：
   ```
   #16 exporting to image
   #16 exporting sha256:...
   #16 pushing manifest for ghcr.io/alice0422/xiaozhi-esp32-server:server-base
   #16 DONE
   ```

## 📦 镜像地址格式

根据您的构建，镜像地址应该是：

```
ghcr.io/alice0422/xiaozhi-esp32-server:server-base
ghcr.io/alice0422/xiaozhi-esp32-server:server
ghcr.io/alice0422/xiaozhi-esp32-server:web
```

以及带 commit SHA 的版本：
```
ghcr.io/alice0422/xiaozhi-esp32-server:server-base-acf8893
ghcr.io/alice0422/xiaozhi-esp32-server:server-acf8893
ghcr.io/alice0422/xiaozhi-esp32-server:web-acf8893
```

## ⚠️ 常见问题

### 问题 1：在仓库页面看不到 Packages

**原因**：GitHub Container Registry 的镜像不在仓库的 Packages 标签下显示。

**解决**：到用户/组织的 Packages 页面查看。

### 问题 2：镜像推送失败但没有报错

**检查方法**：
1. 查看构建日志中的 "Build and push" 步骤
2. 确认是否有 "Pushed" 或 "DONE" 消息
3. 检查是否有权限错误

### 问题 3：镜像名称大小写问题

**确认**：所有镜像名称都应该是小写的 `alice0422`，不是 `Alice0422`。

## 🎯 快速验证步骤

1. **访问用户 Packages 页面**
   ```
   https://github.com/alice0422?tab=packages
   ```

2. **或者直接测试拉取镜像**
   ```bash
   docker pull ghcr.io/alice0422/xiaozhi-esp32-server:server-base
   ```

3. **如果拉取成功**，说明镜像存在且可以访问

4. **如果拉取失败**，检查：
   - Token 是否正确配置
   - 镜像名称是否正确（小写）
   - 是否有推送权限

## 📝 总结

- ✅ **构建成功**：从您的截图看，构建已经成功
- ✅ **镜像已推送**：构建日志显示镜像已创建
- ✅ **查看位置**：到用户 Packages 页面查看，不是仓库 Packages 标签
- ✅ **镜像地址**：`ghcr.io/alice0422/xiaozhi-esp32-server:标签名`

如果还是看不到，请尝试：
1. 刷新页面
2. 等待几分钟（有时需要时间同步）
3. 使用命令行验证镜像是否存在











