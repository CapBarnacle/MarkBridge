"""Guarded Azure OpenAI helpers for routing and repair advice."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from openai import AzureOpenAI

from markbridge.api.config import ApiSettings


@dataclass(frozen=True, slots=True)
class LlmAdvice:
    used: bool
    recommendation: str | None = None
    rationale: tuple[str, ...] = ()
    repair_plan: tuple[str, ...] = ()
    raw: dict[str, Any] | None = None
    error: str | None = None


class AzureLlmAdvisor:
    def __init__(self, settings: ApiSettings) -> None:
        self._settings = settings
        self._client = AzureOpenAI(
            api_key=settings.azure_api_key,
            azure_endpoint=settings.azure_endpoint,
            api_version=settings.azure_api_version,
            timeout=settings.llm_timeout_seconds,
        )

    @property
    def available(self) -> bool:
        return self._settings.llm_configured

    def recommend_routing(self, *, prompt: str, max_output_tokens: int | None = None) -> LlmAdvice:
        return self._call_json_model(
            system_message=(
                "You are a document routing assistant for a life-insurance CRM parsing pipeline. "
                "Return compact JSON only."
            ),
            user_message=prompt,
            max_output_tokens=max_output_tokens or self._settings.llm_max_output_tokens,
        )

    def recommend_repair(self, *, prompt: str, max_output_tokens: int | None = None) -> LlmAdvice:
        return self._call_json_model(
            system_message=(
                "You are a document repair assistant for a life-insurance CRM parsing pipeline. "
                "Return compact JSON only."
            ),
            user_message=prompt,
            max_output_tokens=max_output_tokens or self._settings.llm_max_output_tokens,
        )

    def recommend_formula_from_image(
        self,
        *,
        prompt: str,
        image_bytes: bytes,
        image_mime_type: str = "image/png",
        max_output_tokens: int | None = None,
    ) -> LlmAdvice:
        image_url = f"data:{image_mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        return self._call_json_model_with_content(
            system_message=(
                "You are a document repair assistant for a life-insurance CRM parsing pipeline. "
                "Use the supplied page image to reconstruct one formula placeholder. Return compact JSON only."
            ),
            user_content=[
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": image_url},
            ],
            max_output_tokens=max_output_tokens or self._settings.llm_max_output_tokens,
        )

    def _call_json_model(self, *, system_message: str, user_message: str, max_output_tokens: int) -> LlmAdvice:
        return self._call_json_model_with_content(
            system_message=system_message,
            user_content=[{"type": "input_text", "text": user_message}],
            max_output_tokens=max_output_tokens,
        )

    def _call_json_model_with_content(
        self,
        *,
        system_message: str,
        user_content: list[dict[str, Any]],
        max_output_tokens: int,
    ) -> LlmAdvice:
        try:
            response = self._client.responses.create(
                model=self._settings.azure_model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": system_message}]},
                    {"role": "user", "content": user_content},
                ],
                max_output_tokens=max_output_tokens,
            )
            text = getattr(response, "output_text", "") or ""
            try:
                parsed = json.loads(text) if text else {}
            except Exception as exc:
                return LlmAdvice(
                    used=False,
                    raw={"_raw_text": text} if text else None,
                    error=str(exc),
                )
            recommendation = parsed.get("recommendation") or parsed.get("primary_parser")
            rationale = parsed.get("rationale") or []
            repair_plan = parsed.get("repair_plan") or []
            return LlmAdvice(
                used=True,
                recommendation=recommendation,
                rationale=tuple(str(item) for item in rationale),
                repair_plan=tuple(str(item) for item in repair_plan),
                raw=parsed,
            )
        except Exception as exc:
            return LlmAdvice(used=False, error=str(exc))
