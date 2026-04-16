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


def libreoffice_available() -> bool:
    return shutil.which("libreoffice") is not None or shutil.which("soffice") is not None


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
