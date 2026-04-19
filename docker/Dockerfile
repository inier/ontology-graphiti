# Graphiti 项目 Dockerfile

FROM python:3.10-slim

WORKDIR /app

# 跳过系统依赖安装（避免网络问题）

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 8000

# 运行应用
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]