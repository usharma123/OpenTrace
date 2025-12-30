"""Tests for trace to ReactFlow graph conversion."""

import pytest
from app.trace_to_graph import (
    trace_to_reactflow,
    find_critical_path,
    find_slowest_spans,
    find_error_spans,
    extract_tag_value,
    has_error,
    get_parent_span_id,
)


# Sample Jaeger trace data for testing
SAMPLE_TRACE = {
    "traceID": "abc123def456",
    "spans": [
        {
            "traceID": "abc123def456",
            "spanID": "span1",
            "operationName": "HTTP GET /api/users",
            "references": [],
            "startTime": 1700000000000000,  # microseconds
            "duration": 150000,  # 150ms in microseconds
            "tags": [
                {"key": "http.method", "value": "GET"},
                {"key": "http.status_code", "value": 200},
            ],
            "logs": [],
            "processID": "p1"
        },
        {
            "traceID": "abc123def456",
            "spanID": "span2",
            "operationName": "db-query",
            "references": [{"refType": "CHILD_OF", "spanID": "span1"}],
            "startTime": 1700000000050000,
            "duration": 50000,  # 50ms
            "tags": [
                {"key": "db.system", "value": "postgresql"},
                {"key": "db.statement", "value": "SELECT * FROM users"},
            ],
            "logs": [],
            "processID": "p1"
        },
        {
            "traceID": "abc123def456",
            "spanID": "span3",
            "operationName": "cache-lookup",
            "references": [{"refType": "CHILD_OF", "spanID": "span1"}],
            "startTime": 1700000000100000,
            "duration": 20000,  # 20ms
            "tags": [
                {"key": "cache.hit", "value": True},
            ],
            "logs": [],
            "processID": "p1"
        },
    ],
    "processes": {
        "p1": {"serviceName": "user-service", "tags": []}
    }
}


TRACE_WITH_ERRORS = {
    "traceID": "error123",
    "spans": [
        {
            "traceID": "error123",
            "spanID": "err1",
            "operationName": "HTTP POST /api/orders",
            "references": [],
            "startTime": 1700000000000000,
            "duration": 200000,
            "tags": [
                {"key": "http.status_code", "value": 500},
                {"key": "error", "value": True},
            ],
            "logs": [],
            "processID": "p1"
        },
        {
            "traceID": "error123",
            "spanID": "err2",
            "operationName": "db-insert",
            "references": [{"refType": "CHILD_OF", "spanID": "err1"}],
            "startTime": 1700000000050000,
            "duration": 100000,
            "tags": [
                {"key": "otel.status_code", "value": "ERROR"},
            ],
            "logs": [],
            "processID": "p1"
        },
    ],
    "processes": {
        "p1": {"serviceName": "order-service", "tags": []}
    }
}


class TestExtractTagValue:
    def test_extract_existing_tag(self):
        tags = [{"key": "http.method", "value": "GET"}]
        assert extract_tag_value(tags, "http.method") == "GET"

    def test_extract_missing_tag(self):
        tags = [{"key": "http.method", "value": "GET"}]
        assert extract_tag_value(tags, "missing") is None

    def test_extract_from_empty_tags(self):
        assert extract_tag_value([], "any") is None


class TestHasError:
    def test_no_error(self):
        span = {"tags": [{"key": "http.status_code", "value": 200}]}
        assert has_error(span) is False

    def test_error_tag_true(self):
        span = {"tags": [{"key": "error", "value": True}]}
        assert has_error(span) is True

    def test_http_500(self):
        span = {"tags": [{"key": "http.status_code", "value": 500}]}
        assert has_error(span) is True

    def test_http_503(self):
        span = {"tags": [{"key": "http.status_code", "value": 503}]}
        assert has_error(span) is True

    def test_otel_error_status(self):
        span = {"tags": [{"key": "otel.status_code", "value": "ERROR"}]}
        assert has_error(span) is True


class TestGetParentSpanId:
    def test_with_parent(self):
        span = {"references": [{"refType": "CHILD_OF", "spanID": "parent1"}]}
        assert get_parent_span_id(span) == "parent1"

    def test_no_parent(self):
        span = {"references": []}
        assert get_parent_span_id(span) is None

    def test_follows_from_not_parent(self):
        span = {"references": [{"refType": "FOLLOWS_FROM", "spanID": "other"}]}
        assert get_parent_span_id(span) is None


class TestTraceToReactflow:
    def test_converts_trace_to_graph(self):
        graph = trace_to_reactflow(SAMPLE_TRACE)

        # Check metadata
        assert graph.meta.trace_id == "abc123def456"
        assert graph.meta.span_count == 3
        assert graph.meta.service_count == 1

        # Check nodes
        assert len(graph.nodes) == 3
        node_ids = {n.id for n in graph.nodes}
        assert "span:span1" in node_ids
        assert "span:span2" in node_ids
        assert "span:span3" in node_ids

        # Check edges (2 children of span1)
        assert len(graph.edges) == 2
        edge_targets = {e.target for e in graph.edges}
        assert "span:span2" in edge_targets
        assert "span:span3" in edge_targets

    def test_node_data_populated(self):
        graph = trace_to_reactflow(SAMPLE_TRACE)

        root_node = next(n for n in graph.nodes if n.id == "span:span1")
        assert root_node.data.operation_name == "HTTP GET /api/users"
        assert root_node.data.service_name == "user-service"
        assert root_node.data.duration_ms == 150.0  # Converted from microseconds
        assert root_node.data.status == "success"
        assert root_node.data.tags.get("http.status_code") == 200

    def test_error_status_detected(self):
        graph = trace_to_reactflow(TRACE_WITH_ERRORS)

        error_node = next(n for n in graph.nodes if n.id == "span:err1")
        assert error_node.data.status == "error"

    def test_error_edges_animated(self):
        graph = trace_to_reactflow(TRACE_WITH_ERRORS)

        # Edge to error span should be animated
        error_edge = next(e for e in graph.edges if e.target == "span:err2")
        assert error_edge.animated is True

    def test_empty_trace(self):
        empty_trace = {"traceID": "empty", "spans": [], "processes": {}}
        graph = trace_to_reactflow(empty_trace)

        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
        assert graph.meta.span_count == 0


class TestFindCriticalPath:
    def test_finds_longest_path(self):
        path = find_critical_path(SAMPLE_TRACE)

        # Should find the path through span1 -> span2 (longest duration path)
        assert "span1" in path
        assert len(path) >= 1

    def test_empty_trace(self):
        empty_trace = {"traceID": "empty", "spans": []}
        path = find_critical_path(empty_trace)
        assert path == []


class TestFindSlowestSpans:
    def test_finds_slowest(self):
        slowest = find_slowest_spans(SAMPLE_TRACE, n=2)

        assert len(slowest) == 2
        # Slowest should be span1 (150ms), then span2 (50ms)
        assert slowest[0]["spanID"] == "span1"
        assert slowest[1]["spanID"] == "span2"

    def test_limit_results(self):
        slowest = find_slowest_spans(SAMPLE_TRACE, n=1)
        assert len(slowest) == 1


class TestFindErrorSpans:
    def test_finds_errors(self):
        errors = find_error_spans(TRACE_WITH_ERRORS)

        assert len(errors) == 2
        error_ids = {s["spanID"] for s in errors}
        assert "err1" in error_ids
        assert "err2" in error_ids

    def test_no_errors(self):
        errors = find_error_spans(SAMPLE_TRACE)
        assert len(errors) == 0
