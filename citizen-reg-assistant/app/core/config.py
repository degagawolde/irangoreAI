from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Citizen Regulation Assistant"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Gemini
    GEMINI_API_KEY: str
    GEMINI_LLM_MODEL: str = "models/gemini-2.5-flash"
    GEMINI_EMBED_MODEL: str = "models/gemini-embedding-2"

    # Database
    DATABASE_URL: str

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()