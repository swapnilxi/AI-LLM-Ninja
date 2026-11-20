import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { errMsg } from "@/shared/lib/utils";

/** Generic mutation with toast + invalidation. */
export function useAction<TVars = void, TRes = any>(fn: (v: TVars) => Promise<TRes>, opts: { success?: string; invalidate?: unknown[][]; onSuccess?: (r: TRes, v: TVars) => void } = {}) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (res, vars) => {
      if (opts.success) toast.success(opts.success);
      opts.invalidate?.forEach((k) => qc.invalidateQueries({ queryKey: k }));
      opts.onSuccess?.(res, vars);
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}
