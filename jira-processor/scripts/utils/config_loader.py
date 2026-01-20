"""Load configuration dynamically from repo-level .claude/jira-config.yaml or .json"""

import os
import json
from typing import Dict, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

DEFAULT_CONFIG = {
    "jira": {
        "projects": [],
        "statuses": ["Open", "In Progress", "To Do"],
        "max_tickets_per_run": 10
    },
    "github": {
        "owner": None,
        "repo": None,
        "base_branch": "main",
        "branch_prefix": "feature/"
    },
    "verification": {
        "max_fix_attempts": 3,
        "test_command": "python -m pytest",
        "build_command": "docker-compose build",
        "timeout_seconds": 300
    }
}


def find_repo_root() -> Optional[str]:
    """Find the git repository root from current working directory."""
    cwd = os.getcwd()
    while cwd != "/":
        if os.path.isdir(os.path.join(cwd, ".git")):
            return cwd
        cwd = os.path.dirname(cwd)
    return None


def load_repo_config() -> Dict:
    """
    Load configuration from repo-level .claude/jira-config.yaml or .json.
    Falls back to defaults if not found.
    """
    repo_root = find_repo_root()
    if not repo_root:
        return DEFAULT_CONFIG.copy()

    claude_dir = os.path.join(repo_root, ".claude")
    yaml_path = os.path.join(claude_dir, "jira-config.yaml")
    json_path = os.path.join(claude_dir, "jira-config.json")

    repo_config = {}

    if os.path.exists(yaml_path) and HAS_YAML:
        with open(yaml_path, "r") as f:
            repo_config = yaml.safe_load(f) or {}
    elif os.path.exists(json_path):
        with open(json_path, "r") as f:
            repo_config = json.load(f)
    else:
        return DEFAULT_CONFIG.copy()

    merged = DEFAULT_CONFIG.copy()
    for key in merged:
        if key in repo_config:
            if isinstance(merged[key], dict):
                merged[key] = {**merged[key], **repo_config[key]}
            else:
                merged[key] = repo_config[key]

    return merged


def get_github_config() -> Dict:
    """Get GitHub configuration for current repo."""
    config = load_repo_config()
    return config.get("github", DEFAULT_CONFIG["github"])


def get_jira_config() -> Dict:
    """Get Jira configuration for current repo."""
    config = load_repo_config()
    return config.get("jira", DEFAULT_CONFIG["jira"])


def get_verification_config() -> Dict:
    """Get verification configuration for current repo."""
    config = load_repo_config()
    return config.get("verification", DEFAULT_CONFIG["verification"])


def get_code_mapping() -> list:
    """Get code mapping rules for current repo."""
    config = load_repo_config()
    return config.get("code_mapping", {}).get("patterns", [])


def get_index_url_mapping() -> Dict:
    """Get index URL mapping for current repo."""
    config = load_repo_config()
    return config.get("index_url_mapping", {})


def get_project_context() -> Dict:
    """Get project context for current repo."""
    config = load_repo_config()
    return config.get("project", {})


def get_investigation_config() -> Dict:
    """Get investigation configuration for current repo."""
    config = load_repo_config()
    return config.get("investigation", {})
