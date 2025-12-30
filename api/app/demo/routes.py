"""Demo endpoints for generating interesting traces."""

import asyncio
import random
from fastapi import APIRouter, HTTPException
import httpx
from opentelemetry import trace

router = APIRouter(prefix="/demo", tags=["demo"])

# Get tracer for manual spans
tracer = trace.get_tracer(__name__)


@router.get("/fast")
async def demo_fast():
    """A fast endpoint that returns immediately."""
    return {
        "status": "ok",
        "latency": "fast",
        "message": "This endpoint completes quickly"
    }


@router.get("/slow")
async def demo_slow():
    """A slow endpoint that simulates processing delay."""
    # Create a custom span for the "processing" work
    with tracer.start_as_current_span("slow-processing") as span:
        delay = random.uniform(0.3, 0.8)
        span.set_attribute("delay_seconds", delay)
        await asyncio.sleep(delay)

    return {
        "status": "ok",
        "latency": "slow",
        "delay_ms": int(delay * 1000),
        "message": "This endpoint simulates slow processing"
    }


@router.get("/external")
async def demo_external():
    """An endpoint that makes an external HTTP call."""
    with tracer.start_as_current_span("external-call") as span:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Call httpbin - a simple HTTP testing service
                span.set_attribute("external.url", "https://httpbin.org/get")
                response = await client.get("https://httpbin.org/get")
                span.set_attribute("external.status_code", response.status_code)

                return {
                    "status": "ok",
                    "external_status": response.status_code,
                    "message": "Successfully called external API"
                }
        except httpx.TimeoutException:
            # Simulate external call if no internet
            span.set_attribute("external.simulated", True)
            await asyncio.sleep(0.1)
            return {
                "status": "ok",
                "external_status": 200,
                "simulated": True,
                "message": "Simulated external call (no internet)"
            }
        except Exception as e:
            span.set_attribute("external.error", str(e))
            span.set_attribute("external.simulated", True)
            await asyncio.sleep(0.1)
            return {
                "status": "ok",
                "external_status": 200,
                "simulated": True,
                "message": f"Simulated external call (error: {str(e)[:50]})"
            }


@router.get("/error")
async def demo_error():
    """An endpoint that always returns a 500 error."""
    with tracer.start_as_current_span("error-operation") as span:
        span.set_attribute("error.intentional", True)
        span.set_attribute("error.type", "demo_error")

    raise HTTPException(
        status_code=500,
        detail="This is an intentional error for testing"
    )


@router.get("/db")
async def demo_db():
    """Simulates a database operation."""
    with tracer.start_as_current_span("db-query") as span:
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.operation", "SELECT")
        span.set_attribute("db.statement", "SELECT * FROM users LIMIT 100")

        # Simulate query time
        query_time = random.uniform(0.01, 0.1)
        await asyncio.sleep(query_time)

        span.set_attribute("db.rows_affected", 42)

    return {
        "status": "ok",
        "records": 42,
        "query_time_ms": int(query_time * 1000),
        "message": "Simulated database query"
    }


@router.get("/chain")
async def demo_chain():
    """
    An endpoint that creates a chain of nested operations.
    Useful for testing trace visualization with depth.
    """
    results = []

    with tracer.start_as_current_span("chain-step-1") as span1:
        span1.set_attribute("step", 1)
        await asyncio.sleep(0.05)
        results.append("step1")

        with tracer.start_as_current_span("chain-step-2") as span2:
            span2.set_attribute("step", 2)
            await asyncio.sleep(0.08)
            results.append("step2")

            with tracer.start_as_current_span("chain-step-3") as span3:
                span3.set_attribute("step", 3)
                await asyncio.sleep(0.03)
                results.append("step3")

    return {
        "status": "ok",
        "chain": results,
        "depth": len(results),
        "message": "Completed chain of nested operations"
    }


@router.get("/parallel")
async def demo_parallel():
    """
    An endpoint that runs multiple operations in parallel.
    Creates a fan-out pattern in the trace.
    """
    async def worker(name: str, delay: float) -> dict:
        with tracer.start_as_current_span(f"parallel-worker-{name}") as span:
            span.set_attribute("worker.name", name)
            span.set_attribute("worker.delay", delay)
            await asyncio.sleep(delay)
            return {"name": name, "delay_ms": int(delay * 1000)}

    with tracer.start_as_current_span("parallel-coordinator") as span:
        span.set_attribute("worker_count", 3)

        # Run workers in parallel
        results = await asyncio.gather(
            worker("alpha", random.uniform(0.1, 0.2)),
            worker("beta", random.uniform(0.15, 0.25)),
            worker("gamma", random.uniform(0.05, 0.15)),
        )

    return {
        "status": "ok",
        "workers": results,
        "message": "Completed parallel operations"
    }


@router.get("/mixed")
async def demo_mixed():
    """
    A realistic endpoint that combines multiple types of operations:
    - Input validation
    - Database query
    - External API call
    - Response formatting
    """
    with tracer.start_as_current_span("validate-input") as span:
        span.set_attribute("validation.fields", 5)
        await asyncio.sleep(0.01)

    with tracer.start_as_current_span("db-lookup") as span:
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.operation", "SELECT")
        db_time = random.uniform(0.02, 0.08)
        await asyncio.sleep(db_time)
        span.set_attribute("db.rows_affected", 1)

    with tracer.start_as_current_span("enrich-from-cache") as span:
        span.set_attribute("cache.system", "redis")
        cache_hit = random.choice([True, False])
        span.set_attribute("cache.hit", cache_hit)
        await asyncio.sleep(0.005 if cache_hit else 0.02)

    with tracer.start_as_current_span("format-response") as span:
        span.set_attribute("response.format", "json")
        await asyncio.sleep(0.005)

    return {
        "status": "ok",
        "data": {
            "id": 12345,
            "name": "Demo User",
            "enriched": True
        },
        "cache_hit": cache_hit,
        "message": "Completed mixed operation workflow"
    }
