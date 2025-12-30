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
    libpq-dev \\
    && rm -rf /var/lib/apt/lists/*

# Copy all files first (dependency files may vary)
COPY . .

# Install Python dependencies with multiple fallback strategies
RUN if [ -f requirements.txt ]; then \\
        echo "Installing from requirements.txt..." && \\
        pip install --no-cache-dir -r requirements.txt; \\
    elif [ -f pyproject.toml ]; then \\
        echo "Installing from pyproject.toml..." && \\
        pip install --no-cache-dir poetry 2>/dev/null || true && \\
        if command -v poetry &> /dev/null && grep -q "tool.poetry" pyproject.toml 2>/dev/null; then \\
            echo "Using Poetry..." && \\
            poetry config virtualenvs.create false && \\
            poetry install --no-interaction --no-ansi || pip install --no-cache-dir . || true; \\
        else \\
            echo "Using pip with pyproject.toml..." && \\
            pip install --no-cache-dir . || pip install --no-cache-dir -e . || true; \\
        fi; \\
    elif [ -f setup.py ]; then \\
        echo "Installing from setup.py..." && \\
        pip install --no-cache-dir . || true; \\
    else \\
        echo "No dependency file found, skipping dependency installation"; \\
    fi

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

    # Build startup script content
    script_lines = ['#!/bin/sh']
    script_lines.append('')
    script_lines.append('# Try detected entrypoint first (most reliable)')
    if entrypoint:
        script_lines.append(f'if [ -f "{entrypoint}" ]; then')
        script_lines.append(f'    echo "Starting with detected entrypoint: {entrypoint}"')
        script_lines.append(f'    exec node "{entrypoint}"')
        script_lines.append('fi')
        script_lines.append('')
    
    # Try npm start, but catch errors
    script_lines.append('# Try npm start (if package.json has start script)')
    script_lines.append('if [ -f package.json ] && grep -q \'"start"\' package.json 2>/dev/null; then')
    script_lines.append('    echo "Attempting: npm start"')
    script_lines.append('    # Check if npm start would work by testing the command')
    script_lines.append('    START_SCRIPT=$(node -p "require(\'./package.json\').scripts?.start || \'\'" 2>/dev/null || echo "")')
    script_lines.append('    if [ -n "$START_SCRIPT" ]; then')
    script_lines.append('        # Extract JS file from command (e.g., "node index.js" -> "index.js")')
    script_lines.append('        JS_FILE=$(echo "$START_SCRIPT" | sed -n "s/.*node[[:space:]]*\\([^[:space:]]*\\.js\\).*/\\1/p" | head -1)')
    script_lines.append('        if [ -n "$JS_FILE" ] && [ ! -f "$JS_FILE" ]; then')
    script_lines.append('            echo "Warning: npm start references $JS_FILE which does not exist, skipping"')
    script_lines.append('        else')
    script_lines.append('            exec npm start')
    script_lines.append('        fi')
    script_lines.append('    else')
    script_lines.append('        exec npm start')
    script_lines.append('    fi')
    script_lines.append('fi')
    script_lines.append('')
    
    # Try common entrypoints
    script_lines.append('# Try common entrypoints')
    for common_file in ['index.js', 'app.js', 'server.js', 'src/index.js', 'src/app.js']:
        script_lines.append(f'if [ -f "{common_file}" ]; then')
        script_lines.append(f'    echo "Starting with: {common_file}"')
        script_lines.append(f'    exec node "{common_file}"')
        script_lines.append('fi')
    
    # Last resort: find any .js file in root
    script_lines.append('')
    script_lines.append('# Last resort: find any .js file in root directory')
    script_lines.append('JS_FILE=$(find /app -maxdepth 1 -name "*.js" -type f | head -1)')
    script_lines.append('if [ -n "$JS_FILE" ]; then')
    script_lines.append('    echo "Starting with found file: $JS_FILE"')
    script_lines.append('    exec node "$JS_FILE"')
    script_lines.append('fi')
    script_lines.append('')
    
    script_lines.append('echo "Error: No entrypoint found"')
    script_lines.append('echo "Available .js files:"')
    script_lines.append('find /app -name "*.js" -type f | head -10')
    script_lines.append('exit 1')
    
    script_content = '\n'.join(script_lines)

    dockerfile = f'''FROM node:20-slim

WORKDIR /app

# Install git for packages that need it
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy all files (package.json may or may not exist)
COPY . .

# Install dependencies with multiple fallback strategies
RUN if [ -f package.json ]; then \\
        echo "Installing from package.json..." && \\
        npm install --legacy-peer-deps --ignore-scripts 2>/dev/null || \\
        npm install --legacy-peer-deps 2>/dev/null || \\
        npm install 2>/dev/null || \\
        echo "npm install failed, continuing anyway..."; \\
    else \\
        echo "No package.json found, skipping npm install"; \\
    fi

# Install OpenTelemetry auto-instrumentation
RUN npm install --legacy-peer-deps \\
    @opentelemetry/api \\
    @opentelemetry/auto-instrumentations-node \\
    @opentelemetry/exporter-trace-otlp-grpc \\
    @opentelemetry/sdk-node 2>/dev/null || true

# Create startup script
RUN cat > /app/start.sh << 'EOF'
{script_content}
EOF
RUN chmod +x /app/start.sh

# Run npm rebuild to ensure native modules are properly built
RUN npm rebuild 2>/dev/null || true

# Environment variables for OpenTelemetry
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_EXPORTER_OTLP_PROTOCOL=grpc
ENV NODE_OPTIONS="--require @opentelemetry/auto-instrumentations-node/register"

EXPOSE {port}

CMD ["/app/start.sh"]
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
