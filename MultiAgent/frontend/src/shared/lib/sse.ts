import { authHeaders, apiBase } from "./api";
import type { RunEvent } from "./types";

/**
 * Streams run events over SSE using fetch (so we can send the Authorization header).
 * Replays persisted events, then live events (including ephemeral token deltas).
 * Reconnects with the last seen sequence number.
 */
export function streamRun(runId: string, onEvent: (ev: RunEvent) => void, opts: { onDone?: () => void } = {}): () => void {
  const ctrl = new AbortController();
  let lastSeq = 0;
  let done = false;
  let attempts = 0;

  const connect = async () => {
    while (!done && !ctrl.signal.aborted && attempts < 6) {
      try {
        const res = await fetch(`${apiBase}/api/runs/${runId}/stream?after=${lastSeq}`, { headers: authHeaders(), signal: ctrl.signal });
        if (!res.ok || !res.body) throw new Error(`stream ${res.status}`);
        attempts = 0;
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        for (;;) {
          const { value, done: rdDone } = await reader.read();
          if (rdDone) break;
          buf += decoder.decode(value, { stream: true });
          let idx: number;
          while ((idx = buf.indexOf("\n\n")) >= 0) {
            const chunk = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            const line = chunk.split("\n").find((l) => l.startsWith("data: "));
            if (!line) continue;
            try {
              const ev = JSON.parse(line.slice(6)) as RunEvent;
              if (ev.seq) lastSeq = Math.max(lastSeq, ev.seq);
              onEvent(ev);
              if (ev.type === "run_end") {
                done = true;
                opts.onDone?.();
                ctrl.abort();
                return;
              }
            } catch {
              /* ignore malformed */
            }
          }
        }
      } catch (e) {
        if (ctrl.signal.aborted) return;
      }
      attempts += 1;
      await new Promise((r) => setTimeout(r, Math.min(1000 * attempts, 5000)));
    }
  };
  connect();
  return () => {
    done = true;
    ctrl.abort();
  };
}
