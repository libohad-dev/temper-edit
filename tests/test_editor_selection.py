# SPDX-FileCopyrightText: 2025 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from temper_edit.config import EditorConfig
from temper_edit.editor import select_editor
from temper_edit.exceptions import ConfigError


def test_no_editor_configured() -> None:
    with pytest.raises(ConfigError, match="No editor configured"):
        _ = select_editor(EditorConfig())


def test_select_editor_envvar() -> None:
    assert select_editor(EditorConfig(EDITOR="foo")) == ["foo"]


def test_select_visual_envvar() -> None:
    assert select_editor(EditorConfig(EDITOR="foo", VISUAL="bar")) == ["bar"]


def test_select_sudo_editor_envvar() -> None:
    assert select_editor(
        EditorConfig(EDITOR="foo", VISUAL="bar", SUDO_EDITOR="baz")
    ) == ["baz"]


def test_complex_command() -> None:
    assert select_editor(EditorConfig(EDITOR="foo bar")) == ["foo", "bar"]


def test_complex_command_containing_whitespaces() -> None:
    assert select_editor(EditorConfig(EDITOR='foo --bar "b a z"')) == [
        "foo",
        "--bar",
        "b a z",
    ]
