/** Data hooks for this module (react-query). Query keys: [resource, ...params]. */
import { useQuery } from "@tanstack/react-query";
import { http, qs } from "@/shared/lib/api";
import type { Task } from "./types";

export const useTasks = (projectId?: string | null) =>
  useQuery({ queryKey: ["tasks", projectId], queryFn: () => http.get<Task[]>(`/tasks${qs({ project_id: projectId ?? undefined })}`), enabled: !!projectId });
