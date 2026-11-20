/** /scheduler and /scheduler/upcoming share this header + URL tabs. */
import { useNavigate } from "react-router-dom";
import { CalendarDays, List, MessageSquareText, Plus } from "lucide-react";
import { useAuth } from "@/shared/lib/auth";
import { Page, PageHeader } from "@/shared/layout/PageHeader";
import { Button } from "@/shared/ui/primitives";
import { RouteTabs } from "@/shared/ui/RouteTabs";
import { useSchedules, useUpcoming } from "./api";
import ScheduleList from "./ScheduleList";
import Upcoming from "./Upcoming";

export default function SchedulerLayout({ view }: { view: "list" | "upcoming" }) {
  const { projectId, project, can } = useAuth();
  const list = useSchedules(projectId);
  const upcoming = useUpcoming(projectId);
  const nav = useNavigate();
  return (
    <Page>
      <PageHeader
        title="Scheduler"
        description={`Run agents, teams and workflows once, on a schedule, at an interval or from webhooks${project ? ` in “${project.name}”` : ""}. Set things up by chatting or with a form.`}
        actions={
          can("member") && (
            <>
              <Button variant="outline" icon={<MessageSquareText className="size-4" />} onClick={() => nav("/scheduler/new/chat")} disabled={!projectId}>
                Schedule by chat
              </Button>
              <Button icon={<Plus className="size-4" />} onClick={() => nav("/scheduler/new/form")} disabled={!projectId}>
                New schedule
              </Button>
            </>
          )
        }
      />
      <RouteTabs
        className="mb-5"
        tabs={[
          { to: "/scheduler", label: "Schedules", icon: List, end: true, count: list.data?.length },
          { to: "/scheduler/upcoming", label: "Upcoming", icon: CalendarDays, count: upcoming.data?.length },
        ]}
      />
      {view === "upcoming" ? <Upcoming /> : <ScheduleList />}
    </Page>
  );
}
