"""
BaseAgent: a thin, reusable wrapper around an OpenAI-compatible chat
completions API (used here with Groq's free-tier endpoint) that
implements the tool-use loop (call model -> run requested tools ->
feed results back -> repeat until the model returns plain text).

Every specialist agent (Planner, Researcher, Coder, Critic) subclasses
this with its own system prompt and tool allowlist. Centralizing the
loop here means each agent file only needs to describe its behaviour,
not re-implement API plumbing.

Provider note: Groq exposes an OpenAI-compatible /chat/completions API,
so we use the official `openai` SDK pointed at Groq's base_url. This
also means swapping to real OpenAI, Together, Fireworks, or any other
OpenAI-compatible provider later is a one-line env var change.
"""
from __future__ import annotations
import json
from typing import Callable, AsyncIterator
from openai import OpenAI

from ..config import settings
from ..tools import web_search, code_executor, calculator

TOOL_REGISTRY: dict[str, Callable] = {
    "web_search": lambda **kw: web_search.run(**kw),
    "execute_python": lambda **kw: code_executor.run(**kw),
    "calculator": lambda **kw: calculator.run(**kw),
}

# OpenAI-style function-calling schemas: {"type": "function", "function": {...}}
TOOL_SCHEMAS = {
    "web_search": web_search.TOOL_SCHEMA,
    "execute_python": code_executor.TOOL_SCHEMA,
    "calculator": calculator.TOOL_SCHEMA,
}


class AgentEvent:
    """A structured event streamed to the frontend over the WebSocket."""

    def __init__(self, agent: str, kind: str, content: str):
        self.agent = agent
        self.kind = kind  # "thought" | "tool_call" | "tool_result" | "output" | "error"
        self.content = content

    def to_dict(self):
        return {"agent": self.agent, "kind": self.kind, "content": self.content}


class BaseAgent:
    name: str = "agent"
    system_prompt: str = "You are a helpful agent."
    allowed_tools: list[str] = []
    max_tool_rounds: int = 4

    def __init__(self):
        if not settings.GROQ_API_KEY:
            self.client = None
        else:
            self.client = OpenAI(api_key=settings.GROQ_API_KEY, base_url=settings.BASE_URL)

    def _tool_schemas(self):
        return [TOOL_SCHEMAS[t] for t in self.allowed_tools]

    async def run(self, user_content: str) -> AsyncIterator[AgentEvent]:
        """
        Runs the tool-use loop for this agent and yields AgentEvents as it
        goes (thoughts, tool calls, tool results, and the final output).
        """
        if self.client is None:
            yield AgentEvent(self.name, "error", "GROQ_API_KEY is not set on the server.")
            return

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]

        for _round in range(self.max_tool_rounds):
            try:
                response = self.client.chat.completions.create(
                    model=settings.MODEL_NAME,
                    max_tokens=settings.MAX_TOKENS,
                    messages=messages,
                    tools=self._tool_schemas() if self.allowed_tools else None,
                )
            except Exception as e:
                yield AgentEvent(self.name, "error", f"API error: {e}")
                return

            choice = response.choices[0]
            msg = choice.message
            tool_calls = msg.tool_calls or []

            if msg.content:
                yield AgentEvent(self.name, "thought" if tool_calls else "output", msg.content)

            if not tool_calls:
                return  # done - last text content was the final answer

            # Assistant turn requesting tools must be echoed back verbatim
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in tool_calls
                    ],
                }
            )

            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield AgentEvent(self.name, "tool_call", json.dumps({"tool": tc.function.name, "input": args}))
                fn = TOOL_REGISTRY.get(tc.function.name)
                try:
                    result = fn(**args) if fn else {"error": f"unknown tool {tc.function.name}"}
                except Exception as e:
                    result = {"error": str(e)}
                result_str = json.dumps(result)[:3000]
                yield AgentEvent(self.name, "tool_result", result_str)
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result_str}
                )

        yield AgentEvent(self.name, "output", "(stopped after max tool rounds)")
