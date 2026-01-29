# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import filecmp
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile, _TemporaryFileWrapper
from types import TracebackType
from typing import Literal


def commit_file_steps(source: Path, target: Path) -> Iterator[str]:
    """
    Perform a secure and atomic update, using `source` to replace `target` while
    preserving the `target` file's ownership and permissions.
    """
    target_file_stat = target.stat()
    source.chmod(0o000)
    yield "strip permissions"
    shutil.chown(source, user=target_file_stat.st_uid, group=target_file_stat.st_gid)
    yield "change ownership"
    shutil.copymode(target, source)
    yield "copy permissions"
    shutil.move(source, target)


@dataclass(kw_only=True)
class FileSandbox(ABC):
    """Abstract base class for sandboxed file editing."""

    filename: Path
    tmpdir: Path | None = None

    def __post_init__(self) -> None:
        self.tempfile = NamedTemporaryFile(dir=self.tmpdir, delete=False)  # noqa: SIM115

    @property
    def _orig_path(self) -> str:
        return self.tempfile.name + ".orig"

    @abstractmethod
    def stage_file(self) -> None:  # pragma: no cover
        raise NotImplementedError()

    @abstractmethod
    def commit_file(self) -> None:  # pragma: no cover
        raise NotImplementedError()

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


@dataclass
class LocalFSSandbox(FileSandbox):
    """Sandbox for editing files from a local filesystem."""

    def stage_file(self) -> None:
        shutil.copyfile(self.filename, self.tempfile.name)
        shutil.copyfile(self.tempfile.name, self._orig_path)

    def commit_file(self) -> None:
        """Execute all commit steps."""
        for _ in commit_file_steps(Path(self.tempfile.name), self.filename):
            pass


@dataclass
class ElevatedPermissionSandbox(FileSandbox):
    """Sandbox that uses privilege escalation for root-owned files."""

    escalation_program: list[str]

    def _run_privileged(self, args: list[str]) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(self.escalation_program + args, capture_output=True, check=True)

    def stage_file(self) -> None:
        result = self._run_privileged(["cat", "--", str(self.filename)])
        Path(self.tempfile.name).write_bytes(result.stdout)
        shutil.copyfile(self.tempfile.name, self._orig_path)

    def commit_file(self) -> None:
        Path(self.tempfile.name).chmod(0o000)
        self._run_privileged(["chown", "--reference", str(self.filename), self.tempfile.name])
        self._run_privileged(["chmod", "--reference", str(self.filename), self.tempfile.name])
        self._run_privileged(["mv", "--force", "--", self.tempfile.name, str(self.filename)])
