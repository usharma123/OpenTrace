"""Manage repository analysis, building, and running."""

import os
import uuid
import asyncio
from pathlib import Path
from typing import Optional
import git
import logging

from ..config import get_settings
from ..models import RepoInfo, RepoStatus, RepoLanguage
from .analyzer import RepoAnalyzer
from .dockerfile_gen import generate_dockerfile
from .runner import get_container_runner

logger = logging.getLogger(__name__)


class RepoManager:
    """Manages the lifecycle of analyzed repositories."""

    def __init__(self):
        self.settings = get_settings()
        self.repos: dict[str, RepoInfo] = {}
        self._port_counter = 9000  # Start assigning ports from 9000

    def _get_next_port(self) -> int:
        """Get the next available port for a container."""
        port = self._port_counter
        self._port_counter += 1
        return port

    def _generate_repo_id(self, github_url: str) -> str:
        """Generate a unique repo ID from the GitHub URL."""
        # Extract repo name from URL
        parts = github_url.rstrip("/").split("/")
        if len(parts) >= 2:
            repo_name = f"{parts[-2]}-{parts[-1]}".replace(".git", "")
        else:
            repo_name = "repo"

        # Add short UUID for uniqueness
        short_id = str(uuid.uuid4())[:8]
        return f"{repo_name}-{short_id}"

    async def analyze(self, github_url: str, branch: Optional[str] = None) -> RepoInfo:
        """
        Analyze a GitHub repository.

        Args:
            github_url: URL of the GitHub repository
            branch: Optional branch to clone (default: main/master)

        Returns:
            RepoInfo with analysis results
        """
        repo_id = self._generate_repo_id(github_url)
        host_port = self._get_next_port()

        # Create initial repo info
        repo_info = RepoInfo(
            repoId=repo_id,
            githubUrl=github_url,
            status=RepoStatus.ANALYZING,
            port=host_port
        )
        self.repos[repo_id] = repo_info

        try:
            # Clone repository
            repo_path = Path(self.settings.repos_base_path) / repo_id
            repo_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Cloning {github_url} to {repo_path}")

            # Clone in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._clone_repo,
                github_url,
                str(repo_path),
                branch
            )

            # Analyze the repo
            analyzer = RepoAnalyzer(str(repo_path))
            analysis = analyzer.analyze()

            # Update repo info
            repo_info.language = analysis["language"]
            repo_info.framework = analysis["framework"]
            repo_info.entrypoint = analysis["entrypoint"]
            repo_info.status = RepoStatus.READY

            # Try to detect endpoints (simplified)
            if analysis["entrypoint"]:
                repo_info.endpoints = self._detect_endpoints(
                    repo_path,
                    analysis["language"],
                    analysis["entrypoint"]
                )

            self.repos[repo_id] = repo_info
            return repo_info

        except Exception as e:
            logger.error(f"Failed to analyze repo: {e}")
            repo_info.status = RepoStatus.ERROR
            repo_info.error_message = str(e)
            self.repos[repo_id] = repo_info
            return repo_info

    def _clone_repo(self, url: str, path: str, branch: Optional[str]):
        """Clone a git repository (synchronous)."""
        kwargs = {"depth": 1}  # Shallow clone for speed
        if branch:
            kwargs["branch"] = branch

        git.Repo.clone_from(url, path, **kwargs)

    def _detect_endpoints(
        self,
        repo_path: Path,
        language: RepoLanguage,
        entrypoint: str
    ) -> list[str]:
        """Try to detect API endpoints from the code (simplified)."""
        endpoints = []
        entry_file = repo_path / entrypoint

        if not entry_file.exists():
            return endpoints

        try:
            content = entry_file.read_text()

            if language == RepoLanguage.PYTHON:
                # Look for FastAPI/Flask route decorators
                import re
                patterns = [
                    r'@\w+\.(?:get|post|put|delete)\s*\(\s*["\']([^"\']+)["\']',
                    r'@router\.(?:get|post|put|delete)\s*\(\s*["\']([^"\']+)["\']',
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, content)
                    endpoints.extend(matches)

            elif language == RepoLanguage.NODEJS:
                # Look for Express/Fastify routes
                import re
                patterns = [
                    r'\.(?:get|post|put|delete)\s*\(\s*["\']([^"\']+)["\']',
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, content)
                    endpoints.extend(matches)

        except Exception as e:
            logger.warning(f"Failed to detect endpoints: {e}")

        return list(set(endpoints))[:20]  # Limit to 20 unique endpoints

    async def start(self, repo_id: str) -> Optional[RepoInfo]:
        """
        Build and start a repository container.

        Args:
            repo_id: ID of the repository to start

        Returns:
            Updated RepoInfo or None if not found
        """
        repo_info = self.repos.get(repo_id)
        if not repo_info:
            return None

        if repo_info.status not in [RepoStatus.READY, RepoStatus.STOPPED, RepoStatus.ERROR]:
            return repo_info

        try:
            repo_info.status = RepoStatus.BUILDING
            self.repos[repo_id] = repo_info

            repo_path = Path(self.settings.repos_base_path) / repo_id

            # Generate Dockerfile
            dockerfile = generate_dockerfile(
                language=repo_info.language,
                framework=repo_info.framework,
                entrypoint=repo_info.entrypoint,
                port=8000 if repo_info.language == RepoLanguage.PYTHON else 3000
            )

            # Build image
            runner = get_container_runner()
            image_tag = f"opentrace-{repo_id}:latest"

            success, error = await runner.build_image(
                str(repo_path),
                image_tag,
                dockerfile
            )

            if not success:
                repo_info.status = RepoStatus.ERROR
                repo_info.error_message = f"Build failed: {error}"
                self.repos[repo_id] = repo_info
                return repo_info

            # Run container
            internal_port = 8000 if repo_info.language == RepoLanguage.PYTHON else 3000
            container_name = f"opentrace-{repo_id}"
            service_name = repo_id.split("-")[0]  # Use repo name as service

            container_id, error = await runner.run_container(
                image_tag=image_tag,
                container_name=container_name,
                port=internal_port,
                host_port=repo_info.port,
                service_name=service_name
            )

            if not container_id:
                repo_info.status = RepoStatus.ERROR
                repo_info.error_message = f"Run failed: {error}"
                self.repos[repo_id] = repo_info
                return repo_info

            repo_info.container_id = container_id
            repo_info.status = RepoStatus.RUNNING
            repo_info.error_message = None
            self.repos[repo_id] = repo_info

            return repo_info

        except Exception as e:
            logger.error(f"Failed to start repo: {e}")
            repo_info.status = RepoStatus.ERROR
            repo_info.error_message = str(e)
            self.repos[repo_id] = repo_info
            return repo_info

    async def stop(self, repo_id: str) -> Optional[RepoInfo]:
        """
        Stop a running repository container.

        Args:
            repo_id: ID of the repository to stop

        Returns:
            Updated RepoInfo or None if not found
        """
        repo_info = self.repos.get(repo_id)
        if not repo_info:
            return None

        if repo_info.status != RepoStatus.RUNNING or not repo_info.container_id:
            return repo_info

        try:
            runner = get_container_runner()
            success, error = await runner.stop_container(repo_info.container_id)

            if success:
                repo_info.status = RepoStatus.STOPPED
                repo_info.container_id = None
            else:
                repo_info.error_message = f"Stop failed: {error}"

            self.repos[repo_id] = repo_info
            return repo_info

        except Exception as e:
            logger.error(f"Failed to stop repo: {e}")
            repo_info.error_message = str(e)
            self.repos[repo_id] = repo_info
            return repo_info

    def get_repo(self, repo_id: str) -> Optional[RepoInfo]:
        """Get repository info by ID."""
        return self.repos.get(repo_id)

    def list_repos(self) -> list[RepoInfo]:
        """List all repositories."""
        return list(self.repos.values())


# Global manager instance
_manager: Optional[RepoManager] = None


def get_repo_manager() -> RepoManager:
    """Get the global repo manager instance."""
    global _manager
    if _manager is None:
        _manager = RepoManager()
    return _manager
