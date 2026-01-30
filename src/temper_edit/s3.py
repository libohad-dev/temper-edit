# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from typing import Any

from .atomic_edit import FileSandbox

try:
    import boto3
except ImportError as e:
    raise ImportError("S3 support requires boto3. Install with: pip install temper-edit[s3]") from e


def make_s3_sandbox(bucket: str) -> type[FileSandbox]:
    class S3Sandbox(FileSandbox):
        """Sandbox for editing files stored in AWS S3."""

        def __post_init__(self) -> None:
            super().__post_init__()
            self.s3_client = boto3.client("s3")

        def stage_file(self) -> None:
            self.s3_client.download_file(Bucket=bucket, Key=str(self.filename), Filename=self.tempfile.name)

        def commit_file(self) -> None:
            content = Path(self.tempfile.name).read_bytes()

            put_kwargs: dict[str, Any] = {
                "Bucket": bucket,
                "Key": str(self.filename),
                "Body": content,
            }

            self.s3_client.put_object(**put_kwargs)

            # Clean up the tempfile after successful commit
            Path(self.tempfile.name).unlink()

    return S3Sandbox
