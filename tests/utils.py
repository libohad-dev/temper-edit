# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Callable
from typing import cast

from docker.models.containers import ExecResult


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
