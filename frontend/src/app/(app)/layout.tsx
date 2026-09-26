import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { getCurrentUser } from "@/lib/api/server";

/**
 * The signed-in half of the app.
 *
 * The user is resolved on the server before anything renders. If the session has gone,
 * this redirects rather than rendering a shell that would 401 on its first request.
 */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  return <AppShell user={user}>{children}</AppShell>;
}
