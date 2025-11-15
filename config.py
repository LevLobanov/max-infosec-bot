from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    MAX_BOT_TOKEN: str = Field(default=...)
    VIRUSTOTAL_API_TOKEN: str = Field(default=...)
    LEAKLOOKUP_PUBLIC_KEY: str = Field(default=...)

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
