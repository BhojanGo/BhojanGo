import type { Metadata } from "next";

import { getContext } from "@/lib/prefs";
import { ProfileView } from "./ProfileView";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("account.profile.meta_title") };
}

export default async function ProfilePage() {
  // The calling codes for linking a mobile number come from Markets (the directory).
  const { directory } = await getContext();
  return <ProfileView countries={directory.countries.map((c) => ({ code: c.code, name: c.name, phone_code: c.phone_code }))} />;
}
