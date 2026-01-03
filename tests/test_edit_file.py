# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex
import textwrap
import uuid

from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.masks import supermasks
from tests.utils import parse_output


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

        file_perms_hex = parse_output(container.exec(["stat", "-c", "%f", filename]))
        file_perms = oct(int(file_perms_hex, 16))
        assert file_perms.endswith(octal), f"Mismatched permissions for mode {octal}"
        assert parse_output(container.exec(["cat", filename])) == content, f"Wrong file content for mode {octal}"
