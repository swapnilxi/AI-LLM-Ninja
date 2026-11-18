import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { streamRun } from "@/lib/sse";
import type { RunEvent, RunStatus } from "@/lib/types";

export interface RunStreamState {
  events: RunEvent[]; // persisted trace events
  live: Record<string, string>; // agent -> streaming text of the current LLM call
  status: RunStatus | null;
  output: string;
  error: string;
  done: boolean;
  activeNodes: Set<string>;
  nodeStatus: Record<string, "running" | "done" | "failed" | "skipped">;
}

const initial = (): RunStreamState => ({ events: [], live: {}, status: null, output: "", error: "", done: false, activeNodes: new Set(), nodeStatus: {} });

/** Subscribe to a run's live event stream. */
export function useRunStream(runId: string | null | undefined): RunStreamState {
  const [state, setState] = useState<RunStreamState>(initial);
  const qc = useQueryClient();
  const pending = useRef<Record<string, string>>({});
  const frame = useRef<number | null>(null);

  useEffect(() => {
    setState(initial());
    if (!runId) return;
    const flush = () => {
      frame.current = null;
      const add = pending.current;
      pending.current = {};
      setState((s) => {
        const live = { ...s.live };
        for (const [k, v] of Object.entries(add)) live[k] = (live[k] ?? "") + v;
        return { ...s, live };
      });
    };
    const stop = streamRun(
      runId,
      (ev) => {
        if (ev.type === "token") {
          const key = ev.agent || "agent";
          pending.current[key] = (pending.current[key] ?? "") + (ev.data.text ?? "");
          if (frame.current === null) frame.current = requestAnimationFrame(flush);
          return;
        }
        if (ev.type === "thinking_token") return;
        setState((s) => {
          const next: RunStreamState = { ...s, events: [...s.events, ev] };
          if (ev.type === "run_start") next.status = "running";
          if (ev.type === "llm_response" || ev.type === "agent_end") {
            const live = { ...s.live };
            delete live[ev.agent || "agent"];
            next.live = live;
          }
          if (ev.type === "node_start" && ev.node_id) {
            next.nodeStatus = { ...s.nodeStatus, [ev.node_id]: "running" };
          }
          if (ev.type === "node_end" && ev.node_id) {
            next.nodeStatus = { ...s.nodeStatus, [ev.node_id]: ev.data.status === "failed" ? "failed" : "done" };
          }
          if (ev.type === "node_skipped" && ev.node_id) {
            next.nodeStatus = { ...s.nodeStatus, [ev.node_id]: "skipped" };
          }
          if (ev.type === "run_end") {
            next.status = ev.data.status;
            next.output = ev.data.output ?? "";
            next.error = ev.data.error ?? "";
            next.done = true;
            next.live = {};
          }
          return next;
        });
      },
      {
        onDone: () => {
          qc.invalidateQueries({ queryKey: ["runs"] });
          qc.invalidateQueries({ queryKey: ["run", runId] });
          qc.invalidateQueries({ queryKey: ["dashboard"] });
        },
      },
    );
    return () => {
      stop();
      if (frame.current) cancelAnimationFrame(frame.current);
    };
  }, [runId, qc]);

  return state;
}
