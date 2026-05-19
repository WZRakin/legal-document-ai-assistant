from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None


MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")


def _gemini_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key or genai is None:
        return None
    return genai.Client(api_key=key)


def _safe_json(text: str) -> Dict[str, Any]:
    """Parse model JSON safely, including occasional markdown fenced JSON."""
    if not text:
        return {}

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except Exception:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except Exception:
                pass

    return {
        "raw_model_output": text,
        "parse_warning": "Model did not return valid JSON."
    }


def _generate_text(prompt: str, expect_json: bool = False) -> str:
    client = _gemini_client()

    if client is None:
        raise RuntimeError("GEMINI_API_KEY is not configured or google-genai is not installed.")

    config = None
    if types is not None:
        config = types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json" if expect_json else "text/plain",
        )

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=config,
    )

    return response.text or ""


def extract_structured_fields(full_text: str) -> Dict[str, Any]:
    """Return grounded JSON fields using Gemini when configured, otherwise a safe fallback."""

    if _gemini_client() is None:
        return _fallback_extract(full_text)

    prompt = f"""
You are a legal document extraction assistant.

Extract structured information from the document text below.

Rules:
- Use only facts clearly supported by the document text.
- Do not guess or invent facts.
- If a field is missing, return an empty array or write it in missing_information.
- Include evidence references using page labels or clause numbers when available.
- Return valid JSON only.
- Do not use markdown.
- Do not wrap the JSON in code fences.

Return exactly this JSON shape:
{{
  "document_type": "string",
  "parties": [{{"name": "string", "role": "string", "evidence": "string"}}],
  "key_dates": [{{"date": "string", "type": "string", "evidence": "string"}}],
  "obligations": [{{"party": "string", "obligation": "string", "evidence": "string"}}],
  "payment_terms": [{{"term": "string", "amount": "string", "deadline": "string", "evidence": "string"}}],
  "notice_requirements": [{{"requirement": "string", "evidence": "string"}}],
  "termination": [{{"right_or_condition": "string", "evidence": "string"}}],
  "governing_law": [{{"law_or_forum": "string", "evidence": "string"}}],
  "risks": [{{"risk": "string", "reason": "string", "evidence": "string"}}],
  "missing_information": ["string"]
}}

DOCUMENT TEXT:
{full_text[:45000]}
"""

    try:
        return _safe_json(_generate_text(prompt, expect_json=True))
    except Exception as exc:
        fallback = _fallback_extract(full_text)
        fallback["missing_information"] = [f"Gemini extraction failed: {exc}"]
        return fallback


def generate_grounded_memo(extracted: Dict[str, Any], evidence: List[dict]) -> str:
    evidence_text = "\n\n".join([
        f"[Page {e['page']} | {e['chunk_id']} | score {e.get('score')}]\n{e['text']}"
        for e in evidence
    ])

    if _gemini_client() is None:
        return _fallback_memo(extracted, evidence)

    prompt = f"""
You are drafting a first-pass internal legal-style memo for operator review.

Use ONLY the extracted JSON and retrieved evidence below.

Rules:
- Do not invent facts.
- Do not provide legal advice.
- Mark missing or unclear items clearly.
- Include evidence references like [Page 2, p2_c1].
- Keep the memo concise, structured, and useful.

Output formatting rules:
- Return plain text only.
- Do not use Markdown.
- Do not use **bold** syntax.
- Do not use # or ### headings.
- Do not use asterisks for bullets.
- Use clean numbered headings.
- Use hyphen bullets only when listing items.
- Do not wrap the answer in code fences.

Required memo format:

MEMORANDUM

TO: Operator Review
FROM: Legal Department
DATE: Date of Review
SUBJECT: First-Pass Review of [Document Type]

1. Summary

[Write concise summary.]

2. Parties

- Purchaser: [Name] [Evidence]
- Seller: [Name] [Evidence]

3. Key Dates

- Agreement Date: [Date] [Evidence]

4. Main Obligations

- [Party]&#58; [Obligation] [Evidence]

5. Payment Terms

- [Payment term] [Evidence]

6. Notice / Breach / Termination

- Notice: [Details or Not found in retrieved evidence]
- Breach: [Details or Not found in retrieved evidence]
- Termination: [Details or Not found in retrieved evidence]

7. Governing Law / Forum

- Governing Law: [Details or Not found in retrieved evidence]
- Forum: [Details or Not found in retrieved evidence]

8. Missing or Unclear Information

- [Missing item]

9. Evidence Used

- [Page X, chunk_id]

EXTRACTED JSON:
{json.dumps(extracted, indent=2)}

RETRIEVED EVIDENCE:
{evidence_text}
"""

    try:
        return _generate_text(prompt, expect_json=False)
    except Exception as exc:
        return _fallback_memo(extracted, evidence, reason=f"Gemini memo generation failed: {exc}")


def learn_from_edit(original_draft: str, edited_draft: str) -> Dict[str, Any]:
    if _gemini_client() is None:
        return {
            "learned_rules": [
                "Operator edited the draft. Review tone, structure, and missing details in future drafts."
            ],
            "note": "Set GEMINI_API_KEY and install google-genai for model-based edit learning."
        }

    prompt = f"""
Compare the original AI draft with the operator-edited draft.
Extract reusable improvement rules, not just a side-by-side diff.

Return valid JSON only with these keys:
- learned_rules
- tone_preferences
- structure_preferences
- factual_corrections
- reusable_prompt_instruction

Rules:
- Do not use markdown.
- Do not wrap the JSON in code fences.
- If there are no factual corrections, return an empty array for factual_corrections.

ORIGINAL DRAFT:
{original_draft[:12000]}

OPERATOR EDITED DRAFT:
{edited_draft[:12000]}
"""

    try:
        return _safe_json(_generate_text(prompt, expect_json=True))
    except Exception as exc:
        return {
            "learned_rules": [],
            "error": f"Gemini edit learning failed: {exc}"
        }


def _fallback_extract(full_text: str) -> Dict[str, Any]:
    return {
        "document_type": "Unknown legal-style document",
        "parties": [],
        "key_dates": [],
        "obligations": [],
        "payment_terms": [],
        "notice_requirements": [],
        "termination": [],
        "governing_law": [],
        "risks": [],
        "missing_information": [
            "GEMINI_API_KEY not configured or google-genai not installed. Text was extracted, but model-based structured extraction was not run."
        ],
    }


def _fallback_memo(extracted: Dict[str, Any], evidence: List[dict], reason: str | None = None) -> str:
    summary = reason or "Model drafting is disabled because GEMINI_API_KEY is not configured or google-genai is not installed."

    lines = [
        "First-Pass Internal Memo",
        "",
        "Summary",
        summary,
        "",
        "Extracted Fields",
        json.dumps(extracted, indent=2),
        "",
        "Retrieved Evidence",
    ]

    for e in evidence:
        lines.append(f"Page {e['page']} | {e['chunk_id']}")
        lines.append(e["text"][:900])
        lines.append("")

    return "\n".join(lines)
