#!/bin/bash

# Graphiti 项目一键启动脚本
# 同时启动后端API和前端服务

echo "🔄 Graphiti 项目一键启动脚本"
echo "================================="

echo "📁 检查项目目录"
if [ ! -f "docker/docker-compose.yml" ]; then
    echo "❌ 错误：未找到 docker-compose.yml 文件"
    echo "请确保在项目根目录运行此脚本"
    exit 1
fi

# 启动后端服务
echo "\n🚀 启动后端服务..."
echo "启动 Docker 容器：API、Neo4j、OPA、Redis"
cd docker && docker compose up -d

# 等待后端服务启动
echo "\n⏳ 等待后端服务启动..."
sleep 10

# 检查后端服务状态
echo "\n📋 检查后端服务状态..."
docker compose ps

# 检查 API 健康状态
echo "\n🌡️  检查 API 健康状态..."
curl -s http://localhost:8001/health

# 检查 OPA 健康状态
echo "\n🛡️  检查 OPA 服务状态..."
curl -s http://localhost:8181/health

# 检查 Redis 状态
echo "\n🔄 检查 Redis 状态..."
docker exec graphiti-cache redis-cli ping

# 启动前端服务
echo "\n🖥️  启动前端服务..."
echo "进入前端目录并启动开发服务器"
cd .. && cd frontend

# 检查前端依赖
echo "\n📦 检查前端依赖..."
if [ ! -f "node_modules/.bin/vite" ]; then
    echo "安装前端依赖..."
    npm install
fi

# 启动前端开发服务器
echo "\n🚀 启动前端开发服务器..."
echo "前端服务将在 http://localhost:5173 启动"
echo "按 Ctrl+C 停止服务"
npm run dev