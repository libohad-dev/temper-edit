# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile, _TemporaryFileWrapper
from types import TracebackType
from typing import Literal

try:
    from typing import Self as SandboxedFileT
except ImportError:
    SandboxedFileT = "SandboxedFile"  # type: ignore [assignment]

from pydantic import BaseModel, ConfigDict


class SandboxedFile(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    filename: Path
    tempfile: _TemporaryFileWrapper  # type: ignore [type-arg]

    def __enter__(self) -> _TemporaryFileWrapper:  # type: ignore [type-arg]
        self.tempfile.__enter__()
        shutil.copyfile(self.filename, self.tempfile.name)
        return self.tempfile

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> Literal[False]:
        self.tempfile.__exit__(exc_type, exc_value, traceback)
        shutil.copymode(self.filename, self.tempfile.name)
        shutil.move(self.tempfile.name, self.filename)

        return False

    @classmethod
    def spawn(cls, filename: Path) -> SandboxedFileT:
        return cls(filename=filename, tempfile=NamedTemporaryFile(delete=False))
