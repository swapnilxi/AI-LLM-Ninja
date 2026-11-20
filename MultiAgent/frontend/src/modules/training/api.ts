/** Data hooks for this module (react-query). Query keys: [resource, ...params]. */
import { useQuery } from "@tanstack/react-query";
import { http, qs } from "@/shared/lib/api";
import type { AgentTrainingStats, Lesson, SearchHit, TrainingOverview } from "./types";

export const useTraining = (agentId?: string) =>
  useQuery({ queryKey: ["training", agentId], queryFn: () => http.get<TrainingOverview>(`/agents/${agentId}/training`), enabled: !!agentId });

export const useLessons = (agentId?: string, status = "pending") =>
  useQuery({ queryKey: ["lessons", agentId, status], queryFn: () => http.get<Lesson[]>(`/agents/${agentId}/lessons?status=${status}`), enabled: !!agentId, refetchInterval: 15000 });

/** Stats for every visible agent in one request (Training picker). */
export const useTrainingGrid = () =>
  useQuery({ queryKey: ["training", "grid"], queryFn: () => http.get<Record<string, AgentTrainingStats>>("/training/agents") });

export const useKnowledgeSearch = (params: { q: string; agent_id: string; project_id?: string | null; agent_only?: boolean; top_k?: number }) =>
  useQuery({
    queryKey: ["knowledge-search", params],
    queryFn: () => http.get<SearchHit[]>(`/documents/search${qs(params)}`),
    enabled: !!params.q.trim() && !!params.agent_id,
  });

/** Every query a training action can affect for one agent. */
export const trainingKeys = (agentId: string) => [["training", agentId], ["training", "grid"], ["lessons", agentId], ["memories"]];
