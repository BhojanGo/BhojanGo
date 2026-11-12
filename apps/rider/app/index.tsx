import { useSession } from "@bhojango/mobile-core";
import { Redirect } from "expo-router";

export default function Index() {
  const status = useSession((s) => s.status);
  const role = useSession((s) => s.user?.role);
  if (status !== "signed-in") return <Redirect href="/sign-in" />;
  return <Redirect href={role === "customer" ? "/join" : "/drive"} />; // a new number finishes signing up first
}
