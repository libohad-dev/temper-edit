# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Container, Mapping
from typing import TypeVar

K = TypeVar("K")
V = TypeVar("V")


def keep_keys(d: Mapping[K, V], keys: Container[K]) -> dict[K, V]:
    return {k: v for k, v in d.items() if k in keys}
