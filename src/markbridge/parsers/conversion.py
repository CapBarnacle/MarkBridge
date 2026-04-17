"""Legacy document conversion helpers."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ConversionResult:
    succeeded: bool
    output_path: Path | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class TextExtractionResult:
    succeeded: bool
    text: str | None = None
    message: str | None = None


def libreoffice_available() -> bool:
    return shutil.which("libreoffice") is not None or shutil.which("soffice") is not None


def antiword_available() -> bool:
    return shutil.which("antiword") is not None


def hwp5txt_available() -> bool:
    return shutil.which("hwp5txt") is not None


def convert_doc_to_docx(source_path: Path, output_dir: Path) -> ConversionResult:
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if executable is None:
        return ConversionResult(
            succeeded=False,
            message="LibreOffice conversion command is not available in the current environment.",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        executable,
        "--headless",
        "--convert-to",
        "docx",
        "--outdir",
        str(output_dir),
        str(source_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    target = output_dir / f"{source_path.stem}.docx"
    if completed.returncode != 0 or not target.exists():
        message = completed.stderr.strip() or completed.stdout.strip() or "DOC to DOCX conversion failed."
        return ConversionResult(succeeded=False, message=message)

    return ConversionResult(succeeded=True, output_path=target, message="DOC converted to DOCX.")


def extract_doc_text_with_antiword(source_path: Path) -> TextExtractionResult:
    executable = shutil.which("antiword")
    if executable is None:
        return TextExtractionResult(
            succeeded=False,
            message="antiword command is not available in the current environment.",
        )

    completed = subprocess.run(
        [executable, str(source_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    text = completed.stdout.strip()
    if completed.returncode != 0 or not text:
        message = completed.stderr.strip() or completed.stdout.strip() or "antiword text extraction failed."
        return TextExtractionResult(succeeded=False, message=message)
    return TextExtractionResult(
        succeeded=True,
        text=text,
        message="DOC extracted with antiword text fallback.",
    )


def extract_hwp_text_with_hwp5txt(source_path: Path) -> TextExtractionResult:
    executable = shutil.which("hwp5txt")
    if executable is None:
        return TextExtractionResult(
            succeeded=False,
            message="hwp5txt command is not available in the current environment.",
        )

    completed = subprocess.run(
        [executable, str(source_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    text = completed.stdout.strip()
    if completed.returncode != 0 or not text:
        message = completed.stderr.strip() or completed.stdout.strip() or "hwp5txt text extraction failed."
        return TextExtractionResult(succeeded=False, message=message)
    return TextExtractionResult(
        succeeded=True,
        text=text,
        message="HWP extracted with hwp5txt text route.",
    )
