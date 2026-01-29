# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex
import textwrap
import uuid

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.masks import supermasks
from tests.utils import TEMPER_EDIT_SHELL_COMMAND, exec_as_user, parse_output, stat_file


@pytest.mark.parametrize("escalation_tool", ["sudo", "doas"])
def test_user_with_elevated_privileges_update_root_owned_file(container: DockerContainer, escalation_tool: str) -> None:
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
        parse_output(
            exec_as_user(
                command=[
                    "sh",
                    "-c",
                    f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} --elevate {escalation_tool} {filename}',
                ],
                container=container,
            )
        )

        stat = stat_file(container=container, filename=filename)
        assert stat.user == (0, "root"), f"Wrong file user ownership for mode {octal}"
        assert stat.group == (0, "root"), f"Wrong file group ownership for mode {octal}"
        assert stat.mode.endswith(octal), f"Mismatched permissions for mode {octal}"
        assert parse_output(container.exec(["cat", filename])) == content, f"Wrong file content for mode {octal}"
