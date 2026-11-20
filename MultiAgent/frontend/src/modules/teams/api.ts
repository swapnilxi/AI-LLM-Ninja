/** Data hooks for this module (react-query). Query keys: [resource, ...params]. */
import { useQuery } from "@tanstack/react-query";
import { http } from "@/shared/lib/api";
import type { Team } from "./types";

export const useTeams = () => useQuery({ queryKey: ["teams"], queryFn: () => http.get<Team[]>("/teams") });

export const useTeam = (id?: string) => useQuery({ queryKey: ["teams", id], queryFn: () => http.get<Team>(`/teams/${id}`), enabled: !!id && id !== "new" });
