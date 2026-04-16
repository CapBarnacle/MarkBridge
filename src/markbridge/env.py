"""Minimal .env loader for local development."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv_file(filename: str = ".env") -> None:
    """Populate missing environment variables from a project-local .env file."""

    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / filename
        if not candidate.exists() or not candidate.is_file():
            continue
        for raw_line in candidate.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)
        return
