"""Pipeline settings. Read fresh per call (tests change env at runtime)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class PipelineConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    # Absolute base used for image URLs in generated websites (the editor previews HTML via srcDoc).
    public_api_url: str = "http://localhost:8000"
    image_max_bytes: int = 5 * 1024 * 1024
    website_import_max_images: int = 8
    google_photo_max_bytes: int = 8 * 1024 * 1024


def pipeline_config() -> PipelineConfig:
    return PipelineConfig()
