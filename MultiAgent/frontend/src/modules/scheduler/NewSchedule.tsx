/** /scheduler/new/chat and /scheduler/new/form: two ways to create a schedule, each with its own URL. */
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ClipboardList, MessageSquareText } from "lucide-react";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { RouteTabs } from "@/shared/ui/RouteTabs";
import { ScheduleChat } from "./ScheduleChat";
import { ScheduleForm } from "./ScheduleForm";
import type { ScheduleDraft } from "./types";

function FormMode() {
  const nav = useNavigate();
  const loc = useLocation();
  const draft = (loc.state as { draft?: ScheduleDraft } | null)?.draft ?? null;
  return (
    <div className="mx-auto max-w-3xl">
      <ScheduleForm key={draft ? "draft" : "blank"} draft={draft} source={draft ? "chat" : "form"} onSaved={(a) => nav(`/scheduler/${a.id}`)} onCancel={() => nav("/scheduler")} />
    </div>
  );
}

export default function NewSchedule() {
  return (
    <Page>
      <PageHeader back="/scheduler" title="New schedule" description="Describe it in a conversation, or fill in the form. Both create the same kind of schedule." />
      <RouteTabs
        className="mb-5"
        tabs={[
          { to: "/scheduler/new/chat", label: "Chat", icon: MessageSquareText },
          { to: "/scheduler/new/form", label: "Form", icon: ClipboardList },
        ]}
      />
      <Routes>
        <Route index element={<Navigate to="chat" replace />} />
        <Route path="chat" element={<ScheduleChat />} />
        <Route path="form" element={<FormMode />} />
      </Routes>
    </Page>
  );
}
