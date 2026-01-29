# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess
import sys
from collections.abc import Mapping
from functools import partial
from logging import getLogger
from pathlib import Path
from typing import Protocol

from .atomic_edit import ElevatedPermissionSandbox, FileSandbox, LocalFSSandbox
from .config import EditorConfig
from .utils import keep_keys

logger = getLogger(__name__)


class SandboxFactory(Protocol):
    def __call__(self, filename: Path, tmpdir: Path | None) -> FileSandbox: ...


# Mapping of environment variables set by privilege escalation tools to their program names
ESCALATION_ENVVARS: dict[str, str] = {
    "SUDO_USER": "sudo",
    "DOAS_USER": "doas",
    "PKEXEC_UID": "pkexec",  # Note: pkexec rejection is not tested in the alpine-based images
}


def detect_privilege_escalation(environ: Mapping[str, str]) -> str | None:
    """
    Detect if running under a privilege escalation tool.

    Returns the name of the escalation program if detected, None otherwise.
    Note: pkexec detection is not tested in the alpine-based test images.
    """
    for envvar, program in ESCALATION_ENVVARS.items():
        if envvar in environ:
            return program
    return None


def main(
    filename: Path,
    editor_config: EditorConfig,
    tmpdir: Path | None,
    sandbox_factory: SandboxFactory,
) -> subprocess.CompletedProcess[bytes]:
    from .editor import select_editor

    editor = select_editor(editor_config)

    sandbox = sandbox_factory(filename=filename, tmpdir=tmpdir)
    try:
        with sandbox as sandboxed_file:
            res = subprocess.run(editor + [sandboxed_file.name], capture_output=True)
            if res.returncode != 0:
                print(f"Editor failed. Temporary file preserved at: {sandboxed_file.name}", file=sys.stderr)
                raise RuntimeError(b"stderr: " + res.stderr + b" stdout: " + res.stdout, res.returncode)
    except OSError as e:
        print(
            f"Failed to update file: {filename}. Temporary file preserved at: {sandbox.tempfile.name}",
            file=sys.stderr,
        )
        raise

    return res


def run() -> None:
    import argparse
    import json
    import os

    from .config import ENVVARS

    if escalation_program := detect_privilege_escalation(os.environ):
        print(
            f"Refusing to run under {escalation_program}.\n"
            f"To edit files requiring elevated permissions, use: temper-edit --elevate {escalation_program} <filename>",
            file=sys.stderr,
        )
        sys.exit(1)

    parser = argparse.ArgumentParser("Edit a file atomically")
    parser.add_argument("filename", type=Path, help="File to edit")
    parser.add_argument("--tmpdir", default=os.environ.get("TMPDIR"), type=Path, help="Directory for temporary files")
    parser.add_argument("--elevate", help="Privilege escalation program to use (e.g., sudo, doas)")

    args = parser.parse_args()

    logger.debug("Looking for relevant environment variables", extra=dict(envvars=sorted(ENVVARS)))
    env_config = keep_keys(os.environ, ENVVARS)
    logger.debug("Loaded environment variables", extra=dict(env_config=json.dumps(env_config)))
    editor_config = EditorConfig.from_env(env_config)

    sandbox_factory: SandboxFactory = (
        LocalFSSandbox  # type: ignore[assignment]
        if args.elevate is None
        else partial(ElevatedPermissionSandbox, escalation_program=[args.elevate])
    )
    main(filename=args.filename, editor_config=editor_config, tmpdir=args.tmpdir, sandbox_factory=sandbox_factory)
