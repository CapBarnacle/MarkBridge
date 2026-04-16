"""Runtime configuration for MarkBridge."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from markbridge.env import load_dotenv_file


load_dotenv_file()


@dataclass(frozen=True, slots=True)
class AzureOpenAISettings:
    """Azure OpenAI configuration loaded from environment variables."""

    endpoint: str | None = None
    api_key: str | None = None
    model: str | None = None
    api_version: str = "2025-04-01-preview"

    @property
    def configured(self) -> bool:
        return bool(self.endpoint and self.api_key and self.model)


@dataclass(frozen=True, slots=True)
class StorageSettings:
    """Storage-related settings."""

    work_dir: Path = field(default_factory=lambda: Path(os.getenv("MARKBRIDGE_WORK_DIR", "/tmp/markbridge")))
    s3_region: str | None = field(default_factory=lambda: os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"))


@dataclass(frozen=True, slots=True)
class MarkBridgeSettings:
    """Top-level settings container."""

    azure_openai: AzureOpenAISettings
    storage: StorageSettings


def load_settings() -> MarkBridgeSettings:
    return MarkBridgeSettings(
        azure_openai=AzureOpenAISettings(
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            model=os.getenv("AZURE_OPENAI_MODEL"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
        ),
        storage=StorageSettings(),
    )
