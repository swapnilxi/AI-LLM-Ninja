import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { http, session } from "./api";
import type { AuthResponse, Org, Role, User } from "@/shared/lib/types";
import type { Project } from "@/modules/projects/types";

const RANK: Record<Role, number> = { viewer: 0, member: 1, admin: 2, owner: 3 };

interface AuthCtx {
  user: User | null;
  orgs: Org[];
  org: Org | null;
  loading: boolean;
  projects: Project[];
  project: Project | null;
  projectId: string | null;
  setProjectId: (id: string) => void;
  login: (email: string, password: string) => Promise<void>;
  register: (body: { email: string; name: string; password: string; org_name?: string }) => Promise<void>;
  logout: () => void;
  switchOrg: (id: string) => void;
  refresh: () => Promise<void>;
  can: (role: Role) => boolean;
}

const Ctx = createContext<AuthCtx | null>(null);

function projectKey(orgId: string) {
  return `af_project_${orgId}`;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [orgId, setOrgId] = useState<string | null>(session.orgId);
  const [loading, setLoading] = useState<boolean>(!!session.token);
  const [projectId, setProjectIdState] = useState<string | null>(null);

  const apply = useCallback((data: AuthResponse) => {
    setUser(data.user);
    setOrgs(data.orgs);
    const current = data.orgs.find((o) => o.id === session.orgId) ?? data.orgs[0] ?? null;
    session.set(data.access_token, current?.id ?? null);
    setOrgId(current?.id ?? null);
  }, []);

  const refresh = useCallback(async () => {
    if (!session.token) {
      setLoading(false);
      return;
    }
    try {
      apply(await http.get<AuthResponse>("/auth/me"));
    } catch {
      session.set(null, null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [apply]);

  useEffect(() => {
    refresh();
    const onUnauthorized = () => {
      session.set(null);
      setUser(null);
      qc.clear();
    };
    window.addEventListener("af:unauthorized", onUnauthorized);
    return () => window.removeEventListener("af:unauthorized", onUnauthorized);
  }, [refresh, qc]);

  const projectsQ = useQuery({
    queryKey: ["projects", orgId],
    queryFn: () => http.get<Project[]>("/projects"),
    enabled: !!user && !!orgId,
  });
  const projects = projectsQ.data ?? [];

  useEffect(() => {
    if (!orgId || !projects.length) return;
    let saved: string | null = null;
    try {
      saved = localStorage.getItem(projectKey(orgId));
    } catch {
      /* ignore */
    }
    const valid = projects.find((p) => p.id === (projectId ?? saved));
    if (!valid) setProjectIdState(projects[0].id);
    else if (valid.id !== projectId) setProjectIdState(valid.id);
  }, [orgId, projects, projectId]);

  const setProjectId = useCallback(
    (id: string) => {
      setProjectIdState(id);
      try {
        if (orgId) localStorage.setItem(projectKey(orgId), id);
      } catch {
        /* ignore */
      }
    },
    [orgId],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      apply(await http.post<AuthResponse>("/auth/login", { email, password }));
    },
    [apply],
  );

  const register = useCallback(
    async (body: { email: string; name: string; password: string; org_name?: string }) => {
      apply(await http.post<AuthResponse>("/auth/register", body));
    },
    [apply],
  );

  const logout = useCallback(() => {
    session.set(null, null);
    setUser(null);
    setOrgs([]);
    qc.clear();
  }, [qc]);

  const switchOrg = useCallback(
    (id: string) => {
      session.setOrg(id);
      setOrgId(id);
      setProjectIdState(null);
      qc.clear();
    },
    [qc],
  );

  const org = orgs.find((o) => o.id === orgId) ?? null;
  const value = useMemo<AuthCtx>(
    () => ({
      user,
      orgs,
      org,
      loading,
      projects,
      project: projects.find((p) => p.id === projectId) ?? null,
      projectId,
      setProjectId,
      login,
      register,
      logout,
      switchOrg,
      refresh,
      can: (role: Role) => (org ? RANK[org.role] >= RANK[role] : false),
    }),
    [user, orgs, org, loading, projects, projectId, setProjectId, login, register, logout, switchOrg, refresh],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
