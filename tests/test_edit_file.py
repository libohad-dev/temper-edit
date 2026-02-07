# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex
import textwrap
import uuid

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.masks import supermasks
from tests.utils import (
    TEMPER_EDIT_SHELL_COMMAND,
    check_exception_content,
    exec_as_user,
    extract_log_filename,
    get_mtime_ns,
    list_container_files,
    parse_output,
    stat_file,
)


def test_root_user_update_file_and_preserve_permissions(container: DockerContainer) -> None:
    script = textwrap.dedent(f"""\
    #! /bin/sh
    echo "$1" > "$2"
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])

    for mask in supermasks(0o600, upper_bound=0o744):
        octal = oct(mask).removeprefix("0o")
        filename = f"/tmp/file{octal}"
        content = str(uuid.uuid4())
        container.exec(["touch", filename])
        container.exec(["chmod", octal, filename])
        container.exec(["sh", "-c", f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} {filename}'])

        stat = stat_file(container=container, filename=filename)
        assert stat.user == (0, "root"), f"Wrong file user ownership for mode {octal}"
        assert stat.group == (0, "root"), f"Wrong file group ownership for mode {octal}"
        assert stat.mode.endswith(octal), f"Mismatched permissions for mode {octal}"
        assert parse_output(container.exec(["cat", filename])) == content, f"Wrong file content for mode {octal}"


def test_root_user_update_user_owned_file_and_preserve_permissions(container: DockerContainer) -> None:
    script = textwrap.dedent(f"""\
    #! /bin/sh
    echo "$1" > "$2"
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])

    for mask in supermasks(0o600, upper_bound=0o744):
        octal = oct(mask).removeprefix("0o")
        filename = f"/tmp/file{octal}"
        content = str(uuid.uuid4())
        container.exec(["touch", filename])
        container.exec(["chmod", octal, filename])
        container.exec(["chown", "user:user", filename])
        container.exec(["sh", "-c", f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} {filename}'])

        stat = stat_file(container=container, filename=filename)
        assert stat.user == (1000, "user"), f"Wrong file user ownership for mode {octal}"
        assert stat.group == (1000, "user"), f"Wrong file group ownership for mode {octal}"
        assert stat.mode.endswith(octal), f"Mismatched permissions for mode {octal}"
        assert parse_output(container.exec(["cat", filename])) == content, f"Wrong file content for mode {octal}"


def test_non_root_user_update_file_and_preserve_permissions(container: DockerContainer) -> None:
    script = textwrap.dedent(f"""\
    #! /bin/sh
    echo "$1" > "$2"
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chown", "user:user", "/tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])

    for mask in supermasks(0o600, upper_bound=0o744):
        octal = oct(mask).removeprefix("0o")
        filename = f"/tmp/file{octal}"
        content = str(uuid.uuid4())
        container.exec(["touch", filename])
        container.exec(["chmod", octal, filename])
        container.exec(["chown", "user:user", filename])
        exec_as_user(
            command=["sh", "-c", f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} {filename}'],
            container=container,
        )

        stat = stat_file(container=container, filename=filename)
        assert stat.user == (1000, "user"), f"Wrong file user ownership for mode {octal}"
        assert stat.group == (1000, "user"), f"Wrong file group ownership for mode {octal}"
        assert stat.mode.endswith(octal), f"Mismatched permissions for mode {octal}"
        assert parse_output(container.exec(["cat", filename])) == content, f"Wrong file content for mode {octal}"


def test_non_root_user_cannot_update_root_owned_file(container: DockerContainer) -> None:
    script = textwrap.dedent(f"""\
    #! /bin/sh
    echo "$1" > "$2"
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chown", "user:user", "/tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])

    filename = "/tmp/file.txt"
    content = str(uuid.uuid4())
    container.exec(["touch", filename])
    with pytest.raises(RuntimeError, check=check_exception_content("Permission denied while committing")) as exc_info:
        _ = parse_output(
            exec_as_user(
                command=["sh", "-c", f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} {filename}'],
                container=container,
            )
        )

    assert exc_info.value.args[1] == 41

    stat = stat_file(container=container, filename=filename)
    assert stat.user == (0, "root"), "Wrong file user ownership"
    assert stat.group == (0, "root"), "Wrong file group ownership"
    assert stat.mode.endswith("644"), "Wrong file permissions"
    assert parse_output(container.exec(["cat", filename])) == "", "Wrong file content"


def test_non_root_user_cannot_access_unreadable_file(container: DockerContainer) -> None:
    script = textwrap.dedent("""\
    #! /bin/sh
    echo "$1" > "$2"
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chown", "user:user", "/tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])

    filename = "/tmp/unreadable.txt"
    original_content = "original content"
    content = str(uuid.uuid4())
    container.exec(["sh", "-c", f"echo '{original_content}' > {filename}"])
    container.exec(["chown", "user:user", filename])
    container.exec(["chmod", "000", filename])

    mtime_before = get_mtime_ns(container=container, filename=filename)

    with pytest.raises(
        RuntimeError, check=check_exception_content("Permission denied: /tmp/unreadable.txt")
    ) as exc_info:
        _ = parse_output(
            exec_as_user(
                command=["sh", "-c", f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} {filename}'],
                container=container,
            )
        )

    assert exc_info.value.args[1] == 22

    mtime_after = get_mtime_ns(container=container, filename=filename)

    # Staging errors clean up the tempfile, but a log file is still written
    log_file = extract_log_filename(exc_info)
    log_content = parse_output(container.exec(["cat", log_file]))
    assert "Traceback" in log_content
    assert list_container_files(container, "/tmp") == {"/tmp/edit-file", filename, log_file}

    stat = stat_file(container=container, filename=filename)
    assert stat.user == (1000, "user"), "Wrong file user ownership"
    assert stat.group == (1000, "user"), "Wrong file group ownership"
    assert stat.mode.endswith("000"), "Wrong file permissions"
    assert parse_output(container.exec(["cat", filename])) == "original content", "Wrong file content"
    assert mtime_after == mtime_before, "File mtime should not have changed"
