# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Iterator


def submasks(mask: int) -> Iterator[int]:
    submask = mask
    yield submask
    while submask > 0:
        submask = (submask - 1) & mask
        yield submask


def supermasks(mask: int, num_bits: int) -> Iterator[int]:
    if mask >> num_bits != 0:
        raise ValueError("Bound is too small")

    all_bits = (1 << num_bits) - 1
    for submask in submasks(mask ^ all_bits):
        yield submask ^ all_bits
