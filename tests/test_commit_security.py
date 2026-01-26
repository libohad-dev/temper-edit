# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from pathlib import Path

from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.utils import PYTHON_BINARY, parse_output

SCRIPT_PATH = Path(__file__).parent / "commit_security_script.py"


def test_commit_sequence_is_secure(container: DockerContainer) -> None:
    """Test that the commit process maintains security properties at each step.

    At no point during the commit process should a root-owned file become
    world-executable (potential for privilege escalation attacks), or modify the
    target file's permissions or ownership. In other words, at no step is either
    file accessible to unauthorized users. The sequence is:
    1. chmod 000 - strip all permissions (unreadable except by root)
    2. chown - transfer ownership while still 000 (still unreadable)
    3. copymod - restore permissions with correct ownership
    4. move - atomic move to destination, preserving
    """
    # Setup target file: owned by user:user (1000:1000), mode 755, content "original"
    container.exec(["sh", "-c", "echo -n 'original' > /tmp/target.txt"])
    container.exec(["chmod", "755", "/tmp/target.txt"])
    container.exec(["chown", "user:user", "/tmp/target.txt"])

    # Setup source file: owned by root:root, mode 644, content "modified"
    container.exec(["sh", "-c", "echo -n 'modified' > /tmp/source.txt"])
    container.exec(["chmod", "644", "/tmp/source.txt"])

    script_content = SCRIPT_PATH.read_text()
    output = parse_output(container.exec([PYTHON_BINARY, "-c", script_content]))
    results = json.loads(output)

    expected = [
        {
            # Initial state before generator starts
            "step": "initial",
            "source": {
                "exists": True,
                "uid": 0,  # root-owned
                "gid": 0,
                "mode": "644",
                "content": "modified",
            },
            "target": {
                "exists": True,
                "uid": 1000,  # user-owned
                "gid": 1000,
                "mode": "755",
                "content": "original",
            },
        },
        {
            # After chmod 000: source has no permissions, still root-owned
            "step": "strip permissions",
            "source": {
                "exists": True,
                "uid": 0,  # still root-owned
                "gid": 0,
                "mode": "000",  # no permissions - non-root users cannot access
                "content": "modified",  # root can still read
            },
            "target": {
                "exists": True,
                "uid": 1000,
                "gid": 1000,
                "mode": "755",
                "content": "original",  # unchanged
            },
        },
        {
            # After chown: ownership transferred while still mode 000 - secure
            "step": "change ownership",
            "source": {
                "exists": True,
                "uid": 1000,  # now user-owned
                "gid": 1000,
                "mode": "000",  # still no permissions - non-root users cannot access
                "content": "modified",  # root can still read
            },
            "target": {
                "exists": True,
                "uid": 1000,
                "gid": 1000,
                "mode": "755",
                "content": "original",  # unchanged
            },
        },
        {
            # After copymode: correct ownership + permissions, ready for move
            "step": "copy permissions",
            "source": {
                "exists": True,
                "uid": 1000,
                "gid": 1000,
                "mode": "755",  # permissions restored
                "content": "modified",
            },
            "target": {
                "exists": True,
                "uid": 1000,
                "gid": 1000,
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
                "uid": 1000,
                "gid": 1000,
                "mode": "755",
                "content": "modified",  # new content
            },
        },
    ]

    assert results == expected
