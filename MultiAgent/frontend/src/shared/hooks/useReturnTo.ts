/** Pages that replaced modals accept `?return_to=/some/path` so they can send the user back where they came from. */
import { useSearchParams } from "react-router-dom";

export function useReturnTo(fallback: string): string {
  const [params] = useSearchParams();
  const r = params.get("return_to");
  // only same-app absolute paths (no protocol-relative or external URLs)
  return r && r.startsWith("/") && !r.startsWith("//") ? r : fallback;
}

/** Build a link that carries the current location as `return_to`. */
export function withReturn(to: string, returnTo: string): string {
  return `${to}${to.includes("?") ? "&" : "?"}return_to=${encodeURIComponent(returnTo)}`;
}
