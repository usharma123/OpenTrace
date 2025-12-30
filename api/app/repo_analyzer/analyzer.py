"""Analyze GitHub repositories to detect language, framework, and entry points."""

import os
import json
import re
from pathlib import Path
from typing import Optional, Tuple
import toml

from ..models import RepoLanguage, RepoFramework


# Common subdirectory names for backend services
BACKEND_SUBDIRS = ["server", "backend", "api", "src/server", "src/api", "src/backend"]


class RepoAnalyzer:
    """Analyzes a cloned repository to detect its configuration."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.backend_subdir: Optional[str] = None  # Track if backend is in a subdirectory

    def _find_backend_subdir(self) -> Optional[str]:
        """
        Check if this is a monorepo and find the backend service subdirectory.
        Returns the subdirectory name if found, None otherwise.
        """
        for subdir in BACKEND_SUBDIRS:
            subdir_path = self.repo_path / subdir
            if subdir_path.exists() and subdir_path.is_dir():
                # Check if this subdir has Python backend indicators
                if any([
                    (subdir_path / "requirements.txt").exists(),
                    (subdir_path / "pyproject.toml").exists(),
                    (subdir_path / "app.py").exists(),
                    (subdir_path / "main.py").exists(),
                ]):
                    return subdir
                # Check if this subdir has Node.js backend indicators (with express/fastify)
                pkg_file = subdir_path / "package.json"
                if pkg_file.exists():
                    try:
                        data = json.loads(pkg_file.read_text())
                        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                        # Only consider it a backend if it has backend frameworks
                        if any(fw in deps for fw in ["express", "fastify", "@nestjs/core", "koa", "hapi"]):
                            return subdir
                    except Exception:
                        pass
        return None

    def _get_effective_path(self) -> Path:
        """Get the effective path for analysis (backend subdir or root)."""
        if self.backend_subdir:
            return self.repo_path / self.backend_subdir
        return self.repo_path

    def detect_language(self) -> RepoLanguage:
        """Detect the primary programming language of the repository."""
        # First, check if this is a monorepo with a backend subdirectory
        self.backend_subdir = self._find_backend_subdir()
        effective_path = self._get_effective_path()

        # Check for Python indicators (prioritize Python for backend services)
        if any([
            (effective_path / "requirements.txt").exists(),
            (effective_path / "pyproject.toml").exists(),
            (effective_path / "setup.py").exists(),
            (effective_path / "Pipfile").exists(),
        ]):
            return RepoLanguage.PYTHON

        # Check for Node.js indicators
        if (effective_path / "package.json").exists():
            return RepoLanguage.NODEJS

        # Check file extensions as fallback
        py_files = list(effective_path.glob("**/*.py"))
        js_files = list(effective_path.glob("**/*.js")) + list(effective_path.glob("**/*.ts"))

        if len(py_files) > len(js_files):
            return RepoLanguage.PYTHON
        elif len(js_files) > len(py_files):
            return RepoLanguage.NODEJS

        return RepoLanguage.UNKNOWN

    def detect_framework(self, language: RepoLanguage) -> RepoFramework:
        """Detect the web framework used by the repository."""
        if language == RepoLanguage.PYTHON:
            return self._detect_python_framework()
        elif language == RepoLanguage.NODEJS:
            return self._detect_nodejs_framework()
        return RepoFramework.UNKNOWN

    def _detect_python_framework(self) -> RepoFramework:
        """Detect Python web framework from dependencies."""
        effective_path = self._get_effective_path()

        # Check requirements.txt
        req_file = effective_path / "requirements.txt"
        if req_file.exists():
            content = req_file.read_text().lower()
            if "fastapi" in content:
                return RepoFramework.FASTAPI
            if "flask" in content:
                return RepoFramework.FLASK
            if "django" in content:
                return RepoFramework.DJANGO

        # Check pyproject.toml
        pyproject = effective_path / "pyproject.toml"
        if pyproject.exists():
            try:
                data = toml.load(pyproject)
                deps = []

                # Poetry dependencies
                if "tool" in data and "poetry" in data["tool"]:
                    deps.extend(data["tool"]["poetry"].get("dependencies", {}).keys())

                # PEP 621 dependencies
                if "project" in data:
                    deps.extend(data["project"].get("dependencies", []))

                deps_str = " ".join(str(d).lower() for d in deps)
                if "fastapi" in deps_str:
                    return RepoFramework.FASTAPI
                if "flask" in deps_str:
                    return RepoFramework.FLASK
                if "django" in deps_str:
                    return RepoFramework.DJANGO
            except Exception:
                pass

        return RepoFramework.UNKNOWN

    def _detect_nodejs_framework(self) -> RepoFramework:
        """Detect Node.js web framework from package.json."""
        effective_path = self._get_effective_path()
        pkg_file = effective_path / "package.json"
        if not pkg_file.exists():
            return RepoFramework.UNKNOWN

        try:
            data = json.loads(pkg_file.read_text())
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

            if "@nestjs/core" in deps:
                return RepoFramework.NESTJS
            if "fastify" in deps:
                return RepoFramework.FASTIFY
            if "express" in deps:
                return RepoFramework.EXPRESS

        except Exception:
            pass

        return RepoFramework.UNKNOWN

    def find_entrypoint(self, language: RepoLanguage, framework: RepoFramework) -> Optional[str]:
        """Find the application entry point."""
        if language == RepoLanguage.PYTHON:
            return self._find_python_entrypoint(framework)
        elif language == RepoLanguage.NODEJS:
            return self._find_nodejs_entrypoint()
        return None

    def _find_python_entrypoint(self, framework: RepoFramework) -> Optional[str]:
        """Find Python application entry point."""
        effective_path = self._get_effective_path()

        # Common entry point files
        candidates = [
            "main.py",
            "app.py",
            "app/main.py",
            "src/main.py",
            "src/app.py",
            "server.py",
            "run.py",
        ]

        for candidate in candidates:
            path = effective_path / candidate
            if path.exists():
                # Verify it has a FastAPI/Flask/Django app
                content = path.read_text()
                if framework == RepoFramework.FASTAPI and "FastAPI" in content:
                    return candidate
                if framework == RepoFramework.FLASK and "Flask" in content:
                    return candidate
                if framework == RepoFramework.DJANGO:
                    return candidate
                # If framework unknown, just return if it looks like an app
                if "app" in content.lower() or "application" in content.lower():
                    return candidate

        # Check pyproject.toml for scripts
        pyproject = effective_path / "pyproject.toml"
        if pyproject.exists():
            try:
                data = toml.load(pyproject)
                # Poetry scripts
                scripts = data.get("tool", {}).get("poetry", {}).get("scripts", {})
                if scripts:
                    return list(scripts.values())[0]
            except Exception:
                pass

        return None

    def _find_nodejs_entrypoint(self) -> Optional[str]:
        """Find Node.js application entry point."""
        pkg_file = self.repo_path / "package.json"
        if pkg_file.exists():
            try:
                data = json.loads(pkg_file.read_text())

                # Check main field
                main = data.get("main")
                if main:
                    return main

                # Check scripts.start
                start_script = data.get("scripts", {}).get("start", "")
                # Extract file from "node index.js" or similar
                match = re.search(r"node\s+([^\s]+)", start_script)
                if match:
                    return match.group(1)

            except Exception:
                pass

        # Common entry points
        for candidate in ["index.js", "app.js", "server.js", "src/index.js", "src/app.js"]:
            if (self.repo_path / candidate).exists():
                return candidate

        return None

    def detect_port(self, language: RepoLanguage, framework: RepoFramework) -> int:
        """Detect the port the application listens on."""
        # Default ports by framework
        default_ports = {
            RepoFramework.FASTAPI: 8000,
            RepoFramework.FLASK: 5000,
            RepoFramework.DJANGO: 8000,
            RepoFramework.EXPRESS: 3000,
            RepoFramework.FASTIFY: 3000,
            RepoFramework.NESTJS: 3000,
        }

        # Try to find port in code
        entrypoint = self.find_entrypoint(language, framework)
        if entrypoint:
            entry_path = self.repo_path / entrypoint
            if entry_path.exists():
                content = entry_path.read_text()
                # Look for port definitions
                port_patterns = [
                    r'port\s*[=:]\s*(\d+)',
                    r'PORT\s*[=:]\s*(\d+)',
                    r'\.listen\s*\(\s*(\d+)',
                ]
                for pattern in port_patterns:
                    match = re.search(pattern, content)
                    if match:
                        return int(match.group(1))

        return default_ports.get(framework, 8000)

    def analyze(self) -> dict:
        """
        Perform full analysis of the repository.

        Returns dict with language, framework, entrypoint, and port.
        """
        language = self.detect_language()
        framework = self.detect_framework(language)
        entrypoint = self.find_entrypoint(language, framework)
        port = self.detect_port(language, framework)

        return {
            "language": language,
            "framework": framework,
            "entrypoint": entrypoint,
            "port": port,
        }
