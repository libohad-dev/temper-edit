# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from testcontainers.core.image import DockerImage  # type: ignore[import-untyped]


def test_image_build(image: DockerImage) -> None:
    pass
