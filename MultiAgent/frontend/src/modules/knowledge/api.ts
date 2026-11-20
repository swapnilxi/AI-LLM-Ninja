/** Data hooks for this module (react-query). Query keys: [resource, ...params]. */
import { useQuery } from "@tanstack/react-query";
import { http, qs } from "@/shared/lib/api";
import type { Doc, Memory } from "./types";

export const useDocuments = (ownerType: string, ownerId?: string) =>
  useQuery({ queryKey: ["documents", ownerType, ownerId], queryFn: () => http.get<Doc[]>(`/documents${qs({ owner_type: ownerType, owner_id: ownerId })}`), enabled: !!ownerId });

export const useMemories = (params: { scope?: string; agent_id?: string; project_id?: string }) =>
  useQuery({ queryKey: ["memories", params], queryFn: () => http.get<Memory[]>(`/memories${qs(params)}`), enabled: !!(params.agent_id || params.project_id) });

export const useDocument = (id?: string) =>
  useQuery({ queryKey: ["document", id], queryFn: () => http.get<Doc & { content: string }>(`/documents/${id}`), enabled: !!id });
