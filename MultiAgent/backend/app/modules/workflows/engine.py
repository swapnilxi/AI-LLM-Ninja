"""DAG workflow engine.

Graph format (React Flow compatible):
  {"nodes": [{"id", "type", "position", "data": {...config}}],
   "edges": [{"id", "source", "target", "sourceHandle": null | "true" | "false"}]}

Node types: input, agent, team, tool, llm, condition, template, output.
Templates (sandboxed Jinja) can reference {{ input.x }}, {{ nodes.<id>.output }},
{{ last }} (output of upstream node), {{ vars.x }}, {{ project.name }}.
Independent branches run concurrently.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from typing import Any

from ..db import SessionLocal
from ..models import Agent, Team, Tool, Workflow
from .context import RunContext
from .llm.base import LLMError, ModelSettings
from .llm.registry import get_provider, resolve_model
from .templating import evaluate, render
from .tools.builtin import BUILTINS
from .tools.registry import runtime_for

NODE_TYPES = {"input", "agent", "team", "tool", "llm", "condition", "template", "output"}
MAX_NODES = 60


class WorkflowError(Exception):
    pass


def validate_graph(graph: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    if not nodes:
        return ["Workflow has no nodes"]
    if len(nodes) > MAX_NODES:
        errors.append(f"Too many nodes (max {MAX_NODES})")
    ids = [n.get("id") for n in nodes]
    if len(ids) != len(set(ids)):
        errors.append("Duplicate node ids")
    idset = set(ids)
    for n in nodes:
        t, d = n.get("type"), n.get("data") or {}
        label = d.get("label") or n.get("id")
        if t not in NODE_TYPES:
            errors.append(f"Node '{label}' has unknown type '{t}'")
        if t == "agent" and not d.get("agent_id"):
            errors.append(f"Agent node '{label}' has no agent selected")
        if t == "team" and not d.get("team_id"):
            errors.append(f"Team node '{label}' has no team selected")
        if t == "tool" and not (d.get("tool_id") or d.get("tool_key")):
            errors.append(f"Tool node '{label}' has no tool selected")
    for e in edges:
        if e.get("source") not in idset or e.get("target") not in idset:
            errors.append(f"Edge {e.get('id')} references a missing node")
    # cycle detection (Kahn)
    indeg = {i: 0 for i in idset}
    out = defaultdict(list)
    for e in edges:
        if e.get("source") in idset and e.get("target") in idset:
            indeg[e["target"]] += 1
            out[e["source"]].append(e["target"])
    queue = [i for i, d in indeg.items() if d == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for t in out[n]:
            indeg[t] -= 1
            if indeg[t] == 0:
                queue.append(t)
    if seen != len(idset):
        errors.append("Workflow contains a cycle - workflows must be acyclic")
    return errors


async def run_workflow(ctx: RunContext, wf: Workflow, run_input: dict[str, Any]) -> str:
    graph = wf.graph or {}
    errs = validate_graph(graph)
    if errs:
        raise WorkflowError("; ".join(errs))
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = graph.get("edges") or []
    incoming: dict[str, list[dict]] = defaultdict(list)
    outgoing: dict[str, list[dict]] = defaultdict(list)
    for e in edges:
        incoming[e["target"]].append(e)
        outgoing[e["source"]].append(e)

    status: dict[str, str] = {nid: "pending" for nid in nodes}
    outputs: dict[str, str] = {}
    edge_active: dict[str, bool | None] = {e["id"]: None for e in edges}
    order: list[str] = []

    def tctx(nid: str) -> dict[str, Any]:
        ups = [outputs[e["source"]] for e in incoming[nid] if edge_active.get(e["id"]) and e["source"] in outputs]
        node_data = {}
        for k, v in outputs.items():
            entry: dict[str, Any] = {"output": v, "status": status[k]}
            try:
                entry["json"] = json.loads(v)
            except Exception:
                entry["json"] = None
            node_data[k] = entry
        return {
            "input": run_input,
            "nodes": node_data,
            "last": "\n\n".join(ups) if ups else json.dumps(run_input, ensure_ascii=False) if run_input else "",
            "project": {"id": ctx.project.id, "name": ctx.project.name, "description": ctx.project.description},
            "vars": ctx.project.variables,
            "org": {"id": ctx.org.id, "name": ctx.org.name},
        }

    async def execute(nid: str) -> None:
        node = nodes[nid]
        t, d = node["type"], node.get("data") or {}
        label = d.get("label") or nid
        status[nid] = "running"
        started = time.perf_counter()
        await ctx.emit("node_start", {"type": t, "label": label}, node_id=nid)
        try:
            out, branch = await _run_node(ctx, t, {**d, "_id": nid}, tctx(nid), run_input)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            status[nid] = "failed"
            await ctx.emit("node_end", {"status": "failed", "error": str(exc)[:2000], "label": label}, node_id=nid)
            if d.get("continue_on_error"):
                out, branch = f"[error] {exc}", None
                status[nid] = "done"
            else:
                raise WorkflowError(f"Node '{label}' failed: {exc}") from exc
        else:
            status[nid] = "done"
            await ctx.emit(
                "node_end",
                {"status": "done", "label": label, "output": out[:4000], "branch": branch, "duration_ms": int((time.perf_counter() - started) * 1000)},
                node_id=nid,
            )
        outputs[nid] = out
        order.append(nid)
        for e in outgoing[nid]:
            if t == "condition":
                handle = e.get("sourceHandle") or "true"
                edge_active[e["id"]] = handle == branch
            else:
                edge_active[e["id"]] = True

    while any(s == "pending" for s in status.values()):
        ctx.check()
        ready, skipped = [], []
        for nid, s in status.items():
            if s != "pending":
                continue
            ins = incoming[nid]
            if not ins:
                ready.append(nid)
            elif all(edge_active[e["id"]] is not None for e in ins):
                (ready if any(edge_active[e["id"]] for e in ins) else skipped).append(nid)
        for nid in skipped:
            status[nid] = "skipped"
            for e in outgoing[nid]:
                edge_active[e["id"]] = False
            await ctx.emit("node_skipped", {"label": (nodes[nid].get("data") or {}).get("label") or nid}, node_id=nid)
        if not ready and not skipped:
            raise WorkflowError("Workflow is stuck (unreachable nodes)")
        if ready:
            await asyncio.gather(*[execute(n) for n in ready])

    out_nodes = [n for n in order if nodes[n]["type"] == "output"]
    if out_nodes:
        return "\n\n".join(outputs[n] for n in out_nodes)
    return outputs[order[-1]] if order else ""


async def _run_node(ctx: RunContext, t: str, d: dict[str, Any], tc: dict[str, Any], run_input: dict[str, Any]) -> tuple[str, str | None]:
    if t == "input":
        return json.dumps(run_input, ensure_ascii=False, indent=2), None
    if t in ("template", "output"):
        return render(d.get("template") or "{{ last }}", tc), None
    if t == "condition":
        result = evaluate(d.get("expression") or "true", tc)
        return ("true" if result else "false"), ("true" if result else "false")
    if t == "agent":
        from .runner import run_agent

        async with SessionLocal() as s:
            agent = await s.get(Agent, d.get("agent_id", ""))
        if not agent or (agent.org_id and agent.org_id != ctx.org.id):
            raise WorkflowError("Agent not found")
        prompt = render(d.get("prompt") or "{{ last }}", tc)
        res = await run_agent(ctx.child(agent.id), agent, prompt, label=d.get("label") or agent.name, node_id=d.get("_id", ""))
        return res.text, None
    if t == "team":
        from .orchestrator import run_team

        async with SessionLocal() as s:
            team = await s.get(Team, d.get("team_id", ""))
        if not team or (team.org_id and team.org_id != ctx.org.id):
            raise WorkflowError("Team not found")
        return await run_team(ctx.child(), team, render(d.get("prompt") or "{{ last }}", tc)), None
    if t == "tool":
        rt = None
        if d.get("tool_key") in BUILTINS:
            rt = BUILTINS[d["tool_key"]].runtime()
        elif d.get("tool_id"):
            async with SessionLocal() as s:
                row = await s.get(Tool, d["tool_id"])
            if row and (row.org_id is None or row.org_id == ctx.org.id):
                rt = runtime_for(row)
        if rt is None:
            raise WorkflowError("Tool not found")
        if rt.category == "web" and not ctx.web_access:
            raise WorkflowError("Web access is disabled for this project")
        raw = render(d.get("args") or "{}", tc)
        try:
            args = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"Tool args are not valid JSON after templating: {exc}") from exc
        await ctx.emit("tool_call", {"name": rt.name, "arguments": args})
        res = await rt.handler(args, ctx)
        ctx.usage["tool_calls"] += 1
        await ctx.emit("tool_result", {"name": rt.name, "is_error": res.is_error, "output": res.content[:3000]})
        if res.is_error and not d.get("continue_on_error"):
            raise WorkflowError(res.content[:500])
        return res.content, None
    if t == "llm":
        async with SessionLocal() as s:
            pk, model = await resolve_model(s, ctx.org, d.get("provider") or "default", d.get("model"))
            provider = await get_provider(s, ctx.org, pk)
        resp = await provider.complete(
            system=render(d.get("system") or "You are a helpful assistant.", tc),
            messages=[{"role": "user", "content": render(d.get("prompt") or "{{ last }}", tc)}],
            tools=[],
            settings=ModelSettings(model=model, max_tokens=int(d.get("max_tokens") or 4000), effort=d.get("effort") or "low"),
        )
        ctx.add_usage(resp.usage.input_tokens, resp.usage.output_tokens)
        await ctx.emit("llm_response", {"text": resp.text[:4000], "model": model, "usage": {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}})
        return resp.text, None
    raise LLMError(f"Unknown node type {t}")
