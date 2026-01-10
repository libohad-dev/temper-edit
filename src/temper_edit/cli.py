# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess
from collections.abc import Container, Mapping
from logging import getLogger
from pathlib import Path
from typing import TypeVar

from .config import EditorConfig

logger = getLogger(__name__)

K = TypeVar("K")
V = TypeVar("V")


def keep_keys(d: Mapping[K, V], keys: Container[K]) -> dict[K, V]:
    return {k: v for k, v in d.items() if k in keys}


def main(filename: Path, editor_config: EditorConfig) -> subprocess.CompletedProcess[bytes]:
    from .atomic_edit import SandboxedFile
    from .editor import select_editor

    editor = select_editor(editor_config)

    with SandboxedFile.spawn(filename=filename) as sandboxed_file:
        res = subprocess.run(editor + [sandboxed_file.name], capture_output=True)

    if res.returncode != 0:
        raise RuntimeError(b"stderr: " + res.stderr + b" stdout: " + res.stdout, res.returncode)
    else:
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
    editor_config = EditorConfig.model_validate(env_config)

    main(filename=args.filename, editor_config=editor_config)
