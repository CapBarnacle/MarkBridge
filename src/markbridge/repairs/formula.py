"""Repair candidate generation for corrupted mathematical notation."""

from __future__ import annotations

from dataclasses import dataclass
import re

from markbridge.tracing.model import IssueSeverity
from markbridge.validators.model import ValidationIssue


PRIVATE_USE_TRANSLITERATION = {
    "": "i",
    "": "q",
    "": "x",
    "": "t",
    "": "m",
    "": "n",
    "": "l",
    "": "I",
    "": "J",
    "": "R",
    "": "S",
    "": "P",
    "": "F",
    "": "B",
    "": "W",
    "": "1",
    "": "2",
    "": "3",
    "": "4",
    "": "5",
    "": "6",
    "": "7",
    "": "8",
    "": "9",
    "": "0",
    "": "+",
    "": "-",
    "": "%",
    "": "=",
    "": "|",
    "": ",",
    "": ".",
    "": "/",
    "": "(",
    "": ")",
    "": "frac",
    "": "alpha",
    "": "beta",
    "": "theta",
}

TRAILING_SUPERSCRIPT_TOKENS = {
    "l": "L",
    "i": "I",
    "j": "J",
    "m": "M",
    "n": "N",
    "s": "S",
}


@dataclass(frozen=True, slots=True)
class RepairPatchProposal:
    action: str
    target_text: str
    replacement_text: str
    block_ref: str | None = None
    location_hint: str | None = None
    markdown_line_number: int | None = None
    confidence: float = 0.0
    rationale: str = ""
    uncertain: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "target_text": self.target_text,
            "replacement_text": self.replacement_text,
            "block_ref": self.block_ref,
            "location_hint": self.location_hint,
            "markdown_line_number": self.markdown_line_number,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "uncertain": self.uncertain,
        }


@dataclass(frozen=True, slots=True)
class RepairCandidate:
    issue_id: str
    repair_type: str
    strategy: str
    origin: str
    source_text: str
    source_span: str | None
    candidate_text: str | None
    normalized_math: str | None
    confidence: float
    rationale: str
    requires_review: bool = True
    llm_recommended: bool = True
    block_ref: str | None = None
    markdown_line_number: int | None = None
    location_hint: str | None = None
    severity: str = "warning"
    patch_proposal: RepairPatchProposal | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "issue_id": self.issue_id,
            "repair_type": self.repair_type,
            "strategy": self.strategy,
            "origin": self.origin,
            "source_text": self.source_text,
            "source_span": self.source_span,
            "candidate_text": self.candidate_text,
            "normalized_math": self.normalized_math,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "requires_review": self.requires_review,
            "llm_recommended": self.llm_recommended,
            "block_ref": self.block_ref,
            "markdown_line_number": self.markdown_line_number,
            "location_hint": self.location_hint,
            "severity": self.severity,
            "patch_proposal": self.patch_proposal.as_dict() if self.patch_proposal else None,
        }


def generate_repair_candidates(issues: tuple[ValidationIssue, ...]) -> tuple[RepairCandidate, ...]:
    candidates: list[RepairCandidate] = []
    for issue in issues:
        if issue.code.value != "text_corruption" or not issue.excerpts:
            continue
        corruption_class = str(issue.details.get("corruption_class", ""))
        if corruption_class not in {
            "inline_formula_corruption",
            "table_formula_corruption",
            "formula_placeholder",
            "structure_loss",
        }:
            continue
        candidate = _build_formula_candidate(issue, corruption_class=corruption_class)
        if candidate is not None:
            candidates.append(candidate)
    return tuple(candidates)


def _build_formula_candidate(issue: ValidationIssue, *, corruption_class: str) -> RepairCandidate | None:
    excerpt = issue.excerpts[0]
    source_text = excerpt.content
    source_span = excerpt.highlight_text or None
    location_hint = excerpt.location_hint
    block_ref = issue.location.block_ref if issue.location else None

    if corruption_class == "formula_placeholder":
        return RepairCandidate(
            issue_id=issue.issue_id,
            repair_type="formula_reconstruction",
            strategy="llm_required",
            origin="deterministic",
            source_text=source_text,
            source_span=source_span,
            candidate_text=None,
            normalized_math=None,
            confidence=0.05,
            rationale="The parser emitted a formula placeholder instead of recoverable symbols. This requires context-aware formula reconstruction, likely via LLM or source review.",
            block_ref=block_ref,
            location_hint=location_hint,
            severity=issue.severity.value if isinstance(issue.severity, IssueSeverity) else str(issue.severity),
        )

    transliterated_text = _transliterate_private_use(source_text)
    if transliterated_text == source_text and not source_span:
        return None

    heuristic_text = _apply_formula_heuristics(transliterated_text, corruption_class=corruption_class)
    math_span = _extract_formula_span(
        heuristic_text,
        fallback_span=_transliterate_private_use(source_span or "") or None,
    )
    normalized_math = _normalize_formula_span(math_span) if math_span else None
    strategy = "deterministic_transliteration_with_llm_review"
    confidence = 0.35 if corruption_class == "table_formula_corruption" else 0.4
    if normalized_math and normalized_math.count(" ") <= 3:
        confidence += 0.1
    if normalized_math and ("_" in normalized_math or "^" in normalized_math):
        confidence += 0.1
    if heuristic_text != transliterated_text:
        confidence += 0.1
    confidence = min(confidence, 0.65)
    llm_recommended = _should_escalate_to_llm(
        corruption_class=corruption_class,
        normalized_math=normalized_math,
        confidence=confidence,
        candidate_text=heuristic_text,
    )
    rationale = _build_rationale(
        corruption_class,
        normalized_math=normalized_math,
        llm_recommended=llm_recommended,
    )

    return RepairCandidate(
        issue_id=issue.issue_id,
        repair_type="formula_reconstruction",
        strategy=strategy,
        origin="deterministic",
        source_text=source_text,
        source_span=source_span,
        candidate_text=heuristic_text,
        normalized_math=normalized_math,
        confidence=confidence,
        rationale=rationale,
        llm_recommended=llm_recommended,
        block_ref=block_ref,
        location_hint=location_hint,
        severity=issue.severity.value if isinstance(issue.severity, IssueSeverity) else str(issue.severity),
        patch_proposal=RepairPatchProposal(
            action="replace_text",
            target_text=source_text,
            replacement_text=heuristic_text,
            block_ref=block_ref,
            location_hint=location_hint,
            confidence=confidence,
            rationale=rationale,
            uncertain=llm_recommended,
        ),
    )


def _transliterate_private_use(text: str) -> str:
    translated = "".join(PRIVATE_USE_TRANSLITERATION.get(character, character) for character in text)
    translated = re.sub(r"\s+", " ", translated).strip()
    return translated


def _extract_formula_span(text: str, *, fallback_span: str | None = None) -> str | None:
    if not text:
        return None
    paren_match = re.search(r"\(([^()]+)\)", text)
    if paren_match:
        content = paren_match.group(1).strip()
        if not _contains_hangul(content):
            return content
    table_match = re.match(r"^\|([^|]+)\|", text.strip())
    if table_match:
        return table_match.group(1).strip()
    if text.startswith("<!-- formula-not-decoded -->"):
        return None
    stripped = text.strip()
    if fallback_span and _contains_hangul(stripped):
        return fallback_span
    if fallback_span and stripped in {"", fallback_span}:
        return fallback_span
    return stripped


def _normalize_formula_span(text: str | None) -> str | None:
    if not text:
        return None
    value = text
    value = re.sub(r"\bfrac\b", "/", value)
    value = re.sub(r"\s*\+\s*", " + ", value)
    value = re.sub(r"\s*-\s*", " - ", value)
    value = re.sub(r"\s*=\s*", " = ", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = _rewrite_formula_token(value)
    value = value.replace("l x+t", "l_{x+t}")
    value = value.replace("l x + t", "l_{x+t}")
    return value


def _apply_formula_heuristics(text: str, *, corruption_class: str) -> str:
    if not text:
        return text
    if corruption_class == "table_formula_corruption":
        return _rewrite_formula_token(text)

    def replace_paren(match: re.Match[str]) -> str:
        content = match.group(1)
        if _contains_hangul(content):
            return match.group(0)
        rewritten = _rewrite_formula_token(content)
        return f"({rewritten})"

    rewritten = re.sub(r"\(([^()]+)\)", replace_paren, text)
    if rewritten == text:
        return _rewrite_formula_token(text)
    return rewritten


def _rewrite_formula_token(text: str) -> str:
    value = re.sub(r"\s*\+\s*", "+", text)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\b([qplamAnAP])\s*x\+t\s+([A-Za-z])\b", _rewrite_subscript_with_superscript, value)
    value = re.sub(r"\b([qplamAnAP])\s*x\s*\+\s*t\s+([A-Za-z])\b", _rewrite_subscript_with_superscript, value)
    value = re.sub(r"\b([qplamAnAP])\s*x\+t\b", lambda match: f"{match.group(1)}_{{x+t}}", value)
    value = re.sub(r"\b([qplamAnAP])\s*x\s*\+\s*t\b", lambda match: f"{match.group(1)}_{{x+t}}", value)
    return value


def _rewrite_subscript_with_superscript(match: re.Match[str]) -> str:
    base = match.group(1)
    tail = match.group(2)
    superscript = TRAILING_SUPERSCRIPT_TOKENS.get(tail.lower(), tail.upper() if len(tail) == 1 else tail)
    return f"{base}_{{x+t}}^{{{superscript}}}"


def _contains_hangul(text: str) -> bool:
    return any("\uac00" <= character <= "\ud7a3" for character in text)


def _should_escalate_to_llm(
    *,
    corruption_class: str,
    normalized_math: str | None,
    confidence: float,
    candidate_text: str,
) -> bool:
    if corruption_class in {"formula_placeholder", "structure_loss"}:
        return True
    if not normalized_math:
        return True
    if confidence < 0.6:
        return True
    if "_" in normalized_math or "^" in normalized_math:
        return False
    if candidate_text == normalized_math and re.fullmatch(r"[A-Za-z0-9_{}^+\-=/().,% ]+", normalized_math):
        return confidence < 0.65
    return True


def _build_rationale(
    corruption_class: str,
    *,
    normalized_math: str | None,
    llm_recommended: bool,
) -> str:
    class_reason = {
        "inline_formula_corruption": "The corrupted span appears inside a formula-bearing line or heading, so the candidate is treated as inline actuarial notation.",
        "table_formula_corruption": "The corrupted span appears in a table row label, which usually carries compact actuarial formula notation.",
        "structure_loss": "The markdown contains broken symbols that likely represent a lost mathematical expression.",
    }.get(corruption_class, "The corrupted span appears formula-like.")
    if normalized_math:
        if llm_recommended:
            return f"{class_reason} A deterministic transliteration produced `{normalized_math}`, but it still needs review before replacement."
        return f"{class_reason} A deterministic transliteration produced `{normalized_math}` with enough structure to treat it as a strong reviewable baseline before invoking LLM."
    return f"{class_reason} No trustworthy deterministic reconstruction was available, so LLM review is recommended."
