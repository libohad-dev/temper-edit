# SPDX-FileCopyrightText: 2025 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import datetime
import os
from typing import Self

from .base_model import StrictBaseModel


class FileStat(StrictBaseModel):
    size: int
    mode: int
    user: int
    group: int
    mtime: datetime.datetime

    @classmethod
    def from_stat_results(cls, sr: os.stat_result) -> Self:
        return cls(
            size=sr.st_size,
            mode=sr.st_mode & 0o777,
            user=sr.st_uid,
            group=sr.st_gid,
            mtime=datetime.datetime.fromtimestamp(sr.st_mtime, tz=datetime.UTC),
        )
