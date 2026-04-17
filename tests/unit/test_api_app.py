import importlib
from datetime import datetime, timezone

from markbridge.api.models import RepairCandidateResponse, runtime_status_from_domain, s3_object_option_from_domain
from markbridge.api.storage import S3ObjectOption
from markbridge.routing.runtime import RuntimeParserStatus
from markbridge.shared.ir import DocumentFormat

app_module = importlib.import_module("markbridge.api.app")


def test_create_app_registers_ui_relevant_routes() -> None:
    app = app_module.create_app()
    routes = {route.path for route in app.routes}

    assert "/health" in routes
    assert "/v1/runtime-status" in routes
    assert "/v1/s3/buckets" in routes
    assert "/v1/s3/objects" in routes
    assert "/v1/parse/upload" in routes
    assert "/v1/parse/s3" in routes
    assert "/exports/parse-markdown" in routes
    assert "/exports/parse-markdown/{document_id}/content" in routes
    assert "/exports/parse-markdown/{document_id}/blocks" in routes
    assert "/exports/parse-markdown/{document_id}/blocks/{block_id}/content" in routes


def test_s3_object_option_serialization_is_ui_ready() -> None:
    item = S3ObjectOption(
        bucket="demo-bucket",
        key="incoming/sample-policy.pdf",
        size_bytes=2048,
        updated_at=datetime(2026, 4, 3, 8, 20, tzinfo=timezone.utc),
    )

    response = s3_object_option_from_domain(item)

    dumped = response.model_dump(mode="json")
    assert dumped["label"] == "sample-policy.pdf"
    assert dumped["s3_uri"] == "s3://demo-bucket/incoming/sample-policy.pdf"
    assert dumped["document_format"] == DocumentFormat.PDF.value


def test_repair_candidate_serialization_is_ui_ready() -> None:
    response = RepairCandidateResponse(
        issue_id="issue-1",
        repair_type="formula_reconstruction",
        strategy="deterministic_transliteration_with_llm_review",
        origin="deterministic",
        source_text="1.3. 해지율(      )에 관한 사항",
        source_span="",
        candidate_text="1.3. 해지율( q x + t l )에 관한 사항",
        normalized_math="q_{x+t} l",
        confidence=0.5,
        rationale="Formula-like corruption requires review.",
        requires_review=True,
        llm_recommended=True,
        block_ref="block-13",
        markdown_line_number=41,
        location_hint="block 13",
        severity="warning",
        patch_proposal={
            "action": "replace_text",
            "target_text": "1.3. 해지율(      )에 관한 사항",
            "replacement_text": "1.3. 해지율( q x + t l )에 관한 사항",
            "block_ref": "block-13",
            "location_hint": "block 13",
            "markdown_line_number": 41,
            "confidence": 0.5,
            "rationale": "Formula-like corruption requires review.",
            "uncertain": True,
        },
    )

    dumped = response.model_dump(mode="json")
    assert dumped["repair_type"] == "formula_reconstruction"
    assert dumped["normalized_math"] == "q_{x+t} l"
    assert dumped["llm_recommended"] is True
    assert dumped["patch_proposal"]["markdown_line_number"] == 41


def test_runtime_status_serialization_exposes_route_metadata() -> None:
    response = runtime_status_from_domain(
        RuntimeParserStatus(
            parser_id="antiword",
            installed=True,
            enabled=True,
            reason=None,
            supported_formats=(DocumentFormat.DOC,),
            route_kind="degraded_fallback",
        )
    )

    dumped = response.model_dump(mode="json")
    assert dumped["parser_id"] == "antiword"
    assert dumped["supported_formats"] == ["doc"]
    assert dumped["route_kind"] == "degraded_fallback"
