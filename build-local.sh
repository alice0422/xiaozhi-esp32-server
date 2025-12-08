#!/bin/bash

echo "========================================"
echo "开始构建Docker镜像（本地版本）"
echo "========================================"

echo ""
echo "[1/3] 构建server-base镜像（这可能需要10-30分钟）..."
echo "💡 使用优化版Dockerfile（分批安装，减少内存占用）..."
docker build -t xiaozhi-esp32-server:server-base -f ./Dockerfile-server-base-optimized .
if [ $? -ne 0 ]; then
    echo "❌ 构建server-base失败！"
    exit 1
fi
echo "✅ server-base镜像构建完成"

echo ""
echo "[2/3] 构建server镜像..."
docker build -t xiaozhi-esp32-server:server_latest -f ./Dockerfile-server-local .
if [ $? -ne 0 ]; then
    echo "❌ 构建server失败！"
    exit 1
fi
echo "✅ server镜像构建完成"

echo ""
echo "[3/3] 构建web镜像（这可能需要5-15分钟）..."
docker build -t xiaozhi-esp32-server:web_latest -f ./Dockerfile-web .
if [ $? -ne 0 ]; then
    echo "❌ 构建web失败！"
    exit 1
fi
echo "✅ web镜像构建完成"

echo ""
echo "========================================"
echo "✅ 所有镜像构建完成！"
echo "========================================"
echo ""
echo "📦 镜像列表："
docker images | grep xiaozhi-esp32-server
echo ""
echo "📝 下一步："
echo "1. 修改 main/xiaozhi-server/docker-compose_all.yml"
echo "   将镜像名改为本地镜像名"
echo "2. 运行: cd main/xiaozhi-server && docker-compose -f docker-compose_all.yml up -d"
echo ""




