"""FastAPI surface for MarkBridge."""

from __future__ import annotations

def __getattr__(name: str):
    if name == "app":
        from .app import create_app

        return create_app()
    if name == "create_app":
        from .app import create_app

        return create_app
    raise AttributeError(name)


__all__ = ["app", "create_app"]
