"""Agent planner for orchestrating LLM interactions and tool calls."""

import json
import logging
from typing import Optional

from .config import get_settings
from .models import AgentResponse, Evidence, UIHints, ChatRequest
from .openrouter import get_openrouter_client, TOOLS
from .tools import get_tool_executor
from .fallback import (
    analyze_query,
    analyze_trace_for_slowness,
    analyze_trace_for_errors,
    explain_trace,
    generate_record_action,
    no_trace_response,
    unknown_intent_response,
)

logger = logging.getLogger(__name__)


class AgentPlanner:
    """Orchestrates agent responses using LLM or fallback logic."""

    def __init__(self):
        self.settings = get_settings()
        self.openrouter = get_openrouter_client()
        self.tool_executor = get_tool_executor()

    async def process_message(self, request: ChatRequest) -> AgentResponse:
        """
        Process a user message and return an agent response.

        Uses LLM if available, otherwise falls back to rule-based analysis.
        """
        # Check if we have an LLM available
        if self.openrouter.is_available():
            return await self._process_with_llm(request)
        else:
            return await self._process_with_fallback(request)

    async def _process_with_llm(self, request: ChatRequest) -> AgentResponse:
        """Process message using OpenRouter LLM."""
        try:
            # Build context
            context = None
            if request.selected_trace_id:
                context = f"Currently selected trace: {request.selected_trace_id}"

            # Send to LLM
            response = await self.openrouter.chat_with_tools(
                user_message=request.message,
                context=context
            )

            # Process response
            choices = response.get("choices", [])
            if not choices:
                return AgentResponse(answer="No response from LLM.")

            message = choices[0].get("message", {})

            # Check for tool calls
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                return await self._handle_tool_calls(tool_calls, request)

            # Return text response
            content = message.get("content", "")
            return AgentResponse(
                answer=content,
                evidence=Evidence(traceId=request.selected_trace_id),
                ui=UIHints()
            )

        except Exception as e:
            logger.error(f"LLM processing error: {e}")
            # Fall back to rule-based on error
            return await self._process_with_fallback(request)

    async def _handle_tool_calls(
        self,
        tool_calls: list[dict],
        request: ChatRequest
    ) -> AgentResponse:
        """Execute tool calls and return response."""
        results = []
        highlight_nodes = []
        actions = []

        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            name = function.get("name", "")
            args_str = function.get("arguments", "{}")

            try:
                args = json.loads(args_str)
            except json.JSONDecodeError:
                args = {}

            # Execute the tool
            result = await self.tool_executor.execute(name, args)
            results.append({"tool": name, "result": result})

            # Check for action requests
            if result.get("action_required"):
                actions.append(result["action"])

            # Extract highlight hints from analysis results
            if name == "get_trace_analysis" and not result.get("error"):
                if result.get("criticalPath"):
                    highlight_nodes.extend(result["criticalPath"])
                if result.get("slowestSpans"):
                    highlight_nodes.extend([
                        f"span:{s['spanId']}"
                        for s in result["slowestSpans"]
                    ])

        # Build response
        answer = self._summarize_tool_results(results)

        return AgentResponse(
            answer=answer,
            evidence=Evidence(traceId=request.selected_trace_id),
            ui=UIHints(highlightNodes=highlight_nodes),
            actions=actions
        )

    def _summarize_tool_results(self, results: list[dict]) -> str:
        """Summarize tool execution results into a readable response."""
        summaries = []

        for result in results:
            tool = result["tool"]
            data = result["result"]

            if data.get("error"):
                summaries.append(f"Error: {data['error']}")
                continue

            if tool == "list_traces":
                count = len(data) if isinstance(data, list) else 0
                summaries.append(f"Found {count} recent traces.")
                if isinstance(data, list) and data:
                    summaries.append("Recent traces:")
                    for trace in data[:5]:
                        summaries.append(
                            f"- {trace.get('operationName', 'unknown')} "
                            f"({trace.get('durationMs', 0):.1f}ms)"
                        )

            elif tool == "get_trace_analysis":
                summaries.append("**Trace Analysis:**")
                if data.get("slowestSpans"):
                    summaries.append("\nSlowest operations:")
                    for span in data["slowestSpans"][:3]:
                        summaries.append(
                            f"- {span.get('operationName', 'unknown')}: "
                            f"{span.get('durationMs', 0):.1f}ms"
                        )
                if data.get("errorSpans"):
                    summaries.append(f"\nFound {len(data['errorSpans'])} error(s)")
                if data.get("criticalPath"):
                    summaries.append(
                        f"\nCritical path: {len(data['criticalPath'])} spans"
                    )

            elif tool == "get_runtime_flow":
                node_count = len(data.get("nodes", []))
                summaries.append(f"Graph loaded with {node_count} spans.")

            elif data.get("action_required"):
                summaries.append(
                    f"Action requested: {data['action'].get('description', 'unknown')}"
                )

        return "\n".join(summaries) if summaries else "Analysis complete."

    async def _process_with_fallback(self, request: ChatRequest) -> AgentResponse:
        """Process message using rule-based fallback logic."""
        query_analysis = analyze_query(request.message)
        intent = query_analysis["intent"]

        # Handle intents that don't need a trace
        if intent == "record":
            path = query_analysis["parameters"].get("path", "/demo/slow")
            return generate_record_action(path)

        if intent == "list":
            # Fetch traces
            result = await self.tool_executor.execute("list_traces", {"limit": 10})
            if result.get("error"):
                return AgentResponse(
                    answer=f"Error fetching traces: {result['error']}",
                    evidence=Evidence(),
                    ui=UIHints()
                )

            traces = result if isinstance(result, list) else []
            if not traces:
                return AgentResponse(
                    answer="No traces found. Try recording a new trace using the demo endpoints.",
                    evidence=Evidence(),
                    ui=UIHints()
                )

            answer = f"**Recent Traces ({len(traces)} found):**\n\n"
            for trace in traces[:10]:
                has_error = "ERROR" if trace.get("hasError") else "OK"
                answer += (
                    f"- `{trace.get('traceId', 'unknown')[:16]}...` | "
                    f"{trace.get('operationName', 'unknown')} | "
                    f"{trace.get('durationMs', 0):.1f}ms | {has_error}\n"
                )

            return AgentResponse(
                answer=answer,
                evidence=Evidence(),
                ui=UIHints()
            )

        # Intents that need a trace
        if not request.selected_trace_id:
            return no_trace_response()

        # Fetch the trace data
        trace_data = await self.tool_executor.execute(
            "get_trace",
            {"trace_id": request.selected_trace_id}
        )

        if trace_data.get("error"):
            return AgentResponse(
                answer=f"Error fetching trace: {trace_data['error']}",
                evidence=Evidence(traceId=request.selected_trace_id),
                ui=UIHints()
            )

        # Process based on intent
        if intent == "slow":
            return analyze_trace_for_slowness(trace_data)
        elif intent == "error":
            return analyze_trace_for_errors(trace_data)
        elif intent == "explain":
            return explain_trace(trace_data)
        else:
            return unknown_intent_response()


# Global planner instance
_planner: Optional[AgentPlanner] = None


def get_agent_planner() -> AgentPlanner:
    """Get the global agent planner instance."""
    global _planner
    if _planner is None:
        _planner = AgentPlanner()
    return _planner
