# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from tests.masks import all_bits, submasks, supermasks


def test_null_submasks() -> None:
    assert list(submasks(0)) == [0]


def test_non_null_submasks() -> None:
    assert list(submasks(0b1010)) == [10, 8, 2, 0]


def test_invalid_submask_lower_bound() -> None:
    with pytest.raises(ValueError):
        next(submasks(0b101, lower_bound=0b110))


def test_bound_submasks() -> None:
    assert list(submasks(0b1101, lower_bound=0b1000)) == [13, 12, 9, 8]
    assert list(submasks(0b1110, lower_bound=0b0100)) == [14, 12, 6, 4]


def test_all_bits() -> None:
    assert all_bits(0) == 0
    assert all_bits(4) == 7
    assert all_bits(5) == 7
    assert all_bits(15) == 15


def test_invalid_supermask_upper_bound() -> None:
    with pytest.raises(ValueError):
        _ = next(supermasks(0b101, upper_bound=0b100))
    with pytest.raises(ValueError):
        _ = next(supermasks(0b101, upper_bound=0b1000))


def test_single_supermasks() -> None:
    assert list(supermasks(0b111, upper_bound=0b111)) == [7]


def test_multiple_supermasks() -> None:
    assert list(supermasks(0b101, upper_bound=0b1111)) == [5, 7, 13, 15]


def test_bound_supermasks() -> None:
    assert list(supermasks(0b1, upper_bound=0b1011)) == [1, 3, 9, 11]
