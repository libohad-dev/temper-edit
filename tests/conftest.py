# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Iterator
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]
from testcontainers.core.image import DockerImage  # type: ignore[import-untyped]

tags = [
    # keep-sorted start
    "python3.10-alpine3.23",
    "python3.11-alpine3.23",
    "python3.12-alpine3.23",
    "python3.13-alpine3.23",
    "python3.14-alpine3.23",
    # keep-sorted end
]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--container-coverage-dir", help="Directory to store coverage data from containers")


@pytest.fixture(scope="session")
def container_coverage_dir(request: pytest.FixtureRequest) -> Path | None:
    cov_dir = request.config.getoption("--container-coverage-dir")
    if cov_dir:
        path = Path(cov_dir)
        path.mkdir(parents=True, exist_ok=True)
        return Path(cov_dir)
    return None


@pytest.fixture(scope="session", params=tags)
def base_image(request: pytest.FixtureRequest) -> Iterator[DockerImage]:
    image_tag: str = request.param
    with DockerImage(
        path=Path(__file__).parent.parent,
        # keep-sorted start
        buildargs={"IMAGE_TAG": image_tag},
        clean_up=False,
        dockerfile_path="tests/Containerfile-base",
        tag=f"localhost/temper-edit-test-base:{image_tag}",
        # keep-sorted end
    ) as base_test_image:
        yield base_test_image


@pytest.fixture(scope="session")
def image(base_image: DockerImage) -> Iterator[DockerImage]:
    image_tag = base_image.tag.rpartition(":")[2]
    with DockerImage(
        path=Path(__file__).parent.parent,
        # keep-sorted start
        buildargs={"IMAGE_TAG": image_tag},
        clean_up=False,
        dockerfile_path="tests/Containerfile",
        tag=f"localhost/temper-edit-test:{image_tag}",
        # keep-sorted end
    ) as test_image:
        yield test_image


@pytest.fixture
def container(image: DockerImage, container_coverage_dir: Path) -> Iterator[DockerContainer]:
    with DockerContainer(
        str(image),
        # keep-sorted start
        auto_remove=True,
        env={"COVERAGE_FILE": "/coverage/.coverage"},
        network_mode="none",
        read_only=True,
        remove=True,
        volumes=[(str(container_coverage_dir), "/coverage", "rw")],
        # keep-sorted end
    ) as test_container:
        yield test_container
