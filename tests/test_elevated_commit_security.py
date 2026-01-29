# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.utils import PYTHON_BINARY, exec_as_user, parse_output

ELEVATED_SCRIPT_PATH = Path(__file__).parent / "elevated_commit_security_script.py"


@pytest.mark.parametrize("escalation_program", ["sudo", "doas"])
def test_elevated_commit_sequence_is_secure(
    container: DockerContainer,
    escalation_program: str,
) -> None:
    """Test that elevated commit maintains security properties at each step.

    This test runs as an unprivileged user with passwordless sudo/doas access,
    editing a root-owned target file. The security requirements are:
    - At no point should the source file be readable by unauthorized users
      while containing sensitive content with wrong ownership
    - The target file should maintain its ownership and permissions throughout

    The sequence is:
    1. chmod 000 - strip all permissions (unreadable even by owner)
    2. chown - transfer ownership while still 000 (still unreadable)
    3. chmod - restore permissions with correct ownership
    4. mv - atomic move to destination
    """
    # Setup target file: owned by root:root, mode 755, content "original"
    container.exec(["sh", "-c", "echo -n 'original' > /tmp/target.txt"])
    container.exec(["chmod", "755", "/tmp/target.txt"])
    # File stays root:root

    # Setup source file: owned by user:user, mode 644, content "modified"
    container.exec(["sh", "-c", "echo -n 'modified' > /tmp/source.txt"])
    container.exec(["chmod", "644", "/tmp/source.txt"])
    container.exec(["chown", "user:user", "/tmp/source.txt"])

    # Run security script AS USER (user has passwordless sudo/doas via wheel group)
    script_content = ELEVATED_SCRIPT_PATH.read_text()
    output = parse_output(
        exec_as_user(
            command=[PYTHON_BINARY, "-c", script_content, escalation_program],
            container=container,
        )
    )
    results = json.loads(output)

    expected = [
        {
            # Initial state before generator starts
            "step": "initial",
            "source": {
                "exists": True,
                "uid": 1000,  # user-owned (temp file)
                "gid": 1000,
                "mode": "644",
                "content": "modified",
            },
            "target": {
                "exists": True,
                "uid": 0,  # root-owned
                "gid": 0,
                "mode": "755",
                "content": "original",
            },
        },
        {
            # After chmod 000: source unreadable (even by owner with mode 000)
            "step": "strip permissions",
            "source": {
                "exists": True,
                "uid": 1000,  # still user-owned
                "gid": 1000,
                "mode": "000",  # no permissions - non-root users cannot access
                "content": "<unreadable>",
            },
            "target": {
                "exists": True,
                "uid": 0,
                "gid": 0,
                "mode": "755",
                "content": "original",  # unchanged
            },
        },
        {
            # After chown: ownership transferred to root while still mode 000 - secure
            "step": "change ownership",
            "source": {
                "exists": True,
                "uid": 0,  # now root-owned
                "gid": 0,
                "mode": "000",  # still no permissions - non-root users cannot access
                "content": "<unreadable>",  # script runs as user - no read access
            },
            "target": {
                "exists": True,
                "uid": 0,
                "gid": 0,
                "mode": "755",
                "content": "original",  # unchanged
            },
        },
        {
            # After chmod to target mode: now readable with correct permissions
            "step": "copy permissions",
            "source": {
                "exists": True,
                "uid": 0,
                "gid": 0,
                "mode": "755",  # permissions restored
                "content": "modified",
            },
            "target": {
                "exists": True,
                "uid": 0,
                "gid": 0,
                "mode": "755",
                "content": "original",  # unchanged
            },
        },
        {
            # After move (generator exhausted): source gone, target updated
            "step": "exhausted",
            "source": {
                "exists": False,  # moved away
            },
            "target": {
                "exists": True,
                "uid": 0,
                "gid": 0,
                "mode": "755",
                "content": "modified",  # new content
            },
        },
    ]

    assert results == expected
