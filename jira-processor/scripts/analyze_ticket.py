#!/usr/bin/env python3
"""
Analyze Jira ticket to classify its type and extract relevant data.

Usage:
    python analyze_ticket.py --summary "Ticket summary" --description "Ticket description"
    python analyze_ticket.py --summary "..." --description "..." --comments "Comment text"
    python analyze_ticket.py --json  # Output as JSON
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.jira_patterns import classify_ticket_type, extract_urls, assess_ralph_eligibility
from utils.code_mapper import map_keywords_to_files, extract_index_from_urls, extract_index_from_text, get_primary_files


def analyze_ticket(summary: str, description: str, comments: str = "") -> dict:
    """Analyze a Jira ticket and return classification with extracted data.

    Args:
        summary: Ticket summary/title
        description: Ticket description
        comments: Formatted comments string (optional)
    """
    full_text = f"{summary}\n{description}"
    if comments:
        full_text = f"{full_text}\n{comments}"

    classification = classify_ticket_type(summary, description, comments)

    if classification["type"] == "CODE_CHANGE":
        classification["suggested_files"] = get_primary_files(full_text)
        classification["file_mappings"] = map_keywords_to_files(full_text)[:5]

        ticket_data = {"summary": summary, "description": description, "comments": comments}
        ralph_assessment = assess_ralph_eligibility(ticket_data, classification)
        classification["ralph_eligibility"] = ralph_assessment

    elif classification["type"] == "INVESTIGATION":
        urls = extract_urls(full_text)
        indices_from_urls = extract_index_from_urls(urls)
        indices_from_text = extract_index_from_text(full_text)
        all_indices = list(set(indices_from_urls + indices_from_text))
        classification["suggested_indices"] = all_indices if all_indices else []

    return classification


def main():
    parser = argparse.ArgumentParser(description="Analyze Jira ticket for classification")
    parser.add_argument("--summary", required=True, help="Ticket summary/title")
    parser.add_argument("--description", default="", help="Ticket description")
    parser.add_argument("--comments", default="", help="Formatted comments from ticket")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    result = analyze_ticket(args.summary, args.description, args.comments)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Type: {result['type']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Reason: {result['reason']}")

        if result.get("extracted_data", {}).get("isbns"):
            print(f"ISBNs found: {', '.join(result['extracted_data']['isbns'])}")

        if result.get("suggested_files"):
            print(f"Suggested files: {', '.join(result['suggested_files'])}")

        if result.get("suggested_indices"):
            print(f"Suggested indices: {', '.join(result['suggested_indices'])}")

        if result.get("ralph_eligibility"):
            ralph = result["ralph_eligibility"]
            print(f"Ralph-eligible: {ralph['eligible']}")
            print(f"Ralph confidence: {ralph['confidence']:.2f}")
            if ralph.get("criteria_met"):
                print(f"Criteria met: {', '.join(ralph['criteria_met'])}")
            if ralph.get("disqualifiers"):
                print(f"Disqualifiers: {', '.join(ralph['disqualifiers'])}")


if __name__ == "__main__":
    main()
