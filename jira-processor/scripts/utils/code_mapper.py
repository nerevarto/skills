"""Map ticket requirements to relevant code files."""

from typing import List, Dict
from .config_loader import get_code_mapping, get_index_url_mapping

DEFAULT_CODE_MAPPING_RULES = [
    {
        "keywords": ["index", "indices", "filter", "filtering", "site config"],
        "files": ["config/indexConfig.py"]
    },
    {
        "keywords": ["config", "configuration", "settings"],
        "files": ["config/"]
    }
]


def get_code_mapping_rules() -> List[Dict]:
    """Get code mapping rules, preferring repo config."""
    repo_rules = get_code_mapping()
    return repo_rules if repo_rules else DEFAULT_CODE_MAPPING_RULES


def get_index_url_map() -> Dict:
    """Get index URL mapping, preferring repo config."""
    return get_index_url_mapping()


INDEX_URL_MAPPING = property(lambda self: get_index_url_map())


def map_keywords_to_files(text: str) -> List[Dict]:
    """
    Map text content to relevant code files.

    Returns list of dicts with:
        - file: file path
        - keywords_matched: list of keywords that matched
        - confidence: float (0.0 to 1.0)
    """
    text_lower = text.lower()
    results = []
    rules = get_code_mapping_rules()

    for rule in rules:
        matched_keywords = [kw for kw in rule["keywords"] if kw.lower() in text_lower]
        if matched_keywords:
            confidence = min(len(matched_keywords) / len(rule["keywords"]), 1.0)
            for file_path in rule["files"]:
                results.append({
                    "file": file_path,
                    "keywords_matched": matched_keywords,
                    "confidence": confidence
                })

    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results


def extract_index_from_urls(urls: List[str]) -> List[str]:
    """Extract Algolia index names from URLs based on repo config."""
    indices = set()
    mapping = get_index_url_map()
    for url in urls:
        url_lower = url.lower()
        for domain, index_name in mapping.items():
            if domain in url_lower:
                indices.add(index_name)
    return list(indices)


def extract_index_from_text(text: str) -> List[str]:
    """Extract index names mentioned directly in text."""
    indices = []
    mapping = get_index_url_map()
    for domain, index_name in mapping.items():
        if index_name.lower() in text.lower() or domain.lower() in text.lower():
            indices.append(index_name)
    return list(set(indices))


def get_primary_files(text: str) -> List[str]:
    """Get the most relevant files for a piece of text, deduplicated."""
    mappings = map_keywords_to_files(text)
    seen = set()
    primary = []
    for m in mappings:
        if m["file"] not in seen and m["confidence"] >= 0.3:
            seen.add(m["file"])
            primary.append(m["file"])
    return primary[:5]
