# SPDX-FileCopyrightText: 2025 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from docker.models.containers import ExecResult  # type: ignore[import-untyped]
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]
from testcontainers.core.image import DockerImage  # type: ignore[import-untyped]


@pytest.fixture
def container() -> Iterator[DockerContainer]:
    with (
        DockerImage(path=Path(__file__).parent, dockerfile_path="Containerfile") as image,
        DockerContainer(
            str(image),
            # keep-sorted start
            auto_remove=True,
            network_mode="none",
            read_only=True,
            remove=True,
            # keep-sorted end
        ) as test_container,
    ):
        yield test_container


def parse_output(res: ExecResult) -> str:
    if res.exit_code != 0:
        raise RuntimeError(res.output, res.exit_code)
    else:
        return cast(bytes, res.output).decode("utf-8").strip()


def test_basic_tempfile_permissions(container: DockerContainer) -> None:
    tempfile = parse_output(container.exec(["mktemp"]))

    script = f"""
    import os
    sr = os.stat("{tempfile}")
    print(sr.st_size)
    print(hex(sr.st_mode))
    print(sr.st_uid)
    print(sr.st_gid)
    """
    filestat = parse_output(container.exec(["python", "-c", script]))

    assert filestat.split() == ["0", "0x8180", "0", "0"]
