# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex
import textwrap
import uuid

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.utils import (
    TEMPER_EDIT_SHELL_COMMAND,
    check_exception_content,
    exec_as_user,
    extract_log_filename,
    extract_preserved_temporary_filename,
    list_container_files,
    parse_output,
)


def test_tmpdir_envvar_is_respected(container: DockerContainer) -> None:
    # Fail after editing the temporary file
    script = textwrap.dedent("""\
    #! /bin/sh
    echo "$1" > "$2"
    exit 1
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])

    filename = "/tmp/file.txt"
    container.exec(["touch", filename])

    custom_tmpdir = "/tmp/custom-tmpdir"
    container.exec(["mkdir", "-p", custom_tmpdir])

    content = str(uuid.uuid4())
    with pytest.raises(RuntimeError, check=check_exception_content("Editor failed with exit code 1")) as exc_info:
        _ = parse_output(
            container.exec(
                [
                    "sh",
                    "-c",
                    f'TMPDIR="{custom_tmpdir}" EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} {filename}',
                ]
            )
        )

    assert exc_info.value.args[1] == 30

    # Verify temporary file was created in the custom tmpdir, preserved, and contains the expected content
    tempfile = extract_preserved_temporary_filename(exc_info)
    log_file = extract_log_filename(exc_info)
    assert list_container_files(container=container, directory="/tmp") == {
        "/tmp/file.txt",
        "/tmp/edit-file",
        custom_tmpdir,
    }
    assert list_container_files(container=container, directory=custom_tmpdir) == {tempfile, log_file}
    assert parse_output(container.exec(["cat", tempfile])) == content, "Preserved temp file has wrong content"

    # Verify log file contains traceback
    log_content = parse_output(container.exec(["cat", log_file]))
    assert "Traceback" in log_content


def test_envvar_tmpdir_must_exist(container: DockerContainer) -> None:
    # Fail after editing the temporary file
    script = textwrap.dedent("""\
    #! /bin/sh
    echo "$1" > "$2"
    exit 1
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])

    filename = "/tmp/file.txt"
    container.exec(["touch", filename])

    content = str(uuid.uuid4())
    with pytest.raises(
        RuntimeError,
        check=check_exception_content("Temporary directory does not exist: /tmp/does-not-exist\n"),
    ) as exc_info:
        _ = parse_output(
            container.exec(
                [
                    "sh",
                    "-c",
                    f'TMPDIR="/tmp/does-not-exist" EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} {filename}',
                ]
            )
        )

    assert exc_info.value.args[1] == 10

    # Verify no temporary file was created
    assert list_container_files(container=container, directory="/tmp") == {"/tmp/file.txt", "/tmp/edit-file"}


def test_envvar_tmpdir_must_be_writable(container: DockerContainer) -> None:
    # Fail after editing the temporary file
    script = textwrap.dedent("""\
    #! /bin/sh
    echo "$1" > "$2"
    exit 1
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chmod", "a+x", "/tmp/edit-file"])

    filename = "/tmp/file.txt"
    container.exec(["touch", filename])

    custom_tmpdir = "/tmp/custom-tmpdir"
    container.exec(["mkdir", "-p", custom_tmpdir])

    content = str(uuid.uuid4())
    with pytest.raises(
        RuntimeError,
        check=check_exception_content("Temporary directory is not writable: /tmp/custom-tmpdir\n"),
    ) as exc_info:
        _ = parse_output(
            exec_as_user(
                command=[
                    "sh",
                    "-c",
                    f'TMPDIR="{custom_tmpdir}" EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} {filename}',
                ],
                container=container,
            )
        )

    assert exc_info.value.args[1] == 10

    # Verify no temporary file was created
    assert list_container_files(container=container, directory="/tmp") == {
        "/tmp/file.txt",
        "/tmp/edit-file",
        custom_tmpdir,
    }
    assert list_container_files(container=container, directory=custom_tmpdir) == set()


def test_tmpdir_cli_argument(container: DockerContainer) -> None:
    # Fail after editing the temporary file
    script = textwrap.dedent("""\
    #! /bin/sh
    echo "$1" > "$2"
    exit 1
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])

    filename = "/tmp/file.txt"
    container.exec(["touch", filename])

    custom_tmpdir = "/tmp/custom-tmpdir"
    container.exec(["mkdir", "-p", custom_tmpdir])

    content = str(uuid.uuid4())
    with pytest.raises(RuntimeError, check=check_exception_content("Editor failed with exit code 1")) as exc_info:
        _ = parse_output(
            container.exec(
                [
                    "sh",
                    "-c",
                    f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} --tmpdir {custom_tmpdir} {filename}',
                ]
            )
        )

    assert exc_info.value.args[1] == 30

    # Verify temporary file was created in the custom tmpdir, preserved, and contains the expected content
    tempfile = extract_preserved_temporary_filename(exc_info)
    log_file = extract_log_filename(exc_info)
    assert list_container_files(container=container, directory="/tmp") == {
        "/tmp/file.txt",
        "/tmp/edit-file",
        custom_tmpdir,
    }
    assert list_container_files(container=container, directory=custom_tmpdir) == {tempfile, log_file}
    assert parse_output(container.exec(["cat", tempfile])) == content, "Preserved temp file has wrong content"

    # Verify log file contains traceback
    log_content = parse_output(container.exec(["cat", log_file]))
    assert "Traceback" in log_content


def test_cli_tmpdir_must_exist(container: DockerContainer) -> None:
    # Fail after editing the temporary file
    script = textwrap.dedent("""\
    #! /bin/sh
    echo "$1" > "$2"
    exit 1
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])

    filename = "/tmp/file.txt"
    container.exec(["touch", filename])

    content = str(uuid.uuid4())
    with pytest.raises(
        RuntimeError,
        check=check_exception_content("Temporary directory does not exist: /tmp/does-not-exist\n"),
    ) as exc_info:
        _ = parse_output(
            container.exec(
                [
                    "sh",
                    "-c",
                    f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} --tmpdir /tmp/does-not-exist {filename}',
                ]
            )
        )

    assert exc_info.value.args[1] == 10

    # Verify no temporary file was created
    assert list_container_files(container=container, directory="/tmp") == {"/tmp/file.txt", "/tmp/edit-file"}


def test_cli_tmpdir_must_be_writable(container: DockerContainer) -> None:
    # Fail after editing the temporary file
    script = textwrap.dedent("""\
    #! /bin/sh
    echo "$1" > "$2"
    exit 1
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chmod", "a+x", "/tmp/edit-file"])

    filename = "/tmp/file.txt"
    container.exec(["touch", filename])

    custom_tmpdir = "/tmp/custom-tmpdir"
    container.exec(["mkdir", "-p", custom_tmpdir])

    content = str(uuid.uuid4())
    with pytest.raises(
        RuntimeError,
        check=check_exception_content("Temporary directory is not writable: /tmp/custom-tmpdir\n"),
    ) as exc_info:
        _ = parse_output(
            exec_as_user(
                command=[
                    "sh",
                    "-c",
                    f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} --tmpdir {custom_tmpdir} {filename}',
                ],
                container=container,
            )
        )

    assert exc_info.value.args[1] == 10

    # Verify no temporary file was created
    assert list_container_files(container=container, directory="/tmp") == {
        "/tmp/file.txt",
        "/tmp/edit-file",
        custom_tmpdir,
    }
    assert list_container_files(container=container, directory=custom_tmpdir) == set()


def test_cli_tmpdir_has_higher_priority_than_envvar(container: DockerContainer) -> None:
    # Fail after editing the temporary file
    script = textwrap.dedent("""\
    #! /bin/sh
    echo "$1" > "$2"
    exit 1
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])

    filename = "/tmp/file.txt"
    container.exec(["touch", filename])

    cli_tmpdir = "/tmp/cli-tmpdir"
    envvar_tmpdir = "/tmp/envvar-tmpdir"
    container.exec(["mkdir", "-p", cli_tmpdir])
    container.exec(["mkdir", "-p", envvar_tmpdir])

    content = str(uuid.uuid4())
    with pytest.raises(RuntimeError, check=check_exception_content("Editor failed with exit code 1")) as exc_info:
        _ = parse_output(
            container.exec(
                [
                    "sh",
                    "-c",
                    f'TMPDIR="{envvar_tmpdir}" EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} --tmpdir {cli_tmpdir} {filename}',
                ]
            )
        )

    assert exc_info.value.args[1] == 30

    # Verify temporary file was created in the CLI custom tmpdir, preserved, and contains the expected content
    tempfile = extract_preserved_temporary_filename(exc_info)
    log_file = extract_log_filename(exc_info)
    assert list_container_files(container=container, directory="/tmp") == {
        "/tmp/file.txt",
        "/tmp/edit-file",
        cli_tmpdir,
        envvar_tmpdir,
    }
    assert list_container_files(container=container, directory=cli_tmpdir) == {tempfile, log_file}
    assert list_container_files(container=container, directory=envvar_tmpdir) == set()
    assert parse_output(container.exec(["cat", tempfile])) == content, "Preserved temp file has wrong content"

    # Verify log file contains traceback
    log_content = parse_output(container.exec(["cat", log_file]))
    assert "Traceback" in log_content
