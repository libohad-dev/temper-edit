# SPDX-FileCopyrightText: 2025 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later


from pydantic import BaseModel, ConfigDict


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(
        # keep-sorted start
        extra="forbid",
        frozen=True,
        strict=True,
        validate_assignment=True,
        validate_by_alias=True,
        validate_by_name=True,
        validate_default=True,
        validate_return=True,
        # keep-sorted end
    )
