"""Azure OpenAI integration scaffolding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from markbridge.config import AzureOpenAISettings


@dataclass(frozen=True, slots=True)
class RoutingPromptInput:
    """Small routing payload sent to the LLM when deterministic routing is ambiguous."""

    document_format: str
    feature_summary: str
    candidate_parsers: tuple[str, ...]
    cost_guardrail: str = "Prefer the smallest sufficient recommendation. Do not request full document text."


class AzureResponsesClient:
    """Minimal Azure OpenAI Responses API client wrapper."""

    def __init__(self, settings: AzureOpenAISettings) -> None:
        if not settings.configured:
            raise ValueError("Azure OpenAI settings are not fully configured.")
        self._settings = settings
        self._client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.endpoint,
        )

    def respond(self, input_text: str, *, metadata: dict[str, Any] | None = None) -> Any:
        return self._client.responses.create(
            model=self._settings.model,
            input=input_text,
            metadata=metadata or {},
        )


class AzureOpenAILLMRouter:
    """LLM-assisted routing helper with cost guardrails."""

    def __init__(self, client: AzureResponsesClient) -> None:
        self._client = client

    def recommend_parser(self, prompt: RoutingPromptInput) -> Any:
        candidate_text = ", ".join(prompt.candidate_parsers)
        input_text = (
            "You are selecting a parser route for MarkBridge.\n"
            f"Document format: {prompt.document_format}\n"
            f"Feature summary: {prompt.feature_summary}\n"
            f"Executable candidates: {candidate_text}\n"
            f"Guardrail: {prompt.cost_guardrail}\n"
            "Return the recommended parser id and a short rationale."
        )
        return self._client.respond(
            input_text,
            metadata={"purpose": "parser_routing"},
        )
