# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex
from collections.abc import Callable
from typing import cast

from docker.models.containers import ExecResult
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

TEMPER_EDIT_BINARY = "/app/.venv/bin/temper-edit"


def parse_output(res: ExecResult) -> str:
    if res.exit_code != 0:
        raise RuntimeError(res.output, res.exit_code)
    else:
        return cast(bytes, res.output).decode("utf-8").strip()


def check_exception_content(subst: str) -> Callable[[RuntimeError], bool]:
    def checker(exc: RuntimeError) -> bool:
        exc_content = exc.args[0].decode("utf-8")
        return subst in exc_content

    return checker


def stat_file(container: DockerContainer, filename: str) -> tuple[int, str, str]:
    stat_result = parse_output(container.exec(["stat", "--format", "%u %U %f", filename]))
    uid, username, file_perms_hex = stat_result.split()
    file_perms = oct(int(file_perms_hex, 16))

    return int(uid), username, file_perms


def get_mtime_ns(container: DockerContainer, filename: str) -> float:
    """Get modification time with nanosecond resolution using GNU stat."""
    return float(parse_output(container.exec(["stat", "--format", "%.9Y", filename])))


def exec_as_user(command: list[str], container: DockerContainer, user: str = "user") -> ExecResult:
    return container.exec(["su", "-", user, "-c", shlex.join(command)])  # type: ignore[no-any-return]
