from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ollama Configuration
    ollama_url: str = "http://localhost:11434"
    model_name: str = "qwen2.5:7b"
    
    # Embedding Configuration
    embedding_model_name: str = "all-MiniLM-L6-v2"
    
    # Database Configuration
    chroma_db_path: Path = Path("./data/chroma")
    sqlite_path: Path = Path("./data/graphmem.db")
    
    # Thresholds
    retrieval_confidence_threshold: float = 0.7
    memory_consolidation_threshold: float = 0.5
    
    # General API / System settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Environment variables configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

# Global instance for easy import
settings = Settings()
