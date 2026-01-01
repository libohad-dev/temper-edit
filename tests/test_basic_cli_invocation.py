# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.utils import check_exception_content, parse_output


def test_script_fails_without_arguments(container: DockerContainer) -> None:
    with pytest.raises(RuntimeError):
        _ = parse_output(container.exec(["temper-edit"]))


def test_script_fails_with_multiple_argument(container: DockerContainer) -> None:
    with pytest.raises(RuntimeError):
        _ = parse_output(container.exec(["temper-edit", "foo", "bar"]))


def test_script_fails_with_no_editor_configured(container: DockerContainer) -> None:
    with pytest.raises(RuntimeError, match="No editor configured"):
        _ = parse_output(container.exec(["temper-edit", "foo"]))


def test_script_fails_with_invalid_editor(container: DockerContainer) -> None:
    with pytest.raises(RuntimeError, check=check_exception_content("No such file or directory: 'missing-editor'")):
        _ = parse_output(container.exec(["sh", "-c", "EDITOR=missing-editor temper-edit /etc/motd"]))


def test_script_fails_with_missing_file(container: DockerContainer) -> None:
    with pytest.raises(RuntimeError, check=check_exception_content("cat: can't open '/foo/bar'")):
        _ = parse_output(container.exec(["sh", "-c", "EDITOR=/bin/cat temper-edit /foo/bar"]))
