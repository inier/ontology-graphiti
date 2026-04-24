# Graphiti 项目 Dockerfile

FROM python:3.10-slim

WORKDIR /app

# 先复制项目所有文件
COPY . .

# 安装Python依赖（先安装除openharness外的其他依赖）
RUN pip install --no-cache-dir \
    graphiti-core>=0.28.0 \
    neo4j>=5.0.0 \
    networkx>=2.8.0 \
    opa-python \
    flask \
    fastapi \
    uvicorn \
    pandas \
    numpy \
    requests \
    beautifulsoup4 \
    python-dateutil \
    jsonpickle \
    pydantic>=2.0.0 \
    httpx>=0.25.0 \
    redis>=5.0.0 \
    "python-jose[cryptography]>=3.3.0" \
    python-multipart>=0.0.6 \
    pymongo \
    pytest>=8.0.0 \
    black>=23.0.0 \
    flake8>=6.1.0

# 安装本地的 openharness（跳过 requirements.txt）
RUN pip install --no-cache-dir ./openharness

# 暴露端口
EXPOSE 8000

# 运行应用
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]