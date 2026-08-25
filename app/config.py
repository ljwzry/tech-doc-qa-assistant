import os
from dotenv import load_dotenv
load_dotenv()

class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "deepseek")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    # 默认使用 SiliconFlow 中转平台（国内可访问、性价比高），若需使用 DeepSeek 官方请在 .env 中覆盖
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.siliconflow.cn/v1")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3")
    # 默认使用 BGE-small-zh，适合纯 CPU 环境（约100MB，速度快）
    # 如有 GPU 可改为 BAAI/bge-m3（约2GB，效果更好）
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh")
    embedding_device: str = os.getenv("EMBEDDING_DEVICE", "cpu")
    # CPU 线程数，充分利用多核 CPU
    embedding_threads: int = int(os.getenv("EMBEDDING_THREADS", "8"))
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
    upload_dir: str = os.getenv("UPLOAD_DIR", "./data/docs")
    max_file_size: str = os.getenv("MAX_FILE_SIZE", "50MB")  # 支持 '50MB', '1GB' 等格式
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    # API 鉴权配置（生产环境建议启用）
    auth_enabled: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    api_key: str = os.getenv("API_KEY", "")

settings = Settings()