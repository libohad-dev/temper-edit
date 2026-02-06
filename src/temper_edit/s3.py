# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from typing import Any

from .atomic_edit import FileSandbox
from .exceptions import ConcurrentModificationError

try:
    import boto3
except ImportError as e:
    raise ImportError("S3 support requires boto3. Install with: pip install temper-edit[s3]") from e


# Note: S3 conditional writes (If-Match header) were added in November 2024.
# See: https://aws.amazon.com/about-aws/whats-new/2024/11/amazon-s3-functionality-conditional-writes/
# This allows atomic compare-and-swap without TOCTOU races.


def make_s3_sandbox(bucket: str, force: bool = False) -> type[FileSandbox]:
    class S3Sandbox(FileSandbox):
        """Sandbox for editing files stored in AWS S3."""

        def __post_init__(self) -> None:
            super().__post_init__()
            self.s3_client = boto3.client("s3")

        def stage_file(self) -> None:
            key = str(self.filename)
            head_response = self.s3_client.head_object(Bucket=bucket, Key=key)
            self.original_metadata: dict[str, str] = head_response.get("Metadata", {})
            self.original_content_type: str | None = head_response.get("ContentType")
            self.original_etag: str | None = head_response.get("ETag")
            self.s3_client.download_file(Bucket=bucket, Key=key, Filename=self.tempfile.name)

        def commit_file(self) -> None:
            from botocore.exceptions import ClientError

            content = Path(self.tempfile.name).read_bytes()

            put_kwargs: dict[str, Any] = {
                "Bucket": bucket,
                "Key": str(self.filename),
                "Body": content,
                "Metadata": self.original_metadata,
            }

            # ContentType is optional per the S3 API spec, but in practice AWS and MinIO
            # always set it in put_object() (defaulting to application/octet-stream). This
            # guard handles hypothetical S3-compatible services that might omit it. See:
            # https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html#API_HeadObject_ResponseSyntax
            # https://github.com/minio/minio-py/blob/7.2.20/minio/api.py#L1915
            if self.original_content_type is not None:  # pragma: no cover
                put_kwargs["ContentType"] = self.original_content_type

            # Use ETag for optimistic concurrency control unless --force is specified
            if not force and self.original_etag is not None:
                put_kwargs["IfMatch"] = self.original_etag

            try:
                self.s3_client.put_object(**put_kwargs)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                # 412 PreconditionFailed: ETag mismatch
                # 409 ConditionalRequestConflict: Race during upload (S3-specific)
                if error_code in ("PreconditionFailed", "ConditionalRequestConflict", "412", "409"):
                    raise ConcurrentModificationError(
                        "Object was modified by another process (concurrent modification detected)"
                    ) from e
                raise

            # Clean up the tempfile after successful commit
            Path(self.tempfile.name).unlink()

    return S3Sandbox
