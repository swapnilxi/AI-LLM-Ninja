/** Data hooks for this module (react-query). Query keys: [resource, ...params]. */
import { useQuery } from "@tanstack/react-query";
import { http } from "@/shared/lib/api";
import type { Connection, Connector } from "./types";

export const useConnections = () => useQuery({ queryKey: ["connections"], queryFn: () => http.get<Connection[]>("/connections") });

export const useConnectorCatalog = () => useQuery({ queryKey: ["connector-catalog"], queryFn: () => http.get<Connector[]>("/connectors/catalog"), staleTime: 600_000 });
