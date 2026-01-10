# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex
import textwrap
import uuid

import pytest
from docker.models.containers import ExecResult
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.masks import supermasks
from tests.utils import parse_output


def stat_file(container: DockerContainer, filename: str) -> tuple[int, str, str]:
    stat_result = parse_output(container.exec(["stat", "-c", "%u %U %f", filename]))
    uid, username, file_perms_hex = stat_result.split()
    file_perms = oct(int(file_perms_hex, 16))

    return int(uid), username, file_perms


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
        container.exec(["sh", "-c", f'EDITOR="/tmp/edit-file {content}" temper-edit {filename}'])

        uid, username, file_perms = stat_file(container=container, filename=filename)
        assert (uid, username) == (0, "root"), f"Wrong file ownership for mode {octal}"
        assert file_perms.endswith(octal), f"Mismatched permissions for mode {octal}"
        assert parse_output(container.exec(["cat", filename])) == content, f"Wrong file content for mode {octal}"


def exec_as_user(command: list[str], container: DockerContainer, user: str = "user") -> ExecResult:
    return container.exec(["su", "-", user, "-c", shlex.join(command)])  # type: ignore[no-any-return]


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
            command=["sh", "-c", f'EDITOR="/tmp/edit-file {content}" temper-edit {filename}'], container=container
        )

        uid, username, file_perms = stat_file(container=container, filename=filename)
        assert (uid, username) == (1000, "user"), f"Wrong file ownership for mode {octal}"
        assert file_perms.endswith(octal), f"Mismatched permissions for mode {octal}"
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
    with pytest.raises(RuntimeError, match="Permission denied"):
        _ = parse_output(
            exec_as_user(
                command=["sh", "-c", f'EDITOR="/tmp/edit-file {content}" temper-edit {filename}'], container=container
            )
        )

    uid, username, file_perms = stat_file(container=container, filename=filename)
    assert (uid, username) == (0, "root"), "Wrong file ownership"
    assert file_perms.endswith("644"), "Wrong file permissions"
    assert parse_output(container.exec(["cat", filename])) == "", "Wrong file content"
