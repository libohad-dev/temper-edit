# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import shlex
import textwrap
import uuid

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.utils import TEMPER_EDIT_BINARY, exec_as_user, get_mtime_ns, parse_output, stat_file


def list_tmp_files(container: DockerContainer) -> set[str]:
    """List all files in /tmp directory."""
    return set(parse_output(container.exec(["ls", "-1", "/tmp"])).splitlines())


def test_original_file_is_not_modified_midway(container: DockerContainer) -> None:
    filename = "/tmp/file.txt"

    # Manually check on the original file along the way
    script = textwrap.dedent(f"""\
    #! /bin/sh
    cp "{filename}" /tmp/pre-edit
    echo "$1" > "$2"
    cp "{filename}" /tmp/post-edit
    """)

    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chown", "user:user", "/tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])

    content = str(uuid.uuid4())
    container.exec(["touch", filename])
    container.exec(["chown", "user:user", filename])

    mtime_before = get_mtime_ns(container=container, filename=filename)

    parse_output(
        exec_as_user(
            command=["sh", "-c", f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_BINARY} {filename}'],
            container=container,
        )
    )

    mtime_after = get_mtime_ns(container=container, filename=filename)

    uid, username, file_perms = stat_file(container=container, filename=filename)
    assert (uid, username) == (1000, "user"), "Wrong file ownership"
    assert file_perms.endswith("644"), "Wrong file permissions"
    assert parse_output(container.exec(["cat", filename])) == content, "Wrong file content"
    assert mtime_after > mtime_before, "File mtime should have increased after successful edit"

    for fn in ["/tmp/pre-edit", "/tmp/post-edit"]:
        assert parse_output(container.exec(["cat", fn])) == "", f"Wrong file content in {fn}"

    # Verify temporary files were cleaned up
    assert list_tmp_files(container) == {"file.txt", "edit-file", "pre-edit", "post-edit"}


def test_original_file_is_not_modified_when_the_editor_fails(container: DockerContainer) -> None:
    # Fail after editing the temporary file
    script = textwrap.dedent("""\
    #! /bin/sh
    echo "$1" > "$2"
    exit 1
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])

    filename = "/tmp/file.txt"
    original_content = "foobar"
    content = str(uuid.uuid4())
    container.exec(["sh", "-c", f"echo '{original_content}' > {filename}"])

    mtime_before = get_mtime_ns(container=container, filename=filename)

    with pytest.raises(RuntimeError) as exc_info:
        _ = parse_output(
            container.exec(["sh", "-c", f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_BINARY} {filename}'])
        )

    mtime_after = get_mtime_ns(container=container, filename=filename)

    uid, username, file_perms = stat_file(container=container, filename=filename)
    assert (uid, username) == (0, "root"), "Wrong file ownership"
    assert file_perms.endswith("644"), "Wrong file permissions"
    assert parse_output(container.exec(["cat", filename])) == original_content, "Wrong file content"
    assert mtime_after == mtime_before, "File mtime should not have changed after failed edit"

    # Validate error message format and extract preserved temp file path
    error_output = exc_info.value.args[0].decode("utf-8")
    match = re.search(r"Temporary file preserved at: (?P<tempfile>/tmp/\S+)", error_output)
    assert match is not None, f"Error message should contain preserved temp file path, got: {error_output}"
    # Verify temporary file was preserved and contains the expected content
    tempfile = match["tempfile"]
    assert list_tmp_files(container) == {"file.txt", "edit-file", tempfile.removeprefix("/tmp/")}
    assert parse_output(container.exec(["cat", tempfile])) == content, "Preserved temp file has wrong content"


def test_original_file_is_not_modified_when_content_unchanged(container: DockerContainer) -> None:
    # Editor that does nothing (just exits successfully)
    script = textwrap.dedent("""\
    #! /bin/sh
    exit 0
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/noop-editor"])
    container.exec(["chmod", "u+x", "/tmp/noop-editor"])

    filename = "/tmp/file.txt"
    original_content = "foobar"
    container.exec(["sh", "-c", f"echo '{original_content}' > {filename}"])

    mtime_before = get_mtime_ns(container=container, filename=filename)

    parse_output(container.exec(command=["sh", "-c", f'EDITOR="/tmp/noop-editor" {TEMPER_EDIT_BINARY} {filename}']))

    mtime_after = get_mtime_ns(container=container, filename=filename)

    uid, username, file_perms = stat_file(container=container, filename=filename)
    assert (uid, username) == (0, "root"), "Wrong file ownership"
    assert file_perms.endswith("644"), "Wrong file permissions"
    assert parse_output(container.exec(["cat", filename])) == original_content, "File content should be unchanged"
    assert mtime_after == mtime_before, "File mtime should not have changed when content is unchanged"

    # Verify temporary files were cleaned up
    assert list_tmp_files(container) == {"file.txt", "noop-editor"}
