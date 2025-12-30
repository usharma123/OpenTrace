"""Agent-based repository analyzer using LLM to understand and generate Dockerfiles."""

import os
import json
import httpx
from pathlib import Path
from typing import Optional
import logging

from ..config import get_settings

logger = logging.getLogger(__name__)


ANALYZE_PROMPT = """You are an expert DevOps engineer. Analyze this repository and generate a Dockerfile to run the BACKEND service.

## Repository Structure:
{file_tree}

## Key Files Content:
{file_contents}

## Your Task:
1. Identify the backend/API service (not frontend)
2. Determine the language and framework
3. Generate a Dockerfile that:
   - Uses an appropriate base image
   - Installs dependencies
   - Sets up OpenTelemetry instrumentation for tracing
   - Exposes the correct port
   - Has a proper CMD to start the server

## Response Format (JSON):
{{
    "language": "python" or "nodejs",
    "framework": "fastapi" or "flask" or "django" or "express" or "fastify" or "nestjs" or "unknown",
    "backend_dir": "path/to/backend" or "." if root,
    "entrypoint": "main.py" or "app.py" or "index.js" etc,
    "port": 8000,
    "dockerfile": "FROM python:3.11-slim\\n...(full Dockerfile content)",
    "explanation": "Brief explanation of what you found and how to run it"
}}

Important:
- For Python: Add OpenTelemetry instrumentation packages and use `opentelemetry-instrument` wrapper
- For Node.js: Add @opentelemetry packages and set NODE_OPTIONS for auto-instrumentation
- The service must listen on 0.0.0.0, not localhost
- Include OTEL_TRACES_EXPORTER=otlp and OTEL_EXPORTER_OTLP_PROTOCOL=grpc env vars

Return ONLY valid JSON, no markdown code blocks."""


class AgentAnalyzer:
    """Uses LLM to analyze repositories and generate Dockerfiles."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.settings = get_settings()

    def _get_file_tree(self, max_depth: int = 3) -> str:
        """Generate a file tree representation of the repository."""
        lines = []

        def walk(path: Path, prefix: str = "", depth: int = 0):
            if depth > max_depth:
                return

            # Skip common non-essential directories
            skip_dirs = {'.git', 'node_modules', '__pycache__', '.venv', 'venv',
                        'dist', 'build', '.next', '.cache', 'coverage'}

            try:
                entries = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
            except PermissionError:
                return

            dirs = [e for e in entries if e.is_dir() and e.name not in skip_dirs]
            files = [e for e in entries if e.is_file()]

            for f in files[:20]:  # Limit files per directory
                lines.append(f"{prefix}{f.name}")

            for d in dirs[:10]:  # Limit subdirectories
                lines.append(f"{prefix}{d.name}/")
                walk(d, prefix + "  ", depth + 1)

        walk(self.repo_path)
        return "\n".join(lines[:100])  # Limit total lines

    def _read_key_files(self) -> str:
        """Read contents of key configuration files."""
        key_files = [
            "README.md",
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
            # Common backend locations
            "server/package.json",
            "server/requirements.txt",
            "backend/package.json",
            "backend/requirements.txt",
            "api/package.json",
            "api/requirements.txt",
            # Entry points
            "main.py",
            "app.py",
            "server.py",
            "index.js",
            "app.js",
            "server/app.py",
            "server/main.py",
            "backend/app.py",
            "backend/main.py",
        ]

        contents = []
        for file_path in key_files:
            full_path = self.repo_path / file_path
            if full_path.exists() and full_path.is_file():
                try:
                    content = full_path.read_text()
                    # Truncate large files
                    if len(content) > 3000:
                        content = content[:3000] + "\n... (truncated)"
                    contents.append(f"=== {file_path} ===\n{content}")
                except Exception as e:
                    logger.warning(f"Failed to read {file_path}: {e}")

        return "\n\n".join(contents) if contents else "No key files found"

    async def analyze(self) -> dict:
        """
        Use LLM to analyze the repository and generate build configuration.

        Returns:
            Dict with language, framework, backend_dir, entrypoint, port, dockerfile, explanation
        """
        # Check if OpenRouter is configured
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            logger.warning("OPENROUTER_API_KEY not set, falling back to heuristic analyzer")
            return await self._fallback_analyze()

        file_tree = self._get_file_tree()
        file_contents = self._read_key_files()

        prompt = ANALYZE_PROMPT.format(
            file_tree=file_tree,
            file_contents=file_contents
        )

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "https://opentrace.local",
                        "X-Title": "OpenTrace",
                    },
                    json={
                        "model": os.environ.get("OPENROUTER_MODEL", "minimax/minimax-m2.1"),
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,  # Low temperature for consistent output
                    },
                )

                if response.status_code != 200:
                    logger.error(f"OpenRouter error: {response.status_code} - {response.text}")
                    return await self._fallback_analyze()

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # Parse JSON response
                # Handle potential markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]

                analysis = json.loads(content.strip())
                logger.info(f"Agent analysis: {analysis.get('explanation', 'No explanation')}")
                return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return await self._fallback_analyze()
        except Exception as e:
            logger.error(f"Agent analysis failed: {e}")
            return await self._fallback_analyze()

    async def _fallback_analyze(self) -> dict:
        """Fallback to basic heuristic analysis if LLM is unavailable."""
        from .analyzer import RepoAnalyzer
        from .dockerfile_gen import generate_dockerfile
        from ..models import RepoLanguage

        analyzer = RepoAnalyzer(str(self.repo_path))
        result = analyzer.analyze()

        # Generate dockerfile using the old method
        try:
            dockerfile = generate_dockerfile(
                language=result["language"],
                framework=result["framework"],
                entrypoint=result["entrypoint"],
                port=result["port"]
            )
        except Exception:
            dockerfile = None

        return {
            "language": result["language"].value if result["language"] else "unknown",
            "framework": result["framework"].value if result["framework"] else "unknown",
            "backend_dir": analyzer.backend_subdir or ".",
            "entrypoint": result["entrypoint"],
            "port": result["port"],
            "dockerfile": dockerfile,
            "explanation": "Fallback heuristic analysis (LLM unavailable)"
        }
