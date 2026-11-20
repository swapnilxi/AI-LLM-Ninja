import { useQuery } from "@tanstack/react-query";
import { http } from "@/shared/lib/api";
import type { Catalog } from "@/shared/lib/types";

export const useCatalog = () => useQuery({ queryKey: ["catalog"], queryFn: () => http.get<Catalog>("/catalog"), staleTime: 600_000 });
