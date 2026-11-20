import { useInfiniteQuery } from "@tanstack/react-query";
import { ScrollText } from "lucide-react";
import { http } from "@/shared/lib/api";
import { formatDate, timeAgo } from "@/shared/lib/utils";
import { Badge, Button, Card, CardHeader, EmptyState, PageLoader } from "@/shared/ui/primitives";

interface AuditRow {
  id: number;
  action: string;
  user: string;
  target_type: string;
  target_id: string;
  ip: string;
  details: Record<string, any>;
  created_at: string;
}

const PAGE = 100;

function tone(action: string): "danger" | "warning" | "primary" | "muted" {
  if (/delete|remove|revoke|locked/.test(action)) return "danger";
  if (/secret|apikey|provider|password|role/.test(action)) return "warning";
  if (/create|add|register/.test(action)) return "primary";
  return "muted";
}

export function AuditTab() {
  const q = useInfiniteQuery({
    queryKey: ["audit"],
    queryFn: ({ pageParam }) => http.get<AuditRow[]>(`/org/audit?limit=${PAGE}&offset=${pageParam}`),
    initialPageParam: 0,
    getNextPageParam: (last, all) => (last.length === PAGE ? all.length * PAGE : undefined),
  });
  if (q.isLoading) return <PageLoader />;
  const rows = q.data?.pages.flat() ?? [];
  return (
    <Card>
      <CardHeader title="Audit log" description="Security-relevant activity: sign-ins, membership, keys, providers, connectors, secrets and deletions." />
      {rows.length === 0 ? (
        <EmptyState icon={<ScrollText className="size-5" />} title="No activity yet" className="m-4 border-0" />
      ) : (
        <>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <thead className="border-b border-border text-left text-xs text-muted">
                <tr>
                  <th className="px-4 py-2 font-medium">When</th>
                  <th className="px-4 py-2 font-medium">Action</th>
                  <th className="px-4 py-2 font-medium">User</th>
                  <th className="px-4 py-2 font-medium">Target</th>
                  <th className="px-4 py-2 font-medium">IP</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((r) => (
                  <tr key={r.id} className="hover:bg-surface-2/50">
                    <td className="whitespace-nowrap px-4 py-2 text-muted" title={formatDate(r.created_at)}>{timeAgo(r.created_at)}</td>
                    <td className="px-4 py-2"><Badge tone={tone(r.action)} className="font-mono">{r.action}</Badge></td>
                    <td className="max-w-[220px] truncate px-4 py-2">{r.user || "—"}</td>
                    <td className="max-w-[260px] truncate px-4 py-2 font-mono text-xs text-muted">{[r.target_type, r.target_id].filter(Boolean).join(" ") || "—"}</td>
                    <td className="px-4 py-2 font-mono text-xs text-muted">{r.ip || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="divide-y divide-border md:hidden">
            {rows.map((r) => (
              <li key={r.id} className="px-4 py-3">
                <div className="flex items-center justify-between gap-2">
                  <Badge tone={tone(r.action)} className="font-mono">{r.action}</Badge>
                  <span className="text-xs text-muted">{timeAgo(r.created_at)}</span>
                </div>
                <div className="mt-1 truncate text-xs text-muted">
                  {r.user || "system"}
                  {r.target_id && <> · <span className="font-mono">{r.target_id}</span></>}
                  {r.ip && <> · {r.ip}</>}
                </div>
              </li>
            ))}
          </ul>
          {q.hasNextPage && (
            <div className="border-t border-border p-3 text-center">
              <Button variant="outline" size="sm" loading={q.isFetchingNextPage} onClick={() => q.fetchNextPage()}>Load more</Button>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
