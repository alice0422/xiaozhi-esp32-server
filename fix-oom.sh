#!/bin/bash

echo "========================================"
echo "修复OOM问题 - 添加Swap空间"
echo "========================================"

# 检查是否已有swap
if swapon --show | grep -q .; then
    echo "⚠️  检测到已有swap空间："
    swapon --show
    read -p "是否继续添加新的swap？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 创建4GB swap文件（根据你的14GB内存，4GB swap应该足够）
echo ""
echo "[1/5] 创建4GB swap文件..."
sudo fallocate -l 4G /swapfile
if [ $? -ne 0 ]; then
    echo "⚠️  fallocate失败，尝试使用dd方式..."
    sudo dd if=/dev/zero of=/swapfile bs=1M count=4096
fi

# 设置权限
echo "[2/5] 设置swap文件权限..."
sudo chmod 600 /swapfile

# 格式化为swap
echo "[3/5] 格式化swap文件..."
sudo mkswap /swapfile

# 启用swap
echo "[4/5] 启用swap..."
sudo swapon /swapfile

# 永久启用（重启后仍然有效）
echo "[5/5] 配置永久启用..."
if ! grep -q "/swapfile" /etc/fstab; then
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# 验证
echo ""
echo "========================================"
echo "✅ Swap空间已添加！"
echo "========================================"
echo ""
echo "当前内存和swap状态："
free -h
echo ""
echo "Swap文件信息："
swapon --show
echo ""
echo "💡 现在可以重新运行构建脚本了！"
echo "   ./build-local.sh"









