"""Parse Atlassian Document Format (ADF) to plain text."""

import json
from typing import Union


def parse_adf_to_text(adf: Union[dict, str]) -> str:
    """Convert ADF document to plain text.

    Args:
        adf: ADF document as dict or JSON string

    Returns:
        Plain text representation of the document
    """
    if isinstance(adf, str):
        try:
            adf = json.loads(adf)
        except json.JSONDecodeError:
            return adf

    if not isinstance(adf, dict):
        return str(adf) if adf else ""

    return _extract_text_from_node(adf).strip()


def _extract_text_from_node(node: dict) -> str:
    """Recursively extract text from an ADF node."""
    if not isinstance(node, dict):
        return ""

    node_type = node.get("type", "")
    text_parts = []

    if node_type == "text":
        return node.get("text", "")

    if node_type == "mention":
        attrs = node.get("attrs", {})
        return attrs.get("text", "")

    if node_type == "emoji":
        attrs = node.get("attrs", {})
        return attrs.get("shortName", "")

    if node_type == "hardBreak":
        return "\n"

    content = node.get("content", [])
    for child in content:
        text_parts.append(_extract_text_from_node(child))

    result = "".join(text_parts)

    if node_type in ("paragraph", "heading", "blockquote", "listItem"):
        result = result + "\n"
    elif node_type in ("bulletList", "orderedList"):
        result = result + "\n"

    return result


def parse_jira_comments(comments_data: Union[list, dict]) -> list[dict]:
    """Parse Jira comments array into simplified format.

    Args:
        comments_data: Raw comments from Jira API (fields.comment.comments)

    Returns:
        List of dicts with 'author', 'text', 'created' keys
    """
    if isinstance(comments_data, dict):
        comments_data = comments_data.get("comments", [])

    if not isinstance(comments_data, list):
        return []

    parsed = []
    for comment in comments_data:
        author = comment.get("author", {}).get("displayName", "Unknown")
        body = comment.get("body", {})
        text = parse_adf_to_text(body)
        created = comment.get("created", "")

        parsed.append({
            "author": author,
            "text": text,
            "created": created
        })

    return parsed


def format_comments_for_analysis(comments: list[dict]) -> str:
    """Format parsed comments into a single string for analysis.

    Args:
        comments: List of parsed comments from parse_jira_comments()

    Returns:
        Formatted string with all comments
    """
    if not comments:
        return ""

    lines = []
    for i, comment in enumerate(comments, 1):
        author = comment.get("author", "Unknown")
        text = comment.get("text", "").strip()
        if text:
            lines.append(f"[Comment {i} by {author}]: {text}")

    return "\n".join(lines)
