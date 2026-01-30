# SPDX-FileCopyrightText: 2026 Ohad Livne <libohad-dev@proton.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]
from testcontainers.core.image import DockerImage  # type: ignore[import-untyped]
from testcontainers.core.network import Network  # type: ignore[import-untyped]
from testcontainers.minio import Minio, MinioContainer  # type: ignore[import-untyped]

PYTHON_TAGS = [
    # keep-sorted start
    "3.10.19-alpine3.23",
    "3.11.14-alpine3.23",
    "3.12.12-alpine3.23",
    "3.13.11-alpine3.23",
    "3.14.2-alpine3.23",
    "3.15.0a5-alpine3.23",
    # keep-sorted end
]
MINIO_TAG = "RELEASE.2025-09-07T16-13-09Z"
MINIO_NETWORK_ALIAS = "minio"


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


@pytest.fixture(scope="session", params=PYTHON_TAGS)
def base_image(request: pytest.FixtureRequest) -> Iterator[DockerImage]:
    image_tag: str = request.param
    with DockerImage(
        path=Path(__file__).parent.parent,
        # keep-sorted start
        buildargs={"IMAGE_TAG": image_tag},
        clean_up=False,
        dockerfile_path="tests/Containerfile.base",
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
def container(image: DockerImage, container_coverage_dir: Path | None) -> Iterator[DockerContainer]:
    cov_dir_mount: dict[str, Any] = (
        {"tmpfs": {"/coverage": "size=1M,mode=1777"}}
        if container_coverage_dir is None
        else {"volumes": [(str(container_coverage_dir), "/coverage", "rw")]}
    )

    with DockerContainer(
        str(image),
        # keep-sorted start
        auto_remove=True,
        env={"COVERAGE_FILE": "/coverage/.coverage"},
        network_mode="none",
        read_only=True,
        remove=True,
        # keep-sorted end
        **cov_dir_mount,
    ) as test_container:
        yield test_container


@pytest.fixture(scope="session")
def s3_image(image: DockerImage) -> Iterator[DockerImage]:
    """Test image with boto3 installed for S3 tests."""
    image_tag = image.tag.rpartition(":")[2]
    with DockerImage(
        path=Path(__file__).parent.parent,
        # keep-sorted start
        buildargs={"IMAGE_TAG": image_tag},
        clean_up=False,
        dockerfile_path="tests/Containerfile.s3",
        tag=f"localhost/temper-edit-test-s3:{image_tag}",
        # keep-sorted end
    ) as s3_test_image:
        yield s3_test_image


@pytest.fixture
def s3_network() -> Iterator[Network]:
    """Per-test isolated network for S3 containers."""
    with Network() as network:
        yield network


@pytest.fixture
def minio(s3_network: Network) -> Iterator[MinioContainer]:
    """MinIO container attached to the test network."""
    with MinioContainer(
        # keep-sorted start
        auto_remove=True,
        image=f"docker.io/minio/minio:{MINIO_TAG}",
        network=s3_network,
        network_aliases=[MINIO_NETWORK_ALIAS],
        read_only=True,
        remove=True,
        # keep-sorted end
    ) as minio_container:
        yield minio_container


@pytest.fixture
def s3_container(
    s3_image: DockerImage,
    s3_network: Network,
    minio: MinioContainer,
    container_coverage_dir: Path | None,
) -> Iterator[DockerContainer]:
    """Test container with network access to MinIO."""
    cov_dir_mount: dict[str, Any] = (
        {"tmpfs": {"/coverage": "size=1M,mode=1777"}}
        if container_coverage_dir is None
        else {"volumes": [(str(container_coverage_dir), "/coverage", "rw")]}
    )

    with DockerContainer(
        str(s3_image),
        # keep-sorted start block=yes
        auto_remove=True,
        env={
            "AWS_ACCESS_KEY_ID": minio.access_key,
            "AWS_ENDPOINT_URL": f"http://{MINIO_NETWORK_ALIAS}:{minio.port}",
            "AWS_SECRET_ACCESS_KEY": minio.secret_key,
            "COVERAGE_FILE": "/coverage/.coverage",
        },
        network=s3_network,
        read_only=True,
        remove=True,
        # keep-sorted end
        **cov_dir_mount,
    ) as test_container:
        yield test_container


@pytest.fixture
def s3_client(minio: MinioContainer) -> Minio:
    """Create an S3 client for test setup/verification."""

    return minio.get_client()


@pytest.fixture
def s3_bucket(s3_client: Minio) -> str:
    """Create a test bucket in MinIO."""

    bucket_name = "test-bucket"
    s3_client.make_bucket(bucket_name)
    return bucket_name
