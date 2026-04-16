"""FastAPI application factory for MarkBridge."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from markbridge.api.config import get_settings
from markbridge.api.models import (
    HealthResponse,
    ParseMarkdownBlockListResponse,
    ParseMarkdownExportListResponse,
    ParseMarkdownExportStatus,
    ParseResponse,
    RuntimeStatusResponse,
    S3BucketListResponse,
    S3BucketOptionResponse,
    S3ObjectListResponse,
    S3ParseRequest,
    s3_object_option_from_domain,
)
from markbridge.api.service import MarkBridgePipeline
from markbridge.api.storage import list_s3_buckets, list_s3_objects
from markbridge.routing.runtime import get_runtime_statuses
from markbridge.api.models import runtime_status_from_domain


def _content_disposition_attachment(filename: str) -> str:
    safe_filename = "".join(char if ord(char) < 128 else "_" for char in Path(filename).name or "download.md")
    safe_filename = safe_filename.replace('"', "_").strip() or "download.md"
    encoded_filename = quote(Path(filename).name or "download.md")
    return f"attachment; filename=\"{safe_filename}\"; filename*=UTF-8''{encoded_filename}"


def create_app() -> FastAPI:
    settings = get_settings()
    pipeline = MarkBridgePipeline(settings)

    app = FastAPI(
        title="MarkBridge API",
        version="0.1.0",
        description="Backend-first parsing surface for source-faithful Markdown generation.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            llm_configured=settings.llm_configured,
            azure_model=settings.azure_model,
        )

    @app.get("/v1/runtime-status", response_model=RuntimeStatusResponse)
    def runtime_status() -> RuntimeStatusResponse:
        statuses = get_runtime_statuses()
        return RuntimeStatusResponse(
            parsers=[runtime_status_from_domain(status) for status in statuses.values()]
        )

    @app.get("/v1/s3/buckets", response_model=S3BucketListResponse)
    def s3_buckets() -> S3BucketListResponse:
        try:
            buckets = list_s3_buckets()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Unable to list S3 buckets: {exc}") from exc
        return S3BucketListResponse(
            buckets=[S3BucketOptionResponse(name=name, label=name) for name in buckets]
        )

    @app.get("/v1/s3/objects", response_model=S3ObjectListResponse)
    def s3_objects(
        bucket: str = Query(..., min_length=1),
        prefix: str = Query(""),
        limit: int = Query(100, ge=1, le=500),
    ) -> S3ObjectListResponse:
        try:
            objects = list_s3_objects(bucket=bucket, prefix=prefix, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Unable to list S3 objects: {exc}") from exc
        return S3ObjectListResponse(
            objects=[s3_object_option_from_domain(item) for item in objects]
        )

    @app.post("/v1/parse/upload", response_model=ParseResponse)
    async def parse_upload(
        file: UploadFile = File(...),
        llm_requested: bool = Form(False),
        parser_hint: str | None = Form(None),
    ) -> ParseResponse:
        content = await file.read()
        try:
            return pipeline.submit_local_upload(
                filename=file.filename or "upload.bin",
                content=content,
                content_type=file.content_type,
                llm_requested=llm_requested,
                parser_hint=parser_hint,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/v1/parse/s3", response_model=ParseResponse)
    def parse_s3(request: S3ParseRequest) -> ParseResponse:
        try:
            return pipeline.submit_s3_uri(
                s3_uri=request.s3_uri,
                llm_requested=request.llm_requested,
                parser_hint=request.parser_hint,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Unable to retrieve S3 source: {exc}") from exc

    @app.get("/exports/parse-markdown", response_model=ParseMarkdownExportListResponse)
    def list_parse_markdown_exports(
        updated_after: str | None = Query(None),
        limit: int = Query(100, ge=1, le=500),
        cursor: str | None = Query(None),
        parse_status: ParseMarkdownExportStatus | None = Query(None),
    ) -> ParseMarkdownExportListResponse:
        parsed_updated_after = None
        if updated_after:
            try:
                normalized = updated_after[:-1] + "+00:00" if updated_after.endswith("Z") else updated_after
                from datetime import datetime

                parsed_updated_after = datetime.fromisoformat(normalized)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid updated_after: {updated_after}") from exc
        return pipeline.list_parse_markdown_exports(
            updated_after=parsed_updated_after,
            limit=limit,
            cursor=cursor,
            parse_status=parse_status,
        )

    @app.get("/exports/parse-markdown/{document_id}/content")
    def get_parse_markdown_content(document_id: str) -> Response:
        try:
            document, content, etag = pipeline.get_parse_markdown_content(document_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        headers = {
            "Content-Disposition": _content_disposition_attachment(document.canonical_markdown_name),
            "ETag": etag,
        }
        if document.last_parse_completed_at is not None:
            headers["Last-Modified"] = document.last_parse_completed_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
        return Response(content=content, media_type="text/markdown; charset=utf-8", headers=headers)

    @app.get("/exports/parse-markdown/{document_id}/blocks", response_model=ParseMarkdownBlockListResponse)
    def list_parse_markdown_blocks(document_id: str) -> ParseMarkdownBlockListResponse:
        try:
            return pipeline.list_parse_markdown_blocks(document_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/exports/parse-markdown/{document_id}/blocks/{block_id}/content")
    def get_parse_markdown_block_content(document_id: str, block_id: str) -> Response:
        try:
            document, content, etag = pipeline.get_parse_markdown_block_content(document_id, block_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        headers = {
            "Content-Disposition": _content_disposition_attachment(f"{document.document_id}-{block_id}.md"),
            "ETag": etag,
        }
        if document.last_parse_completed_at is not None:
            headers["Last-Modified"] = document.last_parse_completed_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
        return Response(content=content, media_type="text/markdown; charset=utf-8", headers=headers)

    return app
