/** Data hooks for this module (react-query). Query keys: [resource, ...params]. */
import { useQuery } from "@tanstack/react-query";
import { http } from "@/shared/lib/api";
import type { Workflow } from "./types";

export const useWorkflows = () => useQuery({ queryKey: ["workflows"], queryFn: () => http.get<Workflow[]>("/workflows") });

export const useWorkflow = (id?: string) => useQuery({ queryKey: ["workflows", id], queryFn: () => http.get<Workflow>(`/workflows/${id}`), enabled: !!id && id !== "new" });
