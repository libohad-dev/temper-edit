# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import shlex
import textwrap
import uuid

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]

from tests.utils import (
    TEMPER_EDIT_SHELL_COMMAND,
    exec_as_user,
    extract_preserved_temporary_filename,
    get_mtime_ns,
    list_container_files,
    parse_output,
    stat_file,
)


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
            command=["sh", "-c", f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} {filename}'],
            container=container,
        )
    )

    mtime_after = get_mtime_ns(container=container, filename=filename)

    stat = stat_file(container=container, filename=filename)
    assert stat.user == (1000, "user"), "Wrong file user ownership"
    assert stat.group == (1000, "user"), "Wrong file group ownership"
    assert stat.mode.endswith("644"), "Wrong file permissions"
    assert parse_output(container.exec(["cat", filename])) == content, "Wrong file content"
    assert mtime_after > mtime_before, "File mtime should have increased after successful edit"

    for fn in ["/tmp/pre-edit", "/tmp/post-edit"]:
        assert parse_output(container.exec(["cat", fn])) == "", f"Wrong file content in {fn}"

    # Verify temporary files were cleaned up
    assert list_container_files(container=container, directory="/tmp") == {
        "/tmp/file.txt",
        "/tmp/edit-file",
        "/tmp/pre-edit",
        "/tmp/post-edit",
    }


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

    with pytest.raises(RuntimeError, match="Editor failed. Temporary file preserved at:") as exc_info:
        _ = parse_output(
            container.exec(["sh", "-c", f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} {filename}'])
        )

    mtime_after = get_mtime_ns(container=container, filename=filename)

    stat = stat_file(container=container, filename=filename)
    assert stat.user == (0, "root"), "Wrong file user ownership"
    assert stat.group == (0, "root"), "Wrong file group ownership"
    assert stat.mode.endswith("644"), "Wrong file permissions"
    assert parse_output(container.exec(["cat", filename])) == original_content, "Wrong file content"
    assert mtime_after == mtime_before, "File mtime should not have changed after failed edit"

    # Verify temporary file was preserved and contains the expected content
    tempfile = extract_preserved_temporary_filename(exc_info)
    assert list_container_files(container=container, directory="/tmp") == {"/tmp/file.txt", "/tmp/edit-file", tempfile}
    assert parse_output(container.exec(["cat", tempfile])) == content, "Preserved temp file has wrong content"


def test_temporary_file_is_preserved_on_update_failure(container: DockerContainer) -> None:
    script = textwrap.dedent("""\
    #! /bin/sh
    echo "$1" > "$2"
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chmod", "a+x", "/tmp/edit-file"])

    filename = "/tmp/readonly-dir/file.txt"
    original_content = "foobar"
    content = str(uuid.uuid4())
    container.exec(["mkdir", "/tmp/readonly-dir"])
    container.exec(["sh", "-c", f"echo '{original_content}' > {filename}"])
    # Make the directory read-only to prevent the final move
    container.exec(["chmod", "555", "/tmp/readonly-dir"])

    mtime_before = get_mtime_ns(container=container, filename=filename)

    with pytest.raises(RuntimeError, match=f"Failed to update file: {filename}") as exc_info:
        _ = parse_output(
            exec_as_user(
                command=["sh", "-c", f'EDITOR="/tmp/edit-file {content}" {TEMPER_EDIT_SHELL_COMMAND} {filename}'],
                container=container,
            )
        )

    mtime_after = get_mtime_ns(container=container, filename=filename)

    stat = stat_file(container=container, filename=filename)
    assert stat.user == (0, "root"), "Wrong file user ownership"
    assert stat.group == (0, "root"), "Wrong file group ownership"
    assert stat.mode.endswith("644"), "Wrong file permissions"
    assert parse_output(container.exec(["cat", filename])) == original_content, "Original file should be unchanged"
    assert mtime_after == mtime_before, "File mtime should not have changed after failed update"

    # Verify temporary file was preserved and contains the edited content
    tempfile = extract_preserved_temporary_filename(exc_info)
    assert list_container_files(container=container, directory="/tmp") == {
        "/tmp/edit-file",
        "/tmp/readonly-dir",
        tempfile,
    }
    assert list_container_files(container=container, directory="/tmp/readonly-dir") == {filename}
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

    parse_output(
        container.exec(command=["sh", "-c", f'EDITOR="/tmp/noop-editor" {TEMPER_EDIT_SHELL_COMMAND} {filename}'])
    )

    mtime_after = get_mtime_ns(container=container, filename=filename)

    stat = stat_file(container=container, filename=filename)
    assert stat.user == (0, "root"), "Wrong file user ownership"
    assert stat.group == (0, "root"), "Wrong file group ownership"
    assert stat.mode.endswith("644"), "Wrong file permissions"
    assert parse_output(container.exec(["cat", filename])) == original_content, "File content should be unchanged"
    assert mtime_after == mtime_before, "File mtime should not have changed when content is unchanged"

    # Verify temporary files were cleaned up
    assert list_container_files(container=container, directory="/tmp") == {"/tmp/file.txt", "/tmp/noop-editor"}
