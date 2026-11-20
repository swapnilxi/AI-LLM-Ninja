import { Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "@/shared/lib/auth";
import { AppShell } from "@/shared/layout/AppShell";
import { PageLoader } from "@/shared/ui/primitives";
import { MODULES } from "@/modules/registry";

const ROUTES = MODULES.flatMap((m) => m.routes.map((r, i) => ({ ...r, key: `${m.id}:${r.path ?? "index"}:${i}` })));

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      {ROUTES.filter((r) => r.public).map((r) => (
        <Route key={r.key} path={r.path} element={r.element} />
      ))}
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route
          path="*"
          element={
            <Suspense fallback={<PageLoader />}>
              <Routes>
                {ROUTES.filter((r) => !r.public).map((r) => (r.index ? <Route key={r.key} index element={r.element} /> : <Route key={r.key} path={r.path} element={r.element} />))}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          }
        />
      </Route>
    </Routes>
  );
}
