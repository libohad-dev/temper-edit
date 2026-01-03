# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from tests.masks import submasks, supermasks


def test_null_submasks() -> None:
    assert list(submasks(0)) == [0]


def test_non_null_submasks() -> None:
    assert list(submasks(0b1010)) == [10, 8, 2, 0]


def test_insufficient_bound() -> None:
    with pytest.raises(ValueError):
        _ = next(supermasks(0b101, num_bits=2))


def test_single_supermasks() -> None:
    assert list(supermasks(0b111, num_bits=3)) == [7]


def test_multiple_supermasks() -> None:
    assert list(supermasks(0b101, num_bits=4)) == [5, 7, 13, 15]
