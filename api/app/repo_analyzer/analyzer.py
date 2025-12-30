"""Analyze GitHub repositories to detect language, framework, and entry points."""

import os
import json
import re
from pathlib import Path
from typing import Optional, Tuple
import toml

from ..models import RepoLanguage, RepoFramework


class RepoAnalyzer:
    """Analyzes a cloned repository to detect its configuration."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def detect_language(self) -> RepoLanguage:
        """Detect the primary programming language of the repository."""
        # Check for Node.js indicators
        if (self.repo_path / "package.json").exists():
            return RepoLanguage.NODEJS

        # Check for Python indicators
        if any([
            (self.repo_path / "requirements.txt").exists(),
            (self.repo_path / "pyproject.toml").exists(),
            (self.repo_path / "setup.py").exists(),
            (self.repo_path / "Pipfile").exists(),
        ]):
            return RepoLanguage.PYTHON

        # Check file extensions as fallback
        py_files = list(self.repo_path.glob("**/*.py"))
        js_files = list(self.repo_path.glob("**/*.js")) + list(self.repo_path.glob("**/*.ts"))

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
        # Check requirements.txt
        req_file = self.repo_path / "requirements.txt"
        if req_file.exists():
            content = req_file.read_text().lower()
            if "fastapi" in content:
                return RepoFramework.FASTAPI
            if "flask" in content:
                return RepoFramework.FLASK
            if "django" in content:
                return RepoFramework.DJANGO

        # Check pyproject.toml
        pyproject = self.repo_path / "pyproject.toml"
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
        pkg_file = self.repo_path / "package.json"
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
            path = self.repo_path / candidate
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
        pyproject = self.repo_path / "pyproject.toml"
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
