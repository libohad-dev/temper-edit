# SPDX-FileCopyrightText: 2025 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
import os
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from docker.models.containers import ExecResult  # type: ignore[import-untyped]
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]
from testcontainers.core.image import DockerImage  # type: ignore[import-untyped]

from temper_edit.file_model import FileStat


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


def get_file_stat(container: DockerContainer, filename: str) -> FileStat:
    filestat_raw = parse_output(container.exec(["python", "-c", f"import os; print(tuple(os.stat('{filename}')))"]))
    sr = os.stat_result(ast.literal_eval(filestat_raw))

    return FileStat.from_stat_results(sr)


def test_basic_tempfile_permissions(container: DockerContainer) -> None:
    tempfile = parse_output(container.exec(["mktemp"]))
    filestat = get_file_stat(container, tempfile)

    assert filestat.model_dump(exclude={"mtime"}) == {
        "size": 0,
        "mode": 0o600,
        "user": 0,
        "group": 0,
    }
