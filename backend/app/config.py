from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "TrustRAG"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = "postgresql+asyncpg://trustrag:trustrag@localhost:5432/trustrag"
    DATABASE_SYNC_URL: str = "postgresql://trustrag:trustrag@localhost:5432/trustrag"

    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333

    REDIS_URL: str = "redis://localhost:6379/0"

    OPENAI_API_KEY: str = ""
    COHERE_API_KEY: str = ""

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    LLM_MODEL: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.1
    RERANK_MODEL: str = "rerank-v3.5"

    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    CONTEXT_TOKEN_BUDGET: int = 4000
    RETRIEVAL_TOP_K: int = 50
    RERANK_TOP_K: int = 10

    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    RATE_LIMIT_PER_MINUTE: int = 60

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
