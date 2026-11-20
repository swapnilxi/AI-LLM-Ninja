/** Data hooks for this module (react-query). Query keys: [resource, ...params]. */
import { useQuery } from "@tanstack/react-query";
import { http } from "@/shared/lib/api";
import type { Skill, SkillCommand, SkillTemplate } from "./types";

export const useSkills = () => useQuery({ queryKey: ["skills"], queryFn: () => http.get<Skill[]>("/skills") });

export const useSkill = (id?: string) => useQuery({ queryKey: ["skills", id], queryFn: () => http.get<Skill>(`/skills/${id}`), enabled: !!id && id !== "new" });

export const useSkillCommands = () => useQuery({ queryKey: ["skills", "commands"], queryFn: () => http.get<SkillCommand[]>("/skills/commands"), staleTime: 60_000 });

export const useSkillTemplates = () => useQuery({ queryKey: ["skill-templates"], queryFn: () => http.get<SkillTemplate[]>("/skills/templates"), staleTime: 600_000 });
