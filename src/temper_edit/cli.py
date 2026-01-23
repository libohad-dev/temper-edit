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

    with SandboxedFile.spawn(filename=filename) as sandboxed_file:
        res = subprocess.run(editor + [sandboxed_file.name], capture_output=True)
        if res.returncode != 0:
            print(f"Temporary file preserved at: {sandboxed_file.name}", file=sys.stderr)
            raise RuntimeError(b"stderr: " + res.stderr + b" stdout: " + res.stdout, res.returncode)

    return res


def run() -> None:
    import argparse
    import json
    import os

    from .config import ENVVARS

    parser = argparse.ArgumentParser("Edit a file atomically")
    parser.add_argument("filename", type=Path, help="File to edit")

    args = parser.parse_args()

    logger.debug("Looking for relevant environment variables", extra=dict(envvars=sorted(ENVVARS)))
    env_config = keep_keys(os.environ, ENVVARS)
    logger.debug("Loaded environment variables", extra=dict(env_config=json.dumps(env_config)))
    editor_config = EditorConfig.from_env(env_config)

    main(filename=args.filename, editor_config=editor_config)
