/** Data hooks for this module (react-query). Query keys: [resource, ...params]. */
import { useQuery } from "@tanstack/react-query";
import { http, qs } from "@/shared/lib/api";
import type { HubCatalog } from "./types";

/** Discover catalog (skill packs, MCP servers, knowledge docs) with install state for the given project. */
export const useHub = (projectId?: string | null) =>
  useQuery({ queryKey: ["hub", projectId], queryFn: () => http.get<HubCatalog>(`/hub${qs({ project_id: projectId ?? undefined })}`), enabled: !!projectId });
