# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.utils import (
    TEMPER_EDIT_COMMAND,
    TEMPER_EDIT_SHELL_COMMAND,
    check_exception_content,
    exec_as_user,
    extract_log_filename,
    list_container_files,
    parse_output,
)


def test_script_fails_without_arguments(container: DockerContainer) -> None:
    with pytest.raises(RuntimeError):
        _ = parse_output(container.exec(TEMPER_EDIT_COMMAND))


def test_script_fails_with_multiple_argument(container: DockerContainer) -> None:
    with pytest.raises(RuntimeError):
        _ = parse_output(container.exec(TEMPER_EDIT_COMMAND + ["foo", "bar"]))


def test_script_fails_with_no_editor_configured(container: DockerContainer) -> None:
    with pytest.raises(RuntimeError, match="No editor configured") as exc_info:
        _ = parse_output(container.exec(TEMPER_EDIT_COMMAND + ["foo"]))

    assert exc_info.value.args[1] == 10

    # Verify no temporary files or log files were created
    assert list_container_files(container, "/tmp") == set()


def test_script_fails_with_invalid_editor(container: DockerContainer) -> None:
    with pytest.raises(RuntimeError, check=check_exception_content("Editor not found: missing-editor")) as exc_info:
        _ = parse_output(container.exec(["sh", "-c", f"EDITOR=missing-editor {TEMPER_EDIT_SHELL_COMMAND} /etc/motd"]))

    assert exc_info.value.args[1] == 30

    # Verify log file was written
    log_file = extract_log_filename(exc_info)
    log_content = parse_output(container.exec(["cat", log_file]))
    assert "Traceback" in log_content


def test_script_fails_with_missing_file(container: DockerContainer) -> None:
    with pytest.raises(RuntimeError, check=check_exception_content("File not found: /foo/bar")) as exc_info:
        _ = parse_output(container.exec(["sh", "-c", f"EDITOR=/bin/cat {TEMPER_EDIT_SHELL_COMMAND} /foo/bar"]))

    assert exc_info.value.args[1] == 21

    # Staging errors clean up the tempfile, but a log file is still written
    log_file = extract_log_filename(exc_info)
    log_content = parse_output(container.exec(["cat", log_file]))
    assert "Traceback" in log_content
    assert list_container_files(container, "/tmp") == {log_file}


@pytest.mark.parametrize("escalation_tool", ["sudo", "doas"])
def test_script_fails_when_run_with_escalated_privileges(container: DockerContainer, escalation_tool: str) -> None:
    with pytest.raises(RuntimeError, match=f"Refusing to run under {escalation_tool}") as exc_info:
        _ = parse_output(
            exec_as_user(
                command=[
                    escalation_tool,
                    "sh",
                    "-c",
                    f'COVERAGE_FILE="/coverage/.coverage" EDITOR=/bin/cat {TEMPER_EDIT_SHELL_COMMAND} /etc/motd',
                ],
                container=container,
            )
        )

    assert exc_info.value.args[1] == 11
