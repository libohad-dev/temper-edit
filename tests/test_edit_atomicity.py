# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex
import textwrap
import uuid

from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.utils import exec_as_user, parse_output, stat_file


def test_original_file_is_not_modified_midway(container: DockerContainer) -> None:
    filename = "/tmp/file.txt"

    # Manually check on the original file along the way
    script = textwrap.dedent(f"""\
    #! /bin/sh
    cp "{filename}" /tmp/pre-edit
    echo "$1" > "$2"
    cp "{filename}" /tmp/post-edit
    """)

    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chown", "user:user", "/tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])

    content = str(uuid.uuid4())
    container.exec(["touch", filename])
    container.exec(["chown", "user:user", filename])
    parse_output(
        exec_as_user(
            command=["sh", "-c", f'EDITOR="/tmp/edit-file {content}" temper-edit {filename}'], container=container
        )
    )

    uid, username, file_perms = stat_file(container=container, filename=filename)
    assert (uid, username) == (1000, "user"), "Wrong file ownership"
    assert file_perms.endswith("644"), "Wrong file permissions"
    assert parse_output(container.exec(["cat", filename])) == content, "Wrong file content"

    for fn in ["/tmp/pre-edit", "/tmp/post-edit"]:
        assert parse_output(container.exec(["cat", fn])) == "", f"Wrong file content in {fn}"
