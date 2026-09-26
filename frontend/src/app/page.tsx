import { redirect } from "next/navigation";

/** There is no marketing page: the root is the dashboard, behind the middleware guard. */
export default function RootPage() {
  redirect("/dashboard");
}
