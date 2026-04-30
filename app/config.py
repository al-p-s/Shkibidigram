from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # App
    app_secret_key: str
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Database
    database_url: str

    # Redis
    redis_url: str

    # MinIO
    minio_endpoint: str
    minio_root_user: str
    minio_root_password: str
    minio_bucket_media: str = "media"
    minio_bucket_avatars: str = "avatars"

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30


settings = Settings()
