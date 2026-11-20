import { lazy } from "react";
import { MessagesSquare, Plus } from "lucide-react";
import { defineModule } from "@/shared/lib/modules";

const Chat = lazy(() => import("./Chat"));

export default defineModule({
  id: "chat",
  nav: [{ to: "/chat", label: "Chat", icon: MessagesSquare, section: "", order: 1 }],
  commands: [{ id: "n-chat", group: "Create", label: "New chat", icon: Plus, to: "/chat/new", keywords: "conversation talk agent team" }],
  // One splat route: /chat, /chat/new, /chat/:conversationId, /chat/:conversationId/skills, /chat/:conversationId/commands
  routes: [{ path: "chat/*", element: <Chat /> }],
});
