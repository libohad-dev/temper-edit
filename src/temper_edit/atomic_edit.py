# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from types import TracebackType

from pydantic import BaseModel


class SandboxedFile(BaseModel):
    filename: Path

    def __enter__(self) -> Path:
        return self.filename

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> bool | None:
        return None
