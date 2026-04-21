#!/bin/bash

# Graphiti 项目一键停止脚本
# 停止所有服务
echo "🔄 Graphiti 项目一键停止脚本"
echo "================================="

# 停止后端服务
echo "\n🛑 停止后端服务..."
cd docker && docker compose down

# 检查服务状态
echo "\n📋 检查服务状态..."
docker compose ps

# 清理 Docker 网络和卷
echo "\n🧹 清理 Docker 资源..."
docker network prune -f 2>/dev/null || true
docker volume prune -f 2>/dev/null || true

echo "\n✅ 所有服务已停止"
echo "================================="
echo "服务已全部停止，资源已清理"