# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import shlex
import subprocess
import sys
import traceback
from collections.abc import Mapping
from logging import getLogger
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import NoReturn

from .atomic_edit import FileSandbox, LocalFSSandbox, make_elevated_permissions_sandbox
from .config import EditorConfig
from .exceptions import EditorError, PrivilegeEscalationError, TemperError
from .utils import keep_keys

logger = getLogger(__name__)


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


def _handle_error(e: TemperError) -> NoReturn:
    print(str(e), file=sys.stderr)
    sys.exit(e.exit_code)


def _handle_sandbox_error(e: TemperError, tempfile_path: str) -> NoReturn:
    print(str(e), file=sys.stderr)
    if Path(tempfile_path).exists():
        print(f"Temporary file preserved at: {tempfile_path}", file=sys.stderr)
    log_path = tempfile_path + ".log"
    Path(log_path).write_text(traceback.format_exc())
    print(f"Complete error log available at: {log_path}", file=sys.stderr)
    sys.exit(e.exit_code)


def _handle_unexpected_error(e: Exception) -> NoReturn:  # pragma: no cover
    with NamedTemporaryFile(delete=False, suffix=".log", prefix="temper-edit-", mode="w") as log_file:
        log_file.write(traceback.format_exc())
        log_path = log_file.name
    print(f"An unexpected error occurred: {e}", file=sys.stderr)
    print(f"Complete error log available at: {log_path}", file=sys.stderr)
    sys.exit(1)


def main(
    filename: Path,
    editor_config: EditorConfig,
    tmpdir: Path | None,
    sandbox_factory: type[FileSandbox],
) -> subprocess.CompletedProcess[bytes]:
    from .editor import select_editor

    try:
        editor = select_editor(editor_config)
    except TemperError as e:
        _handle_error(e)

    try:
        sandbox = sandbox_factory(filename=filename, tmpdir=tmpdir)
    except TemperError as e:
        _handle_error(e)

    try:
        with sandbox as sandboxed_file:
            try:
                res = subprocess.run(editor + [sandboxed_file.name])
            except FileNotFoundError as e:
                raise EditorError(f"Editor not found: {editor[0]}") from e
            if res.returncode != 0:
                raise EditorError(f"Editor failed with exit code {res.returncode}")
    except TemperError as e:
        _handle_sandbox_error(e, sandbox.tempfile.name)

    return res


def select_sandbox_implementation(args: argparse.Namespace) -> type[FileSandbox]:
    if args.s3 is not None:
        from temper_edit.s3 import make_s3_sandbox

        return make_s3_sandbox(bucket=args.s3, force=args.force)
    elif args.elevate is not None:
        return make_elevated_permissions_sandbox(escalation_program=shlex.split(args.elevate))
    else:
        return LocalFSSandbox


def run() -> None:
    import json
    import os

    from .config import ENVVARS

    if escalation_program := detect_privilege_escalation(os.environ):
        print(
            f"Refusing to run under {escalation_program}.\n"
            f"To edit files requiring elevated permissions, use: temper-edit --elevate {escalation_program} <filename>",
            file=sys.stderr,
        )
        sys.exit(PrivilegeEscalationError.exit_code)

    parser = argparse.ArgumentParser("Edit a file atomically")
    parser.add_argument("filename", type=Path, help="File to edit")
    parser.add_argument("--tmpdir", default=os.environ.get("TMPDIR"), type=Path, help="Directory for temporary files")
    sandbox_type = parser.add_mutually_exclusive_group(required=False)
    sandbox_type.add_argument("--elevate", help="Privilege escalation program to use (e.g., sudo, doas)")
    sandbox_type.add_argument(
        "--s3",
        metavar="BUCKET",
        help="Treat filename as an S3 key in the specified bucket",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite even if the object was modified (S3 only)",
    )
    args = parser.parse_args()

    logger.debug("Looking for relevant environment variables", extra=dict(envvars=sorted(ENVVARS)))
    env_config = keep_keys(os.environ, ENVVARS)
    logger.debug("Loaded environment variables", extra=dict(env_config=json.dumps(env_config)))
    editor_config = EditorConfig.from_env(env_config)

    try:
        sandbox_factory = select_sandbox_implementation(args)
    except TemperError as e:
        _handle_error(e)

    try:
        main(
            filename=args.filename,
            editor_config=editor_config,
            tmpdir=args.tmpdir,
            sandbox_factory=sandbox_factory,
        )
    except Exception as e:  # pragma: no cover
        _handle_unexpected_error(e)
