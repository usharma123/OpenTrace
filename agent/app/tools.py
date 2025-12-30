"""Tool execution for the agent."""

import httpx
from typing import Any, Optional
import logging

from .config import get_settings
from .models import ActionRequest

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tools by calling the API service."""

    def __init__(self):
        self.settings = get_settings()
        self.api_url = self.settings.api_url

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a tool and return the result.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        try:
            if tool_name == "list_traces":
                return await self._list_traces(arguments)
            elif tool_name == "get_trace":
                return await self._get_trace(arguments)
            elif tool_name == "get_trace_analysis":
                return await self._get_trace_analysis(arguments)
            elif tool_name == "get_runtime_flow":
                return await self._get_runtime_flow(arguments)
            elif tool_name == "record_request":
                return await self._record_request(arguments)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}

    async def _list_traces(self, args: dict) -> dict:
        """List recent traces."""
        params = {}
        if args.get("service"):
            params["service"] = args["service"]
        if args.get("limit"):
            params["limit"] = args["limit"]

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.api_url}/traces/search",
                params=params
            )
            response.raise_for_status()
            return response.json()

    async def _get_trace(self, args: dict) -> dict:
        """Get full trace data."""
        trace_id = args.get("trace_id")
        if not trace_id:
            return {"error": "trace_id is required"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.api_url}/traces/{trace_id}")
            if response.status_code == 404:
                return {"error": f"Trace {trace_id} not found"}
            response.raise_for_status()
            return response.json()

    async def _get_trace_analysis(self, args: dict) -> dict:
        """Get automated trace analysis."""
        trace_id = args.get("trace_id")
        if not trace_id:
            return {"error": "trace_id is required"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.api_url}/traces/{trace_id}/analysis")
            if response.status_code == 404:
                return {"error": f"Trace {trace_id} not found"}
            response.raise_for_status()
            return response.json()

    async def _get_runtime_flow(self, args: dict) -> dict:
        """Get ReactFlow graph for a trace."""
        trace_id = args.get("trace_id")
        if not trace_id:
            return {"error": "trace_id is required"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.api_url}/flows/runtime/{trace_id}")
            if response.status_code == 404:
                return {"error": f"Trace {trace_id} not found"}
            response.raise_for_status()
            return response.json()

    async def _record_request(self, args: dict) -> dict:
        """
        Record a new trace.

        Note: This returns an action request that requires approval,
        rather than executing directly.
        """
        return {
            "action_required": True,
            "action": ActionRequest(
                actionType="record",
                description=f"Record {args.get('method', 'GET')} request to {args.get('path', '/')}",
                params=args,
                requiresApproval=self.settings.approval_required
            ).model_dump(by_alias=True)
        }


# Global executor instance
_executor: Optional[ToolExecutor] = None


def get_tool_executor() -> ToolExecutor:
    """Get the global tool executor instance."""
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor
