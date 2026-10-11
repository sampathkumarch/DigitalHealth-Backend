from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Health Backend"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    public_base_url: str = "http://127.0.0.1:8000"

    database_url: str = "postgresql+psycopg://health:health@127.0.0.1:5432/health"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle_seconds: int = 1800
    # True when DATABASE_URL points at PgBouncer in transaction mode.
    db_pgbouncer: bool = False

    redis_url: str = "redis://127.0.0.1:6379/0"

    jwt_secret: str = "change-me"
    jwt_access_ttl_seconds: int = 900
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 30
    otp_pepper: str = "change-me-otp"
    otp_ttl_seconds: int = 300
    otp_length: int = 6
    otp_max_attempts: int = 5
    otp_resend_seconds: int = 30
    otp_send_limit: int = 5
    otp_send_window_seconds: int = 900
    otp_verify_limit: int = 10
    # Local testing only. Production keeps the code hashed and off the response.
    otp_store_plaintext: bool = False
    otp_expose_in_response: bool = False

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    s3_bucket: str = ""
    s3_key_prefix: str = ""
    s3_endpoint_url: str = ""
    s3_presign_ttl_seconds: int = 900
    local_storage_dir: str = "var/uploads"
    max_upload_bytes: int = 5 * 1024 * 1024

    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_template_name: str = "otp"
    whatsapp_template_language: str = "en"
    whatsapp_api_version: str = "v21.0"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
