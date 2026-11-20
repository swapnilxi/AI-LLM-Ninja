/** Data hooks for this module (react-query). Query keys: [resource, ...params]. */
import { useQuery } from "@tanstack/react-query";
import { http } from "@/shared/lib/api";
import type { ProviderInfo } from "./types";

export const useProviders = () =>
  useQuery({ queryKey: ["providers"], queryFn: () => http.get<{ providers: ProviderInfo[]; default: { provider: string; model: string } }>("/org/providers") });
