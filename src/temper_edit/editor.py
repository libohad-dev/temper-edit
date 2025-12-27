# SPDX-FileCopyrightText: 2025 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex

from .config import EditorConfig
from .exceptions import ConfigError


def select_editor(editor_config: EditorConfig) -> list[str]:
    if editor_config.SUDO_EDITOR is not None:
        raw_editor = editor_config.SUDO_EDITOR
    elif editor_config.VISUAL is not None:
        raw_editor = editor_config.VISUAL
    elif editor_config.EDITOR is not None:
        raw_editor = editor_config.EDITOR
    else:
        raise ConfigError("No editor configured")

    return shlex.split(raw_editor)
