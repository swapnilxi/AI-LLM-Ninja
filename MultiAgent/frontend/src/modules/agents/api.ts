/** Data hooks for this module (react-query). Query keys: [resource, ...params]. */
import { useQuery } from "@tanstack/react-query";
import { http } from "@/shared/lib/api";
import type { Agent } from "./types";

export const useAgents = () => useQuery({ queryKey: ["agents"], queryFn: () => http.get<Agent[]>("/agents") });

export const useAgent = (id?: string) => useQuery({ queryKey: ["agents", id], queryFn: () => http.get<Agent>(`/agents/${id}`), enabled: !!id && id !== "new" });
