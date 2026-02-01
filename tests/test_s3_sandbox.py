# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Integration tests for S3 sandbox using MinIO."""

import io
import json
import shlex
import textwrap
import uuid

import minio.datatypes
import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]
from testcontainers.minio import Minio, MinioContainer  # type: ignore[import-untyped]

from tests.utils import (
    TEMPER_EDIT_SHELL_COMMAND,
    extract_preserved_temporary_filename,
    list_container_files,
    parse_output,
)

CUSTOM_METADATA_PREFIX = "x-amz-meta-"


def get_custom_metadata(stat_result: minio.datatypes.Object) -> dict[str, str]:
    """Extract only custom S3 metadata keys (x-amz-meta-*) from stat result."""
    # stat_object() always sets metadata=response.headers, so this branch is unreachable.
    # The Optional type annotation exists for list_objects() which doesn't return metadata.
    # See: https://github.com/minio/minio-py/blob/7.2.20/minio/api.py#L2281
    if stat_result.metadata is None:  # pragma: no cover
        return {}
    return {k: v for k, v in stat_result.metadata.items() if k.startswith(CUSTOM_METADATA_PREFIX)}


def setup_editor(container: DockerContainer) -> None:
    """Create the standard test editor that writes its first argument to the file."""
    script = textwrap.dedent("""\
    #! /bin/sh
    echo "$1" > "$2"
    """)
    container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/edit-file"])
    container.exec(["chmod", "u+x", "/tmp/edit-file"])


def test_script_requires_boto(container: DockerContainer, s3_bucket: str, s3_client: Minio) -> None:
    setup_editor(container)

    object_key = "missing_requiremenet.txt"
    original_content = b"original content"
    new_content = str(uuid.uuid4())
    original_metadata = {"x-amz-meta-test-key": "test-value", "x-amz-meta-author": "test-author"}

    # Upload initial object with metadata
    s3_client.put_object(
        s3_bucket, object_key, io.BytesIO(original_content), len(original_content), metadata=original_metadata
    )

    # Get the initial ETag
    initial_stat = s3_client.stat_object(s3_bucket, object_key)
    initial_etag = initial_stat.etag

    with pytest.raises(
        RuntimeError,
        match=r"ImportError: S3 support requires boto3. Install with: pip install temper-edit\[s3\]",
    ):
        parse_output(
            container.exec(
                [
                    "sh",
                    "-c",
                    f'EDITOR="/tmp/edit-file {new_content}" {TEMPER_EDIT_SHELL_COMMAND} --s3 {s3_bucket} {object_key}',
                ]
            )
        )

    # Verify temporary files were cleaned up
    assert list_container_files(container, "/tmp") == {"/tmp/edit-file"}

    # Verify the object wasn't re-uploaded (ETag should be unchanged)
    final_stat = s3_client.stat_object(s3_bucket, object_key)
    assert final_stat.etag == initial_etag, "Object should not have been re-uploaded when content unchanged"

    # Verify content is still the same
    response = s3_client.get_object(s3_bucket, object_key)
    assert response.read() == original_content, "Object content should be unchanged"
    response.close()
    response.release_conn()

    # Verify metadata is preserved
    assert get_custom_metadata(final_stat) == original_metadata, "Object metadata should be unchanged"

    # Verify no other changes to storage
    assert [b.name for b in s3_client.list_buckets()] == [s3_bucket], "No extra buckets should have been created"
    assert [o.object_name for o in s3_client.list_objects(s3_bucket)] == [object_key], "No extra objects should exist"


def test_script_fails_with_missing_object(s3_container: DockerContainer, s3_bucket: str, s3_client: Minio) -> None:
    setup_editor(s3_container)
    object_key = "nonexistent-object.txt"

    with pytest.raises(
        RuntimeError,
        match=r"botocore\.exceptions\.ClientError: An error occurred \(404\) when calling the HeadObject operation: Not Found",
    ):
        parse_output(
            s3_container.exec(
                [
                    "sh",
                    "-c",
                    f'EDITOR="/tmp/edit-file content" {TEMPER_EDIT_SHELL_COMMAND} --s3 {s3_bucket} {object_key}',
                ]
            )
        )

    # Verify no temporary files were left behind (error occurs before temp file creation)
    assert list_container_files(s3_container, "/tmp") == {"/tmp/edit-file"}

    # Verify the script did not modify the storage content
    assert [b.name for b in s3_client.list_buckets()] == [s3_bucket], "No extra buckets should have been created"
    assert list(s3_client.list_objects(s3_bucket)) == [], "No objects should have been created in the bucket"


def test_script_fails_with_missing_bucket(s3_container: DockerContainer, s3_client: Minio) -> None:
    setup_editor(s3_container)
    object_key = "some-object.txt"
    nonexistent_bucket = "nonexistent-bucket"

    with pytest.raises(
        RuntimeError,
        match=r"botocore\.exceptions\.ClientError: An error occurred \(404\) when calling the HeadObject operation: Not Found",
    ):
        parse_output(
            s3_container.exec(
                [
                    "sh",
                    "-c",
                    f'EDITOR="/tmp/edit-file content" {TEMPER_EDIT_SHELL_COMMAND} --s3 {nonexistent_bucket} {object_key}',
                ]
            )
        )

    # Verify no temporary files were left behind (error occurs before temp file creation)
    assert list_container_files(s3_container, "/tmp") == {"/tmp/edit-file"}

    # Verify the script did not modify the storage content
    assert list(s3_client.list_buckets()) == [], "No buckets should have been created"


def test_unchanged_content(s3_container: DockerContainer, s3_bucket: str, s3_client: Minio) -> None:
    # Create a no-op editor that exits without modifying the file
    script = textwrap.dedent("""\
    #! /bin/sh
    exit 0
    """)
    s3_container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/noop-editor"])
    s3_container.exec(["chmod", "u+x", "/tmp/noop-editor"])

    object_key = "unchanged-test.txt"
    original_content = b"original content"
    original_metadata = {"x-amz-meta-unchanged": "preserved", "x-amz-meta-version": "1"}

    # Upload initial object with metadata
    s3_client.put_object(
        s3_bucket, object_key, io.BytesIO(original_content), len(original_content), metadata=original_metadata
    )

    # Get the initial ETag
    initial_stat = s3_client.stat_object(s3_bucket, object_key)
    initial_etag = initial_stat.etag

    # Run temper-edit with no-op editor
    parse_output(
        s3_container.exec(
            ["sh", "-c", f'EDITOR="/tmp/noop-editor" {TEMPER_EDIT_SHELL_COMMAND} --s3 {s3_bucket} {object_key}']
        )
    )

    # Verify temporary files were cleaned up
    assert list_container_files(s3_container, "/tmp") == {"/tmp/noop-editor"}

    # Verify the object wasn't re-uploaded (ETag should be unchanged)
    final_stat = s3_client.stat_object(s3_bucket, object_key)
    assert final_stat.etag == initial_etag, "Object should not have been re-uploaded when content unchanged"

    # Verify content is still the same
    response = s3_client.get_object(s3_bucket, object_key)
    assert response.read() == original_content, "Object content should be unchanged"
    response.close()
    response.release_conn()

    # Verify metadata is preserved
    assert get_custom_metadata(final_stat) == original_metadata, "Object metadata should be unchanged"

    # Verify no other changes to storage
    assert [b.name for b in s3_client.list_buckets()] == [s3_bucket], "No extra buckets should have been created"
    assert [o.object_name for o in s3_client.list_objects(s3_bucket)] == [object_key], "No extra objects should exist"


def test_editor_failure(s3_container: DockerContainer, s3_bucket: str, s3_client: Minio) -> None:
    # Create an editor that modifies the file but exits with failure
    new_content = str(uuid.uuid4())
    script = textwrap.dedent("""\
    #! /bin/sh
    echo "$1" > "$2"
    exit 1
    """)
    s3_container.exec(["sh", "-c", f"echo {shlex.quote(script)} > /tmp/failing-editor"])
    s3_container.exec(["chmod", "u+x", "/tmp/failing-editor"])

    object_key = "editor-failure-test.txt"
    original_content = b"original content before failure"
    original_metadata = {"x-amz-meta-failure-test": "should-remain", "x-amz-meta-status": "original"}

    # Upload initial object with metadata
    s3_client.put_object(
        s3_bucket, object_key, io.BytesIO(original_content), len(original_content), metadata=original_metadata
    )
    initial_stat = s3_client.stat_object(s3_bucket, object_key)
    initial_etag = initial_stat.etag

    # Run temper-edit with failing editor
    with pytest.raises(RuntimeError, match="Editor failed. Temporary file preserved at:") as exc_info:
        parse_output(
            s3_container.exec(
                [
                    "sh",
                    "-c",
                    f'EDITOR="/tmp/failing-editor {new_content}" {TEMPER_EDIT_SHELL_COMMAND} --s3 {s3_bucket} {object_key}',
                ]
            )
        )

    # Verify temporary file was preserved with the edited content
    tempfile = extract_preserved_temporary_filename(exc_info)
    assert list_container_files(s3_container, "/tmp") == {"/tmp/failing-editor", tempfile}
    preserved_content = parse_output(s3_container.exec(["cat", tempfile]))
    assert preserved_content == new_content, "Preserved temp file should contain the edited content"

    # Verify the S3 object wasn't modified
    final_stat = s3_client.stat_object(s3_bucket, object_key)
    assert final_stat.etag == initial_etag, "S3 object should not have been modified after editor failure"

    response = s3_client.get_object(s3_bucket, object_key)
    assert response.read() == original_content, "S3 object content should be unchanged"
    response.close()
    response.release_conn()

    # Verify metadata is preserved
    assert get_custom_metadata(final_stat) == original_metadata, (
        "Object metadata should be unchanged after editor failure"
    )

    # Verify no other changes to storage
    assert [b.name for b in s3_client.list_buckets()] == [s3_bucket], "No extra buckets should have been created"
    assert [o.object_name for o in s3_client.list_objects(s3_bucket)] == [object_key], "No extra objects should exist"


def test_successful_update(s3_container: DockerContainer, s3_bucket: str, s3_client: Minio) -> None:
    setup_editor(s3_container)

    object_key = "successful-update-test.txt"
    original_content = b"original content"
    new_content = str(uuid.uuid4())
    original_metadata = {"x-amz-meta-update-test": "will-be-lost", "x-amz-meta-important": "data"}

    # Upload initial object with metadata
    s3_client.put_object(
        s3_bucket, object_key, io.BytesIO(original_content), len(original_content), metadata=original_metadata
    )
    initial_stat = s3_client.stat_object(s3_bucket, object_key)
    initial_etag = initial_stat.etag

    # Run temper-edit
    parse_output(
        s3_container.exec(
            [
                "sh",
                "-c",
                f'EDITOR="/tmp/edit-file {new_content}" {TEMPER_EDIT_SHELL_COMMAND} --s3 {s3_bucket} {object_key}',
            ]
        )
    )

    # Verify temporary files were cleaned up
    assert list_container_files(s3_container, "/tmp") == {"/tmp/edit-file"}

    # Verify the object was updated
    final_stat = s3_client.stat_object(s3_bucket, object_key)
    assert final_stat.etag != initial_etag, "S3 object ETag should have changed after successful update"

    # Verify the new content (echo adds a trailing newline)
    response = s3_client.get_object(s3_bucket, object_key)
    assert response.read() == f"{new_content}\n".encode(), "S3 object should contain the new content"
    response.close()
    response.release_conn()

    # Verify metadata is cleared after update (current implementation does not preserve metadata)
    assert get_custom_metadata(final_stat) == {}, "Object metadata should be cleared after update"

    # Verify no other changes to storage
    assert [b.name for b in s3_client.list_buckets()] == [s3_bucket], "No extra buckets should have been created"
    assert [o.object_name for o in s3_client.list_objects(s3_bucket)] == [object_key], "No extra objects should exist"


def test_script_fails_with_restricted_user_access(
    s3_container: DockerContainer, s3_bucket: str, s3_client: Minio, minio: MinioContainer
) -> None:
    setup_editor(s3_container)
    object_key = "restricted-object.txt"
    original_content = b"restricted content"
    original_metadata = {"x-amz-meta-access": "restricted", "x-amz-meta-owner": "admin"}
    new_content = str(uuid.uuid4())

    s3_client.put_object(
        s3_bucket, object_key, io.BytesIO(original_content), len(original_content), metadata=original_metadata
    )

    # Get the initial ETag
    initial_stat = s3_client.stat_object(s3_bucket, object_key)
    initial_etag = initial_stat.etag

    # Create a restricted user via mc CLI in the MinIO container
    # MinIO denies access by default for users with no policy attached
    restricted_user = "restricteduser"
    restricted_pass = "restrictedpass123"

    # Set up mc alias pointing to local MinIO
    minio.exec(["mc", "alias", "set", "local", "http://localhost:9000", minio.access_key, minio.secret_key])

    # Create the restricted user (no policy = no access)
    minio.exec(["mc", "admin", "user", "add", "local", restricted_user, restricted_pass])

    # Run temper-edit with the restricted user's credentials
    with pytest.raises(
        RuntimeError,
        match=r"botocore\.exceptions\.ClientError: An error occurred \(403\) when calling the HeadObject operation: Forbidden",
    ):
        parse_output(
            s3_container.exec(
                [
                    "sh",
                    "-c",
                    f"AWS_ACCESS_KEY_ID={restricted_user} AWS_SECRET_ACCESS_KEY={restricted_pass} "
                    f'EDITOR="/tmp/edit-file {new_content}" {TEMPER_EDIT_SHELL_COMMAND} --s3 {s3_bucket} {object_key}',
                ]
            )
        )

    # Verify no temporary files were left behind (error occurs before temp file creation)
    assert list_container_files(s3_container, "/tmp") == {"/tmp/edit-file"}

    # Verify the object wasn't modified
    final_stat = s3_client.stat_object(s3_bucket, object_key)
    assert final_stat.etag == initial_etag, "S3 object should not have been modified with access restricted"

    response = s3_client.get_object(s3_bucket, object_key)
    assert response.read() == original_content, "Object content should be unchanged"
    response.close()
    response.release_conn()

    # Verify metadata is preserved
    assert get_custom_metadata(final_stat) == original_metadata, (
        "Object metadata should be unchanged with access restricted"
    )

    # Verify no other changes to storage
    assert [b.name for b in s3_client.list_buckets()] == [s3_bucket], "No extra buckets should have been created"
    assert [o.object_name for o in s3_client.list_objects(s3_bucket)] == [object_key], "No extra objects should exist"


def test_successful_update_with_full_user_access(
    s3_container: DockerContainer, s3_bucket: str, s3_client: Minio, minio: MinioContainer
) -> None:
    setup_editor(s3_container)

    object_key = "policy-test.txt"
    original_content = b"original content"
    new_content = str(uuid.uuid4())
    original_metadata = {"x-amz-meta-policy-test": "will-be-lost", "x-amz-meta-created-by": "admin"}

    # Upload initial object with metadata using admin credentials
    s3_client.put_object(
        s3_bucket, object_key, io.BytesIO(original_content), len(original_content), metadata=original_metadata
    )
    initial_stat = s3_client.stat_object(s3_bucket, object_key)
    initial_etag = initial_stat.etag

    # Create a user with a policy that allows access to the object
    allowed_user = "alloweduser"
    allowed_pass = "allowedpass123"

    # Set up mc alias pointing to local MinIO
    minio.exec(["mc", "alias", "set", "local", "http://localhost:9000", minio.access_key, minio.secret_key])

    # Create the user
    minio.exec(["mc", "admin", "user", "add", "local", allowed_user, allowed_pass])

    # Create a policy that allows access to the specific object
    allow_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject"],
                "Resource": [f"arn:aws:s3:::{s3_bucket}/{object_key}"],
            }
        ],
    }
    policy_name = "allow-object-access"
    minio.exec(
        [
            "sh",
            "-c",
            f"echo {shlex.quote(json.dumps(allow_policy))} | mc admin policy create local {policy_name} /dev/stdin",
        ]
    )

    # Attach the policy to the user
    minio.exec(["mc", "admin", "policy", "attach", "local", policy_name, "--user", allowed_user])

    # Run temper-edit with the allowed user's credentials
    parse_output(
        s3_container.exec(
            [
                "sh",
                "-c",
                f"AWS_ACCESS_KEY_ID={allowed_user} AWS_SECRET_ACCESS_KEY={allowed_pass} "
                f'EDITOR="/tmp/edit-file {new_content}" {TEMPER_EDIT_SHELL_COMMAND} --s3 {s3_bucket} {object_key}',
            ]
        )
    )

    # Verify temporary files were cleaned up
    assert list_container_files(s3_container, "/tmp") == {"/tmp/edit-file"}

    # Verify the object was updated
    final_stat = s3_client.stat_object(s3_bucket, object_key)
    assert final_stat.etag != initial_etag, "S3 object ETag should have changed after successful update"

    # Verify the new content (echo adds a trailing newline)
    response = s3_client.get_object(s3_bucket, object_key)
    assert response.read() == f"{new_content}\n".encode(), "S3 object should contain the new content"
    response.close()
    response.release_conn()

    # Verify metadata is cleared after update (current implementation does not preserve metadata)
    assert get_custom_metadata(final_stat) == {}, "Object metadata should be cleared after update"

    # Verify no other changes to storage
    assert [b.name for b in s3_client.list_buckets()] == [s3_bucket], "No extra buckets should have been created"
    assert [o.object_name for o in s3_client.list_objects(s3_bucket)] == [object_key], "No extra objects should exist"
