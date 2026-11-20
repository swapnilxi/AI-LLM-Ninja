/** Data hooks for this module (react-query). Query keys: [resource, ...params]. */
import { useQuery } from "@tanstack/react-query";
import { http } from "@/shared/lib/api";
import type { Tool } from "./types";

export const useTools = () => useQuery({ queryKey: ["tools"], queryFn: () => http.get<Tool[]>("/tools") });

export const useTool = (id?: string) => useQuery({ queryKey: ["tools", id], queryFn: () => http.get<Tool>(`/tools/${id}`), enabled: !!id && id !== "new" });
