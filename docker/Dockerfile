# Graphiti 项目 Dockerfile

FROM python:3.10-slim

WORKDIR /app

# 先复制项目所有文件（包括 openharness 子模块）
COPY . .

# 直接使用 requirements.txt 安装所有依赖（包括本地的 openharness）
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口
EXPOSE 8000

# 运行应用
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
