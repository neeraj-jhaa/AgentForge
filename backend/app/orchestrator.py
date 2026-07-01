"""
Orchestrator: the supervisor graph tying every specialist agent together.

Flow:
    1. Planner decomposes the user's goal into steps.
    2. Each step is routed to Researcher or Coder based on a keyword
       heuristic (swap for a routing model call for a fancier version).
    3. Critic reviews the accumulated work; if not APPROVED, one
       revision round is triggered on the flagged agent.
    4. Synthesizer merges everything into the final answer.
    5. The whole run (and its key findings) is written to semantic
       memory so future tasks can recall it via RAG.

Every step yields AgentEvents so the API layer can stream live
progress to the frontend over a WebSocket.
"""
from __future__ import annotations
from typing import AsyncIterator

from .agents.base import AgentEvent
from .agents.specialists import (
    PlannerAgent, ResearcherAgent, CoderAgent, CriticAgent, SynthesizerAgent,
)
from .memory.vector_store import memory
from . import database
from .config import settings

CODE_KEYWORDS = ("code", "script", "calculate", "compute", "algorithm", "function", "python", "parse", "regex")


def _route_step(step: str) -> str:
    lowered = step.lower()
    return "coder" if any(k in lowered for k in CODE_KEYWORDS) else "researcher"


async def run_task(task_id: str, goal: str) -> AsyncIterator[AgentEvent]:
    recalled = memory.search(goal)
    memory_block = ""
    if recalled:
        memory_block = "Relevant memory from previous tasks:\n- " + "\n- ".join(recalled)
        yield AgentEvent("memory", "tool_result", memory_block)

    # ---- 1. PLAN --------------------------------------------------------
    planner = PlannerAgent()
    plan_text = ""
    prompt = f"Goal: {goal}\n\n{memory_block}"
    async for ev in planner.run(prompt):
        database.log_event(task_id, ev.agent, ev.kind, ev.content)
        yield ev
        if ev.kind == "output":
            plan_text = ev.content

    steps = [s.strip("-*0123456789. ").strip() for s in plan_text.splitlines() if s.strip()]
    steps = steps[: settings.MAX_PLAN_STEPS] or [goal]

    # ---- 2. EXECUTE STEPS -------------------------------------------------
    work_log = []
    for step in steps:
        role = _route_step(step)
        agent = CoderAgent() if role == "coder" else ResearcherAgent()
        step_prompt = f"Overall goal: {goal}\nYour step: {step}\n{memory_block}"
        step_output = ""
        async for ev in agent.run(step_prompt):
            database.log_event(task_id, ev.agent, ev.kind, ev.content)
            yield ev
            if ev.kind == "output":
                step_output = ev.content
        work_log.append(f"Step: {step}\nResult ({role}):\n{step_output}")

    combined_work = "\n\n".join(work_log)

    # ---- 3. CRITIQUE + one revision round --------------------------------
    critic = CriticAgent()
    critique_prompt = f"Goal: {goal}\n\nWork produced so far:\n{combined_work}"
    critique_text = ""
    async for ev in critic.run(critique_prompt):
        database.log_event(task_id, ev.agent, ev.kind, ev.content)
        yield ev
        if ev.kind == "output":
            critique_text = ev.content

    if critique_text.strip().upper() != "APPROVED":
        reviser = ResearcherAgent()
        revise_prompt = (
            f"Goal: {goal}\nOriginal work:\n{combined_work}\n\n"
            f"Critic feedback to address:\n{critique_text}\n\n"
            "Produce a corrected, improved version of the work."
        )
        revised_output = ""
        async for ev in reviser.run(revise_prompt):
            database.log_event(task_id, ev.agent, ev.kind, ev.content)
            yield ev
            if ev.kind == "output":
                revised_output = ev.content
        combined_work += f"\n\nRevision after critic feedback:\n{revised_output}"

    # ---- 4. SYNTHESIZE FINAL ANSWER --------------------------------------
    synth = SynthesizerAgent()
    synth_prompt = f"Goal: {goal}\n\nPlan:\n{plan_text}\n\nWork:\n{combined_work}"
    final_answer = ""
    async for ev in synth.run(synth_prompt):
        database.log_event(task_id, ev.agent, ev.kind, ev.content)
        yield ev
        if ev.kind == "output":
            final_answer = ev.content

    # ---- 5. PERSIST + MEMORY -----------------------------------------------
    database.update_task_status(task_id, "completed", final_answer)
    memory.add(task_id, f"Goal: {goal}\nOutcome: {final_answer[:500]}")

    yield AgentEvent("supervisor", "done", final_answer)
