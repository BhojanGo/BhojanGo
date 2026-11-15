import type { Metadata } from "next";

import { getContext } from "@/lib/prefs";
import { ProfileView } from "./ProfileView";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getContext();
  return { title: t("account.profile.meta_title") };
}

export default function ProfilePage() {
  return <ProfileView />;
}
