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
    with pytest.raises(RuntimeError, match="Editor failed. Temporary file preserved at:") as exc_info:
        _ = parse_output(
            container.exec(
                [
                    "sh",
                    "-c",
                    f'TMPDIR="{custom_tmpdir}" EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} {filename}',
                ]
            )
        )

    # Verify temporary file was created in the custom tmpdir, preserved, and contains the expected content
    tempfile = extract_preserved_temporary_filename(exc_info)
    assert list_container_files(container=container, directory="/tmp") == {
        "/tmp/file.txt",
        "/tmp/edit-file",
        custom_tmpdir,
    }
    assert list_container_files(container=container, directory=custom_tmpdir) == {tempfile}
    assert parse_output(container.exec(["cat", tempfile])) == content, "Preserved temp file has wrong content"


def test_missing_tmpdir_envvar_falls_back_to_tmp(container: DockerContainer) -> None:
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
    with pytest.raises(RuntimeError, match="Editor failed. Temporary file preserved at:") as exc_info:
        _ = parse_output(
            container.exec(
                [
                    "sh",
                    "-c",
                    f'TMPDIR="/tmp/does-not-exist" EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} {filename}',
                ]
            )
        )

    # Verify temporary file was preserved and contains the expected content
    tempfile = extract_preserved_temporary_filename(exc_info)
    assert list_container_files(container=container, directory="/tmp") == {"/tmp/file.txt", "/tmp/edit-file", tempfile}
    assert parse_output(container.exec(["cat", tempfile])) == content, "Preserved temp file has wrong content"


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
    with pytest.raises(RuntimeError, match="Editor failed. Temporary file preserved at:") as exc_info:
        _ = parse_output(
            container.exec(
                [
                    "sh",
                    "-c",
                    f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} --tmpdir {custom_tmpdir} {filename}',
                ]
            )
        )

    # Verify temporary file was created in the custom tmpdir, preserved, and contains the expected content
    tempfile = extract_preserved_temporary_filename(exc_info)
    assert list_container_files(container=container, directory="/tmp") == {
        "/tmp/file.txt",
        "/tmp/edit-file",
        custom_tmpdir,
    }
    assert list_container_files(container=container, directory=custom_tmpdir) == {tempfile}
    assert parse_output(container.exec(["cat", tempfile])) == content, "Preserved temp file has wrong content"


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
        match=r"FileNotFoundError: \[Errno 2\] No such file or directory: \\'/tmp/does-not-exist/",
    ):
        _ = parse_output(
            container.exec(
                [
                    "sh",
                    "-c",
                    f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} --tmpdir /tmp/does-not-exist {filename}',
                ]
            )
        )

    # Verify no temporary file was created
    assert list_container_files(container=container, directory="/tmp") == {"/tmp/file.txt", "/tmp/edit-file"}
