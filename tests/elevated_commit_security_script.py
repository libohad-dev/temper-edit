# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Script injected into container to test elevated_commit_file_steps security properties."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from temper_edit.atomic_edit import elevated_commit_file_steps

expected_steps = ["strip permissions", "change ownership", "copy permissions"]

source = Path("/tmp/source.txt")
target = Path("/tmp/target.txt")


def get_file_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    mode = oct(stat.st_mode)[-3:]
    try:
        content = path.read_text()
    except PermissionError:
        content = "<unreadable>"
    return {
        "exists": True,
        "uid": stat.st_uid,
        "gid": stat.st_gid,
        "mode": mode,
        "content": content,
    }


def get_full_step_state(step: str) -> dict[str, Any]:
    return {
        "step": step,
        "source": get_file_state(source),
        "target": get_file_state(target),
    }


def run_commit_process(escalation_program: str) -> list[dict[str, Any]]:
    def run_privileged(args: list[str]) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run([escalation_program] + args, capture_output=True, check=True)

    results = []

    # Create generator - no code executes yet
    gen = elevated_commit_file_steps(source, target, run_privileged)

    # Record initial state
    results.append(get_full_step_state("initial"))

    # Step through generator
    for i, step in enumerate(gen):
        assert step == expected_steps[i], f"Expected {expected_steps[i]}, got {step}"
        results.append(get_full_step_state(step))

    # Generator exhausted - move has completed, record final state
    results.append(get_full_step_state("exhausted"))

    # Verify generator is truly exhausted
    try:
        next(gen)
        raise AssertionError("Generator not exhausted!")
    except StopIteration:
        pass

    return results


if __name__ == "__main__":
    escalation_program = sys.argv[1]
    print(json.dumps(run_commit_process(escalation_program), indent=2))
