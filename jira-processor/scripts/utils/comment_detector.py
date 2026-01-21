"""Utilities for detecting previous comments and follow-up scenarios."""

from datetime import datetime
from typing import Optional


def find_user_comments(comments: list[dict], user_account_id: str) -> list[dict]:
    """Find all comments made by the specified user account ID.

    Args:
        comments: Raw comments from Jira API (fields.comment.comments)
        user_account_id: The Jira account ID to match

    Returns:
        List of comments authored by the specified user, in chronological order
    """
    if not comments or not user_account_id:
        return []

    user_comments = []
    for comment in comments:
        author = comment.get("author", {})
        if author.get("accountId") == user_account_id:
            user_comments.append(comment)

    return user_comments


def get_latest_user_comment(comments: list[dict], user_account_id: str) -> Optional[dict]:
    """Get the most recent comment made by the specified user.

    Args:
        comments: Raw comments from Jira API (fields.comment.comments)
        user_account_id: The Jira account ID to match

    Returns:
        The most recent comment by the user, or None if no comments found
    """
    user_comments = find_user_comments(comments, user_account_id)
    if not user_comments:
        return None

    return max(user_comments, key=lambda c: c.get("created", ""))


def get_comments_after(
    comments: list[dict],
    after_timestamp: str,
    exclude_account_id: Optional[str] = None
) -> list[dict]:
    """Get comments created after the given timestamp.

    Args:
        comments: Raw comments from Jira API (fields.comment.comments)
        after_timestamp: ISO timestamp to filter by (comments after this time)
        exclude_account_id: Optional account ID to exclude from results

    Returns:
        List of comments created after the timestamp, optionally excluding specified user
    """
    if not comments or not after_timestamp:
        return []

    result = []
    for comment in comments:
        created = comment.get("created", "")
        if created > after_timestamp:
            if exclude_account_id:
                author = comment.get("author", {})
                if author.get("accountId") == exclude_account_id:
                    continue
            result.append(comment)

    return result


def has_followup_from_others(comments: list[dict], user_account_id: str) -> bool:
    """Check if there are comments from other users after the user's last comment.

    Args:
        comments: Raw comments from Jira API (fields.comment.comments)
        user_account_id: The Jira account ID to check

    Returns:
        True if there are comments from other users after the user's last comment
    """
    latest_user_comment = get_latest_user_comment(comments, user_account_id)
    if not latest_user_comment:
        return False

    after_timestamp = latest_user_comment.get("created", "")
    newer_comments = get_comments_after(comments, after_timestamp, exclude_account_id=user_account_id)
    return len(newer_comments) > 0


def format_comments_for_followup(
    user_comments: list[dict],
    new_comments: list[dict],
    adf_parser_func
) -> dict:
    """Format comments for the jira-followup skill.

    Args:
        user_comments: All comments by the current user
        new_comments: New comments from other users after user's last comment
        adf_parser_func: Function to convert ADF to plain text (parse_adf_to_text)

    Returns:
        Dict with 'user_comments' and 'new_comments' formatted as readable strings
    """
    formatted_user = []
    for comment in user_comments:
        created = comment.get("created", "")[:19].replace("T", " ")
        body = comment.get("body", {})
        text = adf_parser_func(body)
        formatted_user.append(f"[{created}]: {text.strip()}")

    formatted_new = []
    for comment in new_comments:
        author = comment.get("author", {}).get("displayName", "Unknown")
        created = comment.get("created", "")[:19].replace("T", " ")
        body = comment.get("body", {})
        text = adf_parser_func(body)
        formatted_new.append(f"[Comment by {author} at {created}]: {text.strip()}")

    return {
        "user_comments": "\n".join(formatted_user),
        "new_comments": "\n".join(formatted_new)
    }
