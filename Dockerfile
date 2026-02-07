FROM python:3.9-slim

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装基础依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY api/akshare_api.py .

# 暴露端口
EXPOSE 8080

# 启动命令 (适配 Cloud Run, 监听 0.0.0.0:8080)
CMD ["uvicorn", "akshare_api:app", "--host", "0.0.0.0", "--port", "8080"]
