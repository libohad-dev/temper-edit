# SPDX-FileCopyrightText: 2025 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

from pydantic import ConfigDict

from .base_model import StrictBaseModel

ENV_CONFIGS: set[type["EnvvarModel"]] = set()


class EnvvarModel(StrictBaseModel):
    model_config = ConfigDict(extra="ignore")

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        ENV_CONFIGS.add(cls)


class EditorConfig(EnvvarModel):
    # keep-sorted start
    EDITOR: str | None = None
    SUDO_EDITOR: str | None = None
    VISUAL: str | None = None
    # keep-sorted end


ENVVARS = set().union(*(cfg.__pydantic_fields__ for cfg in ENV_CONFIGS))
