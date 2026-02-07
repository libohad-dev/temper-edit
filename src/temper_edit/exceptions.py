# SPDX-FileCopyrightText: 2025 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later


class TemperError(Exception):
    """Base exception for all temper-edit errors."""

    exit_code: int = 1


class ConfigError(TemperError):
    """Configuration error (no editor, bad tmpdir)."""

    exit_code = 10


class PrivilegeEscalationError(TemperError):
    """Ran under sudo/doas/pkexec."""

    exit_code = 11


class DependencyError(TemperError):
    """Missing optional dependency (e.g. boto3)."""

    exit_code = 12


class StagingError(TemperError):
    """Generic staging failure."""

    exit_code = 20


class StagingFileNotFoundError(StagingError):
    """File not found during staging."""

    exit_code = 21


class StagingPermissionError(StagingError):
    """Permission denied during staging."""

    exit_code = 22


class EditorError(TemperError):
    """Editor non-zero exit or not found."""

    exit_code = 30


class CommitError(TemperError):
    """Generic commit failure."""

    exit_code = 40


class CommitPermissionError(CommitError):
    """Permission denied during commit."""

    exit_code = 41


class ConcurrentModificationError(CommitError):
    """Raised when an S3 object was modified after staging but before commit."""

    exit_code = 42
