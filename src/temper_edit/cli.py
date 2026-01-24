# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess
import sys
from logging import getLogger
from pathlib import Path

from .config import EditorConfig
from .utils import keep_keys

logger = getLogger(__name__)


def main(filename: Path, editor_config: EditorConfig) -> subprocess.CompletedProcess[bytes]:
    from .atomic_edit import SandboxedFile
    from .editor import select_editor

    editor = select_editor(editor_config)

    sandbox = SandboxedFile.spawn(filename=filename)
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

    # Detect usage of privilege escalation tools: sudo, doas, pkexec
    # Note: pkexec rejection is not tested in the alpine-based images
    privilege_escalation_envvars = {"SUDO_USER", "DOAS_USER", "PKEXEC_UID"}
    if privilege_escalation_envvars & os.environ.keys():
        print("Refusing to run with escalated privileges", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser("Edit a file atomically")
    parser.add_argument("filename", type=Path, help="File to edit")

    args = parser.parse_args()

    logger.debug("Looking for relevant environment variables", extra=dict(envvars=sorted(ENVVARS)))
    env_config = keep_keys(os.environ, ENVVARS)
    logger.debug("Loaded environment variables", extra=dict(env_config=json.dumps(env_config)))
    editor_config = EditorConfig.from_env(env_config)

    main(filename=args.filename, editor_config=editor_config)
