# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Iterator
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]
from testcontainers.core.image import DockerImage  # type: ignore[import-untyped]


@pytest.fixture(
    params=[
        # keep-sorted start
        "3.10.19-alpine3.23",
        "3.11.14-alpine3.23",
        "3.12.12-alpine3.23",
        "3.13.11-alpine3.23",
        "3.14.2-alpine3.23",
        # keep-sorted end
    ]
)
def image(request: pytest.FixtureRequest) -> Iterator[DockerImage]:
    image_tag: str = request.param
    with DockerImage(
        path=Path(__file__).parent.parent,
        # keep-sorted start
        buildargs={"IMAGE_TAG": image_tag},
        clean_up=False,
        dockerfile_path="tests/Containerfile",
        squash=True,
        tag=f"temper-edit-test:{image_tag}",
        # keep-sorted end
    ) as test_image:
        yield test_image


@pytest.fixture
def container(image: DockerImage) -> Iterator[DockerContainer]:
    with DockerContainer(
        str(image),
        # keep-sorted start
        auto_remove=True,
        network_mode="none",
        read_only=True,
        remove=True,
        # keep-sorted end
    ) as test_container:
        yield test_container
