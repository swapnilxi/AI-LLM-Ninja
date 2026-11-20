/** Data hooks for this module (react-query). Query keys: [resource, ...params]. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { http, qs } from "@/shared/lib/api";
import { useAuth } from "@/shared/lib/auth";
import { errMsg } from "@/shared/lib/utils";
import type { Run } from "./types";

export const useRuns = (params: Record<string, string | number | undefined> = {}, opts: { refetchInterval?: number } = {}) =>
  useQuery({ queryKey: ["runs", params], queryFn: () => http.get<{ total: number; items: Run[] }>(`/runs${qs(params)}`), refetchInterval: opts.refetchInterval });

/** Start a run in the current project. */
export function useStartRun() {
  const { projectId } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { target_type: string; target_id: string; input: Record<string, any> }) => http.post<Run>("/runs", { project_id: projectId, ...v }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
    onError: (e) => toast.error(errMsg(e)),
  });
}
