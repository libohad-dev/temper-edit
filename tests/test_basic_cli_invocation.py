# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.utils import parse_output


def test_script_fails_without_arguments(container: DockerContainer) -> None:
    with pytest.raises(RuntimeError):
        _ = parse_output(container.exec(["temper-edit"]))


def test_script_runs_with_one_argument(container: DockerContainer) -> None:
    _ = parse_output(container.exec(["temper-edit", "foo"]))


def test_script_fails_with_multiple_argument(container: DockerContainer) -> None:
    with pytest.raises(RuntimeError):
        _ = parse_output(container.exec(["temper-edit", "foo", "bar"]))
