# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import filecmp
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

    @property
    def _orig_path(self) -> str:
        return self.tempfile.name + ".orig"

    def __enter__(self) -> _TemporaryFileWrapper:  # type: ignore [type-arg]
        self.tempfile.__enter__()
        shutil.copyfile(self.filename, self.tempfile.name)
        shutil.copyfile(self.tempfile.name, self._orig_path)
        return self.tempfile

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> Literal[False]:
        self.tempfile.__exit__(exc_type, exc_value, traceback)

        if exc_type is None:
            content_changed = not filecmp.cmp(self.tempfile.name, self._orig_path, shallow=False)
            if content_changed:
                shutil.copymode(self.filename, self.tempfile.name)
                shutil.move(self.tempfile.name, self.filename)
            else:
                Path(self.tempfile.name).unlink()
            Path(self._orig_path).unlink()

        return False

    @classmethod
    def spawn(cls, filename: Path) -> SandboxedFileT:
        return cls(filename=filename, tempfile=NamedTemporaryFile(delete=False))
