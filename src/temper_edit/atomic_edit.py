# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import filecmp
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile, _TemporaryFileWrapper
from types import TracebackType
from typing import Literal


@dataclass
class SandboxedFile:
    filename: Path

    def __post_init__(self) -> None:
        self.tempfile = NamedTemporaryFile(delete=False)  # noqa: SIM115

    @property
    def _orig_path(self) -> str:
        return self.tempfile.name + ".orig"

    def stage_file(self) -> None:
        shutil.copyfile(self.filename, self.tempfile.name)
        shutil.copyfile(self.tempfile.name, self._orig_path)

    def commit_file(self) -> None:
        original_file_stat = self.filename.stat()
        Path(self.tempfile.name).chmod(0o000)
        shutil.chown(self.tempfile.name, user=original_file_stat.st_uid, group=original_file_stat.st_gid)
        shutil.copymode(self.filename, self.tempfile.name)
        shutil.move(self.tempfile.name, self.filename)

    def __enter__(self) -> _TemporaryFileWrapper:  # type: ignore [type-arg]
        self.tempfile.__enter__()
        self.stage_file()
        return self.tempfile

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None
    ) -> Literal[False]:
        self.tempfile.__exit__(exc_type, exc_value, traceback)

        try:
            if exc_type is None:
                content_changed = not filecmp.cmp(self.tempfile.name, self._orig_path, shallow=False)
                if content_changed:
                    self.commit_file()
                else:
                    Path(self.tempfile.name).unlink()
        finally:
            Path(self._orig_path).unlink(missing_ok=True)

        return False
