# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Iterator


def submasks(mask: int, lower_bound: int = 0) -> Iterator[int]:
    if mask & lower_bound != lower_bound:
        raise ValueError(f"Lower bound {bin(lower_bound)} is not a submask of {bin(mask)}")

    submask = mask
    yield submask
    while submask > lower_bound:
        submask = (submask - 1) & mask
        if submask & lower_bound == lower_bound:
            yield submask


def all_bits(mask: int) -> int:
    acc = mask
    shift = 1
    while delta := acc >> shift:
        acc |= delta
        shift <<= 1

    return acc


def supermasks(mask: int, upper_bound: int) -> Iterator[int]:
    if mask & upper_bound != mask:
        raise ValueError(f"Upper bound {bin(upper_bound)} is not a supermask of {bin(mask)}")

    full_mask = all_bits(upper_bound)
    for submask in submasks(mask ^ full_mask, lower_bound=upper_bound ^ full_mask):
        yield submask ^ full_mask
