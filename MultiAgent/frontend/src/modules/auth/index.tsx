import { defineModule } from "@/shared/lib/modules";
import Login from "./Login";
import Register from "./Register";

export default defineModule({
  id: "auth",
  routes: [
    { path: "login", element: <Login />, public: true },
    { path: "register", element: <Register />, public: true },
  ],
});
