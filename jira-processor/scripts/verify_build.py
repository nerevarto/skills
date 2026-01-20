#!/usr/bin/env python3
"""
Run verification tests and build for the project.

Usage:
    python verify_build.py --run-tests
    python verify_build.py --run-build
    python verify_build.py --run-all
    python verify_build.py --json  # Output as JSON
"""

import argparse
import json
import subprocess
import sys
import os
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.config_loader import get_verification_config, find_repo_root


def get_project_root() -> str:
    """Get project root directory."""
    return find_repo_root() or os.getcwd()


def run_command(command: str, timeout: int = 300) -> Tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=get_project_root()
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return -1, "", str(e)


def parse_pytest_failures(output: str) -> List[Dict]:
    """Parse pytest output to extract failure details."""
    failures = []
    lines = output.split("\n")
    current_failure = None

    for line in lines:
        if line.startswith("FAILED "):
            if current_failure:
                failures.append(current_failure)
            test_path = line.replace("FAILED ", "").split(" ")[0]
            current_failure = {
                "test": test_path,
                "error": "",
                "type": "test_failure"
            }
        elif current_failure and ("Error" in line or "assert" in line.lower()):
            current_failure["error"] += line + "\n"

    if current_failure:
        failures.append(current_failure)

    return failures


def parse_build_errors(output: str) -> List[Dict]:
    """Parse build output to extract errors."""
    errors = []
    lines = output.split("\n")

    for i, line in enumerate(lines):
        if "error" in line.lower() or "Error:" in line:
            errors.append({
                "line": i + 1,
                "message": line.strip(),
                "type": "build_error"
            })

    return errors


def run_tests() -> Dict:
    """Run tests and return results."""
    config = get_verification_config()
    command = config.get("test_command", "python -m pytest -v --tb=short")
    timeout = config.get("timeout_seconds", 300)

    exit_code, stdout, stderr = run_command(command, timeout)

    output = stdout + stderr
    failures = parse_pytest_failures(output) if exit_code != 0 else []

    return {
        "passed": exit_code == 0,
        "exit_code": exit_code,
        "failures": failures,
        "output_summary": output[-2000:] if len(output) > 2000 else output
    }


def run_build() -> Dict:
    """Run build and return results."""
    config = get_verification_config()
    command = config.get("build_command", "docker-compose build")
    timeout = config.get("timeout_seconds", 300)

    exit_code, stdout, stderr = run_command(command, timeout)

    output = stdout + stderr
    errors = parse_build_errors(output) if exit_code != 0 else []

    return {
        "passed": exit_code == 0,
        "exit_code": exit_code,
        "errors": errors,
        "output_summary": output[-2000:] if len(output) > 2000 else output
    }


def verify_all() -> Dict:
    """Run both tests and build verification."""
    result = {
        "success": True,
        "tests_passed": None,
        "build_passed": None,
        "failures": [],
        "error_messages": []
    }

    test_result = run_tests()
    result["tests_passed"] = test_result["passed"]
    if not test_result["passed"]:
        result["success"] = False
        result["failures"].extend(test_result["failures"])
        for f in test_result["failures"]:
            if f.get("error"):
                result["error_messages"].append(f"Test failure in {f['test']}: {f['error'][:500]}")

    build_result = run_build()
    result["build_passed"] = build_result["passed"]
    if not build_result["passed"]:
        result["success"] = False
        result["failures"].extend(build_result["errors"])
        for e in build_result["errors"]:
            result["error_messages"].append(f"Build error: {e['message']}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Run verification tests and build")
    parser.add_argument("--run-tests", action="store_true", help="Run tests")
    parser.add_argument("--run-build", action="store_true", help="Run build")
    parser.add_argument("--run-all", action="store_true", help="Run both tests and build")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.run_all or (not args.run_tests and not args.run_build):
        result = verify_all()
    elif args.run_tests:
        test_result = run_tests()
        result = {
            "success": test_result["passed"],
            "tests_passed": test_result["passed"],
            "failures": test_result["failures"],
            "error_messages": [f["error"] for f in test_result["failures"] if f.get("error")]
        }
    elif args.run_build:
        build_result = run_build()
        result = {
            "success": build_result["passed"],
            "build_passed": build_result["passed"],
            "failures": build_result["errors"],
            "error_messages": [e["message"] for e in build_result["errors"]]
        }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Success: {result['success']}")
        if result.get("tests_passed") is not None:
            print(f"Tests passed: {result['tests_passed']}")
        if result.get("build_passed") is not None:
            print(f"Build passed: {result['build_passed']}")
        if result.get("failures"):
            print(f"Failures: {len(result['failures'])}")
            for f in result["failures"][:5]:
                print(f"  - {f.get('test') or f.get('message', 'Unknown')}")

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
