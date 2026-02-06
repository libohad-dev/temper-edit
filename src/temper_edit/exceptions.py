# SPDX-FileCopyrightText: 2025 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later


class ConfigError(RuntimeError):
    pass


class ConcurrentModificationError(OSError):
    """Raised when an S3 object was modified after staging but before commit."""

    pass
