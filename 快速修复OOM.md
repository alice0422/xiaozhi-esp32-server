# 🚨 快速修复OOM问题

## 问题确认
- ✅ 系统日志确认：`apt-get` 进程被OOM killer杀死
- ✅ 没有Swap空间：`Swap: 0B`
- ✅ Docker镜像占用：14.4GB

## 🚀 三步修复（按顺序执行）

### 步骤1：添加Swap空间（必须）

```bash
# 创建4GB swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 永久启用
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 验证（应该看到Swap有4G）
free -h
```

### 步骤2：清理Docker缓存（释放空间）

```bash
# 清理未使用的镜像和缓存
docker system prune -a -f

# 查看释放了多少空间
docker system df
```

### 步骤3：使用优化版Dockerfile重新构建

```bash
# 使用优化版（分批安装，减少内存峰值）
docker build -t xiaozhi-esp32-server:server-base -f ./Dockerfile-server-base-optimized .
```

或者直接运行修改后的构建脚本：
```bash
./build-local.sh
```

## ✅ 验证修复

构建过程中，另开一个终端监控内存：
```bash
# 监控内存使用
watch -n 1 free -h
```

应该看到：
- Swap空间被使用（说明在正常工作）
- 内存使用不会超过物理内存+swap的总和

## 📊 预期结果

- **Swap空间**：4GB可用
- **构建成功**：不再出现exit code 137
- **构建时间**：可能稍长（因为使用swap），但能成功完成

## ⚠️ 注意事项

1. **Swap会影响性能**：使用swap时构建会变慢，但能避免OOM
2. **构建完成后可以保留swap**：对系统运行也有好处
3. **如果不需要可以删除**：
   ```bash
   sudo swapoff /swapfile
   sudo rm /swapfile
   sudo sed -i '/swapfile/d' /etc/fstab
   ```

## 🎯 一键执行（复制粘贴）

```bash
# 添加swap
sudo fallocate -l 4G /swapfile && \
sudo chmod 600 /swapfile && \
sudo mkswap /swapfile && \
sudo swapon /swapfile && \
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab && \
free -h

# 清理Docker
docker system prune -a -f

# 重新构建
docker build -t xiaozhi-esp32-server:server-base -f ./Dockerfile-server-base-optimized .
```









