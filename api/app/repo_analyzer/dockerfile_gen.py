"""Generate instrumented Dockerfiles for different languages and frameworks."""

from ..models import RepoLanguage, RepoFramework


def generate_python_dockerfile(
    framework: RepoFramework,
    entrypoint: str,
    port: int = 8000
) -> str:
    """Generate a Dockerfile for Python applications with OTel instrumentation."""

    # Determine the run command based on framework
    if framework == RepoFramework.FASTAPI:
        # Try to parse the module:app pattern from entrypoint
        if entrypoint:
            # Convert path to module notation
            module = entrypoint.replace("/", ".").replace(".py", "")
            run_cmd = f'["opentelemetry-instrument", "uvicorn", "{module}:app", "--host", "0.0.0.0", "--port", "{port}"]'
        else:
            run_cmd = f'["opentelemetry-instrument", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "{port}"]'
    elif framework == RepoFramework.FLASK:
        if entrypoint:
            module = entrypoint.replace("/", ".").replace(".py", "")
            run_cmd = f'["opentelemetry-instrument", "flask", "run", "--host", "0.0.0.0", "--port", "{port}"]'
        else:
            run_cmd = f'["opentelemetry-instrument", "flask", "run", "--host", "0.0.0.0", "--port", "{port}"]'
    elif framework == RepoFramework.DJANGO:
        run_cmd = f'["opentelemetry-instrument", "python", "manage.py", "runserver", "0.0.0.0:{port}"]'
    else:
        # Generic Python app
        if entrypoint:
            run_cmd = f'["opentelemetry-instrument", "python", "{entrypoint}"]'
        else:
            run_cmd = '["opentelemetry-instrument", "python", "main.py"]'

    dockerfile = f'''FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better caching
COPY requirements.txt* pyproject.toml* setup.py* ./

# Install Python dependencies
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi
RUN if [ -f pyproject.toml ]; then pip install --no-cache-dir .; fi

# Install OpenTelemetry instrumentation
RUN pip install --no-cache-dir \\
    opentelemetry-distro \\
    opentelemetry-exporter-otlp \\
    opentelemetry-instrumentation-fastapi \\
    opentelemetry-instrumentation-flask \\
    opentelemetry-instrumentation-django \\
    opentelemetry-instrumentation-httpx \\
    opentelemetry-instrumentation-requests \\
    opentelemetry-instrumentation-sqlalchemy \\
    opentelemetry-instrumentation-redis \\
    opentelemetry-instrumentation-psycopg2

# Auto-install all available instrumentations
RUN opentelemetry-bootstrap -a install || true

# Copy application code
COPY . .

# Environment variables for OpenTelemetry
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_EXPORTER_OTLP_PROTOCOL=grpc
ENV OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true

EXPOSE {port}

CMD {run_cmd}
'''
    return dockerfile


def generate_nodejs_dockerfile(
    framework: RepoFramework,
    entrypoint: str,
    port: int = 3000
) -> str:
    """Generate a Dockerfile for Node.js applications with OTel instrumentation."""

    if entrypoint:
        run_cmd = f'["node", "{entrypoint}"]'
    else:
        run_cmd = '["node", "index.js"]'

    dockerfile = f'''FROM node:20-slim

WORKDIR /app

# Copy package files first for better caching
COPY package*.json ./

# Install dependencies
RUN npm install

# Install OpenTelemetry auto-instrumentation
RUN npm install \\
    @opentelemetry/api \\
    @opentelemetry/auto-instrumentations-node \\
    @opentelemetry/exporter-trace-otlp-grpc \\
    @opentelemetry/sdk-node

# Copy application code
COPY . .

# Environment variables for OpenTelemetry
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_EXPORTER_OTLP_PROTOCOL=grpc
ENV NODE_OPTIONS="--require @opentelemetry/auto-instrumentations-node/register"

EXPOSE {port}

CMD {run_cmd}
'''
    return dockerfile


def generate_dockerfile(
    language: RepoLanguage,
    framework: RepoFramework,
    entrypoint: str,
    port: int
) -> str:
    """
    Generate an instrumented Dockerfile for the given configuration.

    Args:
        language: Programming language of the repository
        framework: Web framework being used
        entrypoint: Application entry point file
        port: Port the application listens on

    Returns:
        Dockerfile content as a string
    """
    if language == RepoLanguage.PYTHON:
        return generate_python_dockerfile(framework, entrypoint, port)
    elif language == RepoLanguage.NODEJS:
        return generate_nodejs_dockerfile(framework, entrypoint, port)
    else:
        raise ValueError(f"Unsupported language: {language}")
