/** Data hooks for the scheduler module (react-query). Query keys: ["schedules", ...]. */
import { useQuery } from "@tanstack/react-query";
import { http, qs } from "@/shared/lib/api";
import type { Run } from "@/modules/runs/types";
import type { Automation, UpcomingRun } from "./types";

export const useSchedules = (projectId?: string | null) =>
  useQuery({ queryKey: ["schedules", "list", projectId], queryFn: () => http.get<Automation[]>(`/schedules${qs({ project_id: projectId ?? undefined })}`) });

export const useSchedule = (id?: string) =>
  useQuery({ queryKey: ["schedules", "one", id], queryFn: () => http.get<Automation>(`/schedules/${id}`), enabled: !!id });

export const useUpcoming = (projectId?: string | null, days = 7) =>
  useQuery({
    queryKey: ["schedules", "upcoming", projectId, days],
    queryFn: () => http.get<UpcomingRun[]>(`/schedules/upcoming${qs({ project_id: projectId ?? undefined, days })}`),
    refetchInterval: 60_000,
  });

export const useScheduleRuns = (id?: string) =>
  useQuery({ queryKey: ["runs", { automation_id: id }], queryFn: () => http.get<{ total: number; items: Run[] }>(`/runs${qs({ automation_id: id, limit: 50 })}`), enabled: !!id, refetchInterval: 15_000 });
