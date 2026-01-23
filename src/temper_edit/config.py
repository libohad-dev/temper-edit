# SPDX-FileCopyrightText: 2025 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass, fields

from .utils import keep_keys

try:
    from typing import Self as EditorConfigT
except ImportError:
    EditorConfigT = "EditorConfig"  # type: ignore [assignment]


@dataclass(frozen=True)
class EditorConfig:
    # keep-sorted start
    EDITOR: str | None = None
    SUDO_EDITOR: str | None = None
    VISUAL: str | None = None
    # keep-sorted end

    @classmethod
    def from_env(cls, env: dict[str, str]) -> EditorConfigT:
        return cls(**keep_keys(env, {f.name for f in fields(cls)}))


ENVVARS = {f.name for f in fields(EditorConfig)}
