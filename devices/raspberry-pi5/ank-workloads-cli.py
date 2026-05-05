#!/usr/bin/env python3
"""Workaround CLI helper to retrieve Ankaios workloads when dashboard is unavailable."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from typing import Any


def run_cmd(cmd: list[str]) -> tuple[bool, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.returncode == 0, proc.stdout.strip(), proc.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "", str(exc)


def candidate_commands(use_insecure: bool) -> list[list[str]]:
    base: list[list[str]] = [
        ["ank", "get", "workloads", "-o", "json"],
        ["ank", "get", "workload", "-o", "json"],
        ["ank", "get", "state", "-o", "json"],
    ]

    secure: list[list[str]] = [
        ["ank", "-k", "get", "workloads", "-o", "json"],
        ["ank", "-k", "get", "workload", "-o", "json"],
        ["ank", "-k", "get", "state", "-o", "json"],
    ]

    return secure + base if use_insecure else base + secure


def extract_workloads(payload: Any) -> list[dict[str, Any]]:
    # Supports different payload shapes across ank versions.
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        for key in ("workloads", "Workloads"):
            if key in payload:
                workloads_obj = payload[key]
                if isinstance(workloads_obj, dict):
                    return [
                        {"name": name, **(info if isinstance(info, dict) else {})}
                        for name, info in workloads_obj.items()
                    ]
                if isinstance(workloads_obj, list):
                    return [item for item in workloads_obj if isinstance(item, dict)]

        for path in (
            ("desiredState", "workloads"),
            ("state", "workloads"),
            ("status", "workloads"),
        ):
            node: Any = payload
            found = True
            for part in path:
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    found = False
                    break
            if found:
                if isinstance(node, dict):
                    return [
                        {"name": name, **(info if isinstance(info, dict) else {})}
                        for name, info in node.items()
                    ]
                if isinstance(node, list):
                    return [item for item in node if isinstance(item, dict)]
        entries = [payload]
    else:
        entries = []

    normalized: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        normalized.append(item)
    return normalized


def normalize_workload(item: dict[str, Any]) -> dict[str, str]:
    def pick(*keys: str, default: str = "-") -> str:
        for key in keys:
            value = item.get(key)
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                text = str(value).strip()
                if text:
                    return text
        return default

    workload_name = pick("name", "workloadName", "id")
    agent = pick("agent", "agentName", "node", "instance")
    runtime = pick("runtime", "runtimeName")
    image = pick("image", "containerImage")
    state = pick("executionState", "state", "status", "lifecycle", "phase")

    return {
        "name": workload_name,
        "agent": agent,
        "runtime": runtime,
        "image": image,
        "state": state,
    }


def print_table(rows: list[dict[str, str]]) -> None:
    if not rows:
        print("No workloads returned.")
        return

    headers = ["NAME", "AGENT", "RUNTIME", "STATE", "IMAGE"]
    keys = ["name", "agent", "runtime", "state", "image"]
    widths = []
    for header, key in zip(headers, keys):
        widths.append(max(len(header), *(len(row.get(key, "-")) for row in rows)))

    fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for row in rows:
        print(fmt.format(*(row.get(key, "-") for key in keys)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retrieve Ankaios workload information with CLI command fallbacks."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print normalized result as JSON instead of table.",
    )
    parser.add_argument(
        "--insecure-first",
        action="store_true",
        help="Try '-k' commands first.",
    )
    args = parser.parse_args()

    if shutil.which("ank") is None:
        print("Error: 'ank' command not found in PATH.", file=sys.stderr)
        return 2

    last_error = ""
    for cmd in candidate_commands(use_insecure=args.insecure_first):
        ok, stdout, stderr = run_cmd(cmd)
        if not ok:
            last_error = stderr or f"command failed: {' '.join(cmd)}"
            continue
        if not stdout:
            last_error = f"empty output: {' '.join(cmd)}"
            continue

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            last_error = f"non-JSON output from: {' '.join(cmd)}"
            continue

        workloads = extract_workloads(payload)
        normalized = [normalize_workload(item) for item in workloads]

        if args.json:
            print(
                json.dumps(
                    {
                        "command_used": cmd,
                        "workload_count": len(normalized),
                        "workloads": normalized,
                    },
                    indent=2,
                )
            )
        else:
            print(f"Command used: {' '.join(cmd)}")
            print(f"Workloads detected: {len(normalized)}")
            print_table(normalized)
        return 0

    print("Failed to retrieve workloads with known ank commands.", file=sys.stderr)
    if last_error:
        print(f"Last error: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
