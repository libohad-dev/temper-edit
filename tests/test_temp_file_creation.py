# SPDX-FileCopyrightText: 2025 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import textwrap

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.utils import parse_output


def test_failed_command(container: DockerContainer) -> None:
    with pytest.raises(RuntimeError):
        _ = parse_output(container.exec(["false"]))
    with pytest.raises(RuntimeError):
        _ = parse_output(container.exec(["foobar"]))


def test_basic_tempfile_permissions(container: DockerContainer) -> None:
    tempfile = parse_output(container.exec(["mktemp"]))

    script = textwrap.dedent(f"""\
    import os
    sr = os.stat("{tempfile}")
    print(sr.st_size)
    print(hex(sr.st_mode))
    print(sr.st_uid)
    print(sr.st_gid)
    """)
    filestat = parse_output(container.exec(["python", "-c", script]))

    assert filestat.split() == ["0", "0x8180", "0", "0"]
