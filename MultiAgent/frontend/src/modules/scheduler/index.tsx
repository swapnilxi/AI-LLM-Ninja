import { lazy } from "react";
import { Navigate, useParams } from "react-router-dom";
import { CalendarClock, MessageSquareText, Plus } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const SchedulerLayout = lazy(() => import("./SchedulerLayout"));
const NewSchedule = lazy(() => import("./NewSchedule"));
const ScheduleDetail = lazy(() => import("./ScheduleDetail"));

/** Old /automations links keep working. */
function LegacyRedirect() {
  const { id } = useParams();
  return <Navigate to={id ? `/scheduler/${id}` : "/scheduler"} replace />;
}

export default defineModule({
  id: "scheduler",
  nav: [{ to: "/scheduler", label: "Scheduler", icon: CalendarClock, section: "Operate", order: 20, keywords: "schedule cron webhook automations reminders calendar upcoming" }],
  commands: [
    { id: "n-sched-chat", group: "Create", label: "Schedule by chat", icon: MessageSquareText, to: "/scheduler/new/chat", keywords: "remind me later every day" },
    { id: "n-sched", group: "Create", label: "New schedule (form)", icon: Plus, to: "/scheduler/new/form" },
    { id: "p-upcoming", label: "Upcoming scheduled runs", icon: CalendarClock, to: "/scheduler/upcoming", keywords: "agenda calendar" },
  ],
  routes: [
    { path: "scheduler/new/*", element: <NewSchedule /> },
    { path: "scheduler/upcoming", element: <SchedulerLayout view="upcoming" /> },
    { path: "scheduler", element: <SchedulerLayout view="list" /> },
    { path: "scheduler/:id/*", element: <ScheduleDetail /> },
    { path: "automations", element: <LegacyRedirect /> },
    { path: "automations/:id", element: <LegacyRedirect /> },
  ],
});
