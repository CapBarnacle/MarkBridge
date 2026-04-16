"""Runtime configuration for the MarkBridge API surface."""

from __future__ import annotations

from dataclasses import dataclass
import os

from markbridge.env import load_dotenv_file


load_dotenv_file()


@dataclass(frozen=True, slots=True)
class ApiSettings:
    azure_endpoint: str | None = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_api_key: str | None = os.getenv("AZURE_OPENAI_API_KEY")
    azure_model: str = os.getenv("AZURE_OPENAI_MODEL", "gpt-5.2")
    azure_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
    aws_region: str | None = os.getenv("AWS_REGION")
    enable_llm_routing: bool = os.getenv("MARKBRIDGE_ENABLE_LLM_ROUTING", "true").lower() in {"1", "true", "yes"}
    llm_max_output_tokens: int = int(os.getenv("MARKBRIDGE_LLM_MAX_OUTPUT_TOKENS", "256"))
    llm_max_input_chars: int = int(os.getenv("MARKBRIDGE_LLM_MAX_INPUT_CHARS", "6000"))
    llm_timeout_seconds: int = int(os.getenv("MARKBRIDGE_LLM_TIMEOUT_SECONDS", "30"))
    default_tmp_dir: str = os.getenv("MARKBRIDGE_TMP_DIR", "/tmp")
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "MARKBRIDGE_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    )

    @property
    def llm_configured(self) -> bool:
        return bool(self.azure_endpoint and self.azure_api_key and self.azure_model)


def get_settings() -> ApiSettings:
    return ApiSettings()
