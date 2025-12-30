"""Build and run Docker containers for analyzed repositories."""

import asyncio
import docker
from docker.errors import DockerException, ImageNotFound, APIError
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ContainerRunner:
    """Manages building and running Docker containers for repositories."""

    def __init__(self):
        try:
            self.client = docker.from_env()
        except DockerException as e:
            logger.warning(f"Failed to connect to Docker: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Check if Docker is available."""
        if not self.client:
            return False
        try:
            self.client.ping()
            return True
        except Exception:
            return False

    async def build_image(
        self,
        repo_path: str,
        image_tag: str,
        dockerfile_content: str
    ) -> tuple[bool, Optional[str]]:
        """
        Build a Docker image from a Dockerfile.

        Args:
            repo_path: Path to the repository
            image_tag: Tag for the built image
            dockerfile_content: Content of the Dockerfile

        Returns:
            Tuple of (success, error_message)
        """
        if not self.is_available():
            return False, "Docker is not available"

        try:
            # Write Dockerfile to repo
            dockerfile_path = f"{repo_path}/Dockerfile.opentrace"
            with open(dockerfile_path, "w") as f:
                f.write(dockerfile_content)

            # Build image in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._build_sync,
                repo_path,
                image_tag,
                dockerfile_path
            )

            return True, None

        except Exception as e:
            logger.error(f"Failed to build image: {e}")
            return False, str(e)

    def _build_sync(self, repo_path: str, image_tag: str, dockerfile_path: str):
        """Synchronous Docker build operation."""
        self.client.images.build(
            path=repo_path,
            dockerfile="Dockerfile.opentrace",
            tag=image_tag,
            rm=True,  # Remove intermediate containers
            forcerm=True,  # Always remove intermediate containers
        )

    async def run_container(
        self,
        image_tag: str,
        container_name: str,
        port: int,
        host_port: int,
        service_name: str,
        otel_endpoint: str = "http://jaeger:4317",
        network: str = "opentrace-network"
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Run a container from an image.

        Args:
            image_tag: Docker image tag to run
            container_name: Name for the container
            port: Internal port the app listens on
            host_port: Host port to map to
            service_name: OpenTelemetry service name
            otel_endpoint: OpenTelemetry collector endpoint
            network: Docker network to connect to

        Returns:
            Tuple of (container_id, error_message)
        """
        if not self.is_available():
            return None, "Docker is not available"

        try:
            # Remove existing container with same name if exists
            try:
                existing = self.client.containers.get(container_name)
                existing.remove(force=True)
            except Exception:
                pass

            # Run container
            container = self.client.containers.run(
                image_tag,
                name=container_name,
                detach=True,
                ports={f"{port}/tcp": host_port},
                environment={
                    "OTEL_SERVICE_NAME": service_name,
                    "OTEL_EXPORTER_OTLP_ENDPOINT": otel_endpoint,
                },
                network=network,
            )

            return container.id, None

        except ImageNotFound:
            return None, f"Image {image_tag} not found. Did you build it first?"
        except APIError as e:
            return None, f"Docker API error: {e}"
        except Exception as e:
            logger.error(f"Failed to run container: {e}")
            return None, str(e)

    async def stop_container(self, container_id: str) -> tuple[bool, Optional[str]]:
        """
        Stop a running container.

        Args:
            container_id: ID of the container to stop

        Returns:
            Tuple of (success, error_message)
        """
        if not self.is_available():
            return False, "Docker is not available"

        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=10)
            container.remove()
            return True, None
        except Exception as e:
            logger.error(f"Failed to stop container: {e}")
            return False, str(e)

    def get_container_status(self, container_id: str) -> Optional[str]:
        """Get the status of a container."""
        if not self.is_available():
            return None

        try:
            container = self.client.containers.get(container_id)
            return container.status
        except Exception:
            return None

    def get_container_logs(self, container_id: str, tail: int = 100) -> Optional[str]:
        """Get recent logs from a container."""
        if not self.is_available():
            return None

        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=True)
            return logs.decode("utf-8")
        except Exception:
            return None


# Global runner instance
_runner: Optional[ContainerRunner] = None


def get_container_runner() -> ContainerRunner:
    """Get the global container runner instance."""
    global _runner
    if _runner is None:
        _runner = ContainerRunner()
    return _runner
