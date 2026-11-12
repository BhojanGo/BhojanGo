import { useSession } from "@bhojango/mobile-core";
import { Redirect } from "expo-router";

export default function Index() {
  const status = useSession((s) => s.status);
  return <Redirect href={status === "signed-in" ? "/drive" : "/sign-in"} />;
}
