"""Generate static architecture graph from OpenAPI spec."""

from typing import Optional
from fastapi import FastAPI
from fastapi.routing import APIRoute
from .models import FlowGraph, FlowNode, FlowEdge, FlowMeta, NodeData, EdgeData


def get_route_group(path: str) -> str:
    """Extract the route group (first path segment) from a path."""
    parts = path.strip("/").split("/")
    if parts and parts[0]:
        return parts[0]
    return "root"


def openapi_to_static_graph(app: FastAPI) -> FlowGraph:
    """
    Generate a static architecture graph from a FastAPI app's routes.

    Creates:
    - One node per unique route group (service-like grouping)
    - One node per route endpoint
    - Edges connecting route groups to their endpoints
    """
    nodes: list[FlowNode] = []
    edges: list[FlowEdge] = []
    route_groups: dict[str, list[str]] = {}

    # Collect routes by group
    for route in app.routes:
        if isinstance(route, APIRoute):
            path = route.path
            methods = list(route.methods - {"HEAD", "OPTIONS"})
            group = get_route_group(path)

            if group not in route_groups:
                route_groups[group] = []

            for method in methods:
                route_id = f"route:{method}:{path}"
                route_groups[group].append(route_id)

                # Create route node
                node = FlowNode(
                    id=route_id,
                    type="route",
                    position={"x": 0, "y": 0},
                    data=NodeData(
                        spanId=route_id,
                        operationName=f"{method} {path}",
                        serviceName=group,
                        duration=0,
                        startTime=0,
                        status="success",
                        tags={"method": method, "path": path}
                    )
                )
                nodes.append(node)

    # Create group nodes and edges
    for group, route_ids in route_groups.items():
        group_id = f"group:{group}"

        # Create group node
        group_node = FlowNode(
            id=group_id,
            type="service",
            position={"x": 0, "y": 0},
            data=NodeData(
                spanId=group_id,
                operationName=f"/{group}",
                serviceName=group,
                duration=0,
                startTime=0,
                status="success",
                tags={"type": "group", "route_count": len(route_ids)}
            )
        )
        nodes.append(group_node)

        # Create edges from group to routes
        for route_id in route_ids:
            edge = FlowEdge(
                id=f"edge:{group_id}-{route_id}",
                source=group_id,
                target=route_id,
                data=EdgeData(type="contains")
            )
            edges.append(edge)

    meta = FlowMeta(
        version="static",
        spanCount=len(nodes),
        serviceCount=len(route_groups)
    )

    return FlowGraph(nodes=nodes, edges=edges, meta=meta)


def merge_static_and_runtime(
    static_graph: FlowGraph,
    runtime_graph: FlowGraph
) -> FlowGraph:
    """
    Merge static architecture graph with runtime trace graph.

    The static graph provides the architectural context,
    while the runtime graph shows actual execution.
    """
    # Start with static nodes (marked as background)
    merged_nodes = []
    for node in static_graph.nodes:
        # Mark static nodes differently
        node_dict = node.model_dump()
        node_dict["type"] = f"static-{node.type}"
        merged_nodes.append(FlowNode(**node_dict))

    # Add runtime nodes
    for node in runtime_graph.nodes:
        merged_nodes.append(node)

    # Combine edges
    merged_edges = list(static_graph.edges) + list(runtime_graph.edges)

    # Create merged metadata
    meta = FlowMeta(
        traceId=runtime_graph.meta.trace_id,
        totalDurationMs=runtime_graph.meta.total_duration_ms,
        spanCount=len(merged_nodes),
        serviceCount=static_graph.meta.service_count,
        version="overlay"
    )

    return FlowGraph(nodes=merged_nodes, edges=merged_edges, meta=meta)
