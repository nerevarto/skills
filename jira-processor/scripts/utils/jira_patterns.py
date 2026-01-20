"""Pattern matching utilities for Jira ticket classification."""

import re
from typing import List, Dict

CODE_CHANGE_KEYWORDS = [
    "add", "implement", "create", "build", "develop",
    "fix", "bug", "error", "broken", "failing",
    "update", "modify", "change", "refactor",
    "remove", "delete", "deprecate",
    "configure", "enable", "disable",
    "integrate", "connect", "support"
]

INVESTIGATION_KEYWORDS = [
    "not appearing", "not showing", "missing",
    "why", "investigate", "check", "look into",
    "cannot find", "doesn't exist", "no results",
    "no longer", "not working", "broken link"
]

SKIP_KEYWORDS = [
    "meeting", "waiting for", "blocked by",
    "pending approval", "need access", "credentials required",
    "documentation only", "write docs", "update readme"
]

ISBN_PATTERN = re.compile(r'\b(978\d{10})\b')
FILE_PATTERN = re.compile(r'\b[\w/]+\.(py|yaml|json|xml)\b')
FUNCTION_PATTERN = re.compile(r'\b(def\s+\w+|class\s+\w+|\w+\(\))\b')
URL_PATTERN = re.compile(r'https?://[^\s<>"]+')


def extract_isbns(text: str) -> List[str]:
    """Extract ISBN-13 numbers from text."""
    return ISBN_PATTERN.findall(text)


def extract_file_references(text: str) -> List[str]:
    """Extract file path references from text."""
    return FILE_PATTERN.findall(text)


def extract_urls(text: str) -> List[str]:
    """Extract URLs from text."""
    return URL_PATTERN.findall(text)


def extract_function_references(text: str) -> List[str]:
    """Extract function/class references from text."""
    return FUNCTION_PATTERN.findall(text)


def count_keyword_matches(text: str, keywords: List[str]) -> int:
    """Count how many keywords appear in text (case-insensitive)."""
    text_lower = text.lower()
    count = 0
    for keyword in keywords:
        if keyword.lower() in text_lower:
            count += 1
    return count


def find_matching_keywords(text: str, keywords: List[str]) -> List[str]:
    """Return list of keywords that appear in text."""
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def classify_ticket_type(summary: str, description: str) -> Dict:
    """
    Classify ticket into CODE_CHANGE, INVESTIGATION, or SKIP.

    Returns dict with:
        - type: str ("CODE_CHANGE", "INVESTIGATION", "SKIP")
        - confidence: float (0.0 to 1.0)
        - reason: str
        - extracted_data: dict with ISBNs, URLs, file refs, etc.
    """
    full_text = f"{summary}\n{description}"

    extracted_data = {
        "isbns": extract_isbns(full_text),
        "urls": extract_urls(full_text),
        "file_refs": extract_file_references(full_text),
        "function_refs": extract_function_references(full_text)
    }

    skip_matches = find_matching_keywords(full_text, SKIP_KEYWORDS)
    if skip_matches:
        return {
            "type": "SKIP",
            "confidence": 0.9,
            "reason": f"Contains skip indicators: {', '.join(skip_matches)}",
            "extracted_data": extracted_data
        }

    investigation_matches = find_matching_keywords(full_text, INVESTIGATION_KEYWORDS)
    code_change_matches = find_matching_keywords(full_text, CODE_CHANGE_KEYWORDS)

    has_urls = len(extracted_data["urls"]) > 0
    has_file_refs = len(extracted_data["file_refs"]) > 0

    investigation_score = len(investigation_matches) * 2
    if has_urls:
        investigation_score += 2

    code_change_score = len(code_change_matches) * 2
    if has_file_refs:
        code_change_score += 3
    if extracted_data["function_refs"]:
        code_change_score += 2

    if investigation_score > code_change_score and investigation_score >= 3:
        return {
            "type": "INVESTIGATION",
            "confidence": min(investigation_score / 10, 1.0),
            "reason": f"Investigation indicators: {', '.join(investigation_matches)}",
            "extracted_data": extracted_data
        }

    if code_change_score >= 2:
        return {
            "type": "CODE_CHANGE",
            "confidence": min(code_change_score / 10, 1.0),
            "reason": f"Code change indicators: {', '.join(code_change_matches)}",
            "extracted_data": extracted_data
        }

    return {
        "type": "SKIP",
        "confidence": 0.5,
        "reason": "No clear action indicators found",
        "extracted_data": extracted_data
    }
