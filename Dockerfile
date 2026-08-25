FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/docs /app/data/chroma_db /app/data/model_cache

# 环境变量：指定 HuggingFace / sentence-transformers 缓存路径
ENV TRANSFORMERS_CACHE=/app/data/model_cache
ENV HF_HOME=/app/data/model_cache
ENV SENTENCE_TRANSFORMERS_HOME=/app/data/model_cache
ENV HF_HUB_CACHE=/app/data/model_cache

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]