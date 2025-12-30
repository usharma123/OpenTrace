"""OpenRouter API client for LLM interactions."""

import httpx
from typing import Optional
import logging

from .config import get_settings

logger = logging.getLogger(__name__)


# Tool definitions for function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_traces",
            "description": "List recent traces from Jaeger. Use this to see what traces are available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Filter by service name (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of traces to return",
                        "default": 10
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trace",
            "description": "Get full trace data including all spans for detailed analysis.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trace_id": {
                        "type": "string",
                        "description": "The trace ID to fetch"
                    }
                },
                "required": ["trace_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trace_analysis",
            "description": "Get automated analysis of a trace including critical path, slowest spans, and errors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trace_id": {
                        "type": "string",
                        "description": "The trace ID to analyze"
                    }
                },
                "required": ["trace_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_runtime_flow",
            "description": "Get ReactFlow graph visualization data for a trace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trace_id": {
                        "type": "string",
                        "description": "The trace ID to visualize"
                    }
                },
                "required": ["trace_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "record_request",
            "description": "Record a new trace by making a request to the API. This requires user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST"],
                        "description": "HTTP method"
                    },
                    "path": {
                        "type": "string",
                        "description": "API path to request (e.g., /demo/slow)"
                    },
                    "body": {
                        "type": "object",
                        "description": "Request body for POST requests"
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]


SYSTEM_PROMPT = """You are an expert observability analyst helping users understand their application traces.

Your capabilities:
1. List and search traces from Jaeger
2. Analyze traces to find bottlenecks and errors
3. Highlight specific spans in the visualization
4. Record new traces (requires user approval)

When analyzing traces:
- Look for the critical path (longest duration path through the trace)
- Identify slow spans (operations taking longer than expected)
- Find error spans (HTTP 5xx, error tags, failed operations)
- Explain the flow in plain language

When responding:
- Be concise but informative
- Use span IDs to highlight relevant parts of the trace
- Suggest next steps for investigation
- If asked to record a new trace, explain that it requires approval

Always use the available tools to get accurate data before making statements about traces."""


class OpenRouterClient:
    """Client for OpenRouter API (unified LLM gateway)."""

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.openrouter_api_key
        self.model = self.settings.openrouter_model
        self.base_url = self.settings.openrouter_base_url

    def is_available(self) -> bool:
        """Check if OpenRouter is configured."""
        return bool(self.api_key)

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None
    ) -> dict:
        """
        Send a chat request to OpenRouter.

        Args:
            messages: List of message objects with role and content
            tools: Optional list of tool definitions

        Returns:
            Response from the API
        """
        if not self.is_available():
            raise ValueError("OpenRouter API key not configured")

        payload = {
            "model": self.model,
            "messages": messages,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://opentrace.local",
                    "X-Title": "OpenTrace",
                },
                json=payload,
            )

            if response.status_code != 200:
                logger.error(f"OpenRouter error: {response.status_code} - {response.text}")
                raise Exception(f"OpenRouter API error: {response.status_code}")

            return response.json()

    async def chat_with_tools(
        self,
        user_message: str,
        context: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None
    ) -> dict:
        """
        Send a chat request with tool support.

        Args:
            user_message: The user's message
            context: Optional additional context
            conversation_history: Optional previous messages

        Returns:
            API response including any tool calls
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if conversation_history:
            messages.extend(conversation_history)

        if context:
            user_message = f"{user_message}\n\nContext: {context}"

        messages.append({"role": "user", "content": user_message})

        return await self.chat(messages, tools=TOOLS)


# Global client instance
_client: Optional[OpenRouterClient] = None


def get_openrouter_client() -> OpenRouterClient:
    """Get the global OpenRouter client instance."""
    global _client
    if _client is None:
        _client = OpenRouterClient()
    return _client
