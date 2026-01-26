# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from docker.models.containers import ExecResult
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

PYTHON_BINARY = "/usr/local/bin/python"
TEMPER_EDIT_BINARY = "/usr/local/bin/temper-edit"
TEMPER_EDIT_COMMAND = [
    PYTHON_BINARY,
    "-m",
    "coverage",
    "run",
    "--parallel-mode",
    "--rcfile",
    "/app/pyproject.toml",
    "--source",
    "/app/temper_edit",
    TEMPER_EDIT_BINARY,
]
TEMPER_EDIT_SHELL_COMMAND = shlex.join(TEMPER_EDIT_COMMAND)


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


@dataclass(frozen=True)
class FileStat:
    mode: str
    uid: int
    username: str
    gid: int
    groupname: str

    @property
    def user(self) -> tuple[int, str]:
        return (self.uid, self.username)

    @property
    def group(self) -> tuple[int, str]:
        return (self.gid, self.groupname)


def stat_file(container: DockerContainer, filename: str) -> FileStat:
    stat_result = parse_output(container.exec(["stat", "--format", "%u %U %g %G %f", filename]))
    uid, username, gid, groupname, file_perms_hex = stat_result.split()
    mode = oct(int(file_perms_hex, 16))

    return FileStat(mode=mode, uid=int(uid), username=username, gid=int(gid), groupname=groupname)


def get_mtime_ns(container: DockerContainer, filename: str) -> float:
    """Get modification time with nanosecond resolution using GNU stat."""
    return float(parse_output(container.exec(["stat", "--format", "%.9Y", filename])))


def exec_as_user(command: list[str], container: DockerContainer, user: str = "user") -> ExecResult:
    return container.exec(["su", "-", user, "-c", f'COVERAGE_FILE="/coverage/.coverage" {shlex.join(command)}'])  # type: ignore[no-any-return]
