/** Shared react-query hooks. Query keys: [resource, ...params]. Org switching clears the cache. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { http, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Agent, Automation, Catalog, Connection, Connector, Doc, HubCatalog, Lesson, Memory, ProviderInfo, Run, Skill, SkillCommand, SkillTemplate, Task, Team, Tool, TrainingOverview, Workflow } from "@/lib/types";
import { errMsg } from "@/lib/utils";

export const useAgents = () => useQuery({ queryKey: ["agents"], queryFn: () => http.get<Agent[]>("/agents") });
export const useAgent = (id?: string) => useQuery({ queryKey: ["agents", id], queryFn: () => http.get<Agent>(`/agents/${id}`), enabled: !!id && id !== "new" });
export const useSkills = () => useQuery({ queryKey: ["skills"], queryFn: () => http.get<Skill[]>("/skills") });
export const useSkill = (id?: string) => useQuery({ queryKey: ["skills", id], queryFn: () => http.get<Skill>(`/skills/${id}`), enabled: !!id && id !== "new" });
export const useSkillCommands = () => useQuery({ queryKey: ["skills", "commands"], queryFn: () => http.get<SkillCommand[]>("/skills/commands"), staleTime: 60_000 });
export const useSkillTemplates = () => useQuery({ queryKey: ["skill-templates"], queryFn: () => http.get<SkillTemplate[]>("/skills/templates"), staleTime: 600_000 });
export const useTools = () => useQuery({ queryKey: ["tools"], queryFn: () => http.get<Tool[]>("/tools") });
export const useTool = (id?: string) => useQuery({ queryKey: ["tools", id], queryFn: () => http.get<Tool>(`/tools/${id}`), enabled: !!id && id !== "new" });
export const useTeams = () => useQuery({ queryKey: ["teams"], queryFn: () => http.get<Team[]>("/teams") });
export const useTeam = (id?: string) => useQuery({ queryKey: ["teams", id], queryFn: () => http.get<Team>(`/teams/${id}`), enabled: !!id && id !== "new" });
export const useWorkflows = () => useQuery({ queryKey: ["workflows"], queryFn: () => http.get<Workflow[]>("/workflows") });
export const useWorkflow = (id?: string) => useQuery({ queryKey: ["workflows", id], queryFn: () => http.get<Workflow>(`/workflows/${id}`), enabled: !!id && id !== "new" });
export const useConnections = () => useQuery({ queryKey: ["connections"], queryFn: () => http.get<Connection[]>("/connections") });
export const useConnectorCatalog = () => useQuery({ queryKey: ["connector-catalog"], queryFn: () => http.get<Connector[]>("/connectors/catalog"), staleTime: 600_000 });
export const useCatalog = () => useQuery({ queryKey: ["catalog"], queryFn: () => http.get<Catalog>("/catalog"), staleTime: 600_000 });
export const useProviders = () =>
  useQuery({ queryKey: ["providers"], queryFn: () => http.get<{ providers: ProviderInfo[]; default: { provider: string; model: string } }>("/org/providers") });

export const useDocuments = (ownerType: string, ownerId?: string) =>
  useQuery({ queryKey: ["documents", ownerType, ownerId], queryFn: () => http.get<Doc[]>(`/documents${qs({ owner_type: ownerType, owner_id: ownerId })}`), enabled: !!ownerId });

export const useMemories = (params: { scope?: string; agent_id?: string; project_id?: string }) =>
  useQuery({ queryKey: ["memories", params], queryFn: () => http.get<Memory[]>(`/memories${qs(params)}`), enabled: !!(params.agent_id || params.project_id) });

export const useTraining = (agentId?: string) =>
  useQuery({ queryKey: ["training", agentId], queryFn: () => http.get<TrainingOverview>(`/agents/${agentId}/training`), enabled: !!agentId });
export const useLessons = (agentId?: string, status = "pending") =>
  useQuery({ queryKey: ["lessons", agentId, status], queryFn: () => http.get<Lesson[]>(`/agents/${agentId}/lessons?status=${status}`), enabled: !!agentId, refetchInterval: 15000 });

export const useRuns = (params: Record<string, string | number | undefined> = {}, opts: { refetchInterval?: number } = {}) =>
  useQuery({ queryKey: ["runs", params], queryFn: () => http.get<{ total: number; items: Run[] }>(`/runs${qs(params)}`), refetchInterval: opts.refetchInterval });

export const useAutomations = (projectId?: string | null) =>
  useQuery({ queryKey: ["automations", projectId], queryFn: () => http.get<Automation[]>(`/automations${qs({ project_id: projectId ?? undefined })}`) });

export const useTasks = (projectId?: string | null) =>
  useQuery({ queryKey: ["tasks", projectId], queryFn: () => http.get<Task[]>(`/tasks${qs({ project_id: projectId ?? undefined })}`), enabled: !!projectId });

/** Discover catalog (skill packs, MCP servers, knowledge docs) with install state for the given project. */
export const useHub = (projectId?: string | null) =>
  useQuery({ queryKey: ["hub", projectId], queryFn: () => http.get<HubCatalog>(`/hub${qs({ project_id: projectId ?? undefined })}`), enabled: !!projectId });

/** Generic mutation with toast + invalidation. */
export function useAction<TVars = void, TRes = any>(fn: (v: TVars) => Promise<TRes>, opts: { success?: string; invalidate?: unknown[][]; onSuccess?: (r: TRes, v: TVars) => void } = {}) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (res, vars) => {
      if (opts.success) toast.success(opts.success);
      opts.invalidate?.forEach((k) => qc.invalidateQueries({ queryKey: k }));
      opts.onSuccess?.(res, vars);
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

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
