// Moved: reporting a problem lives with your orders in the account now.
import { redirect } from "next/navigation";

export default async function OldReport({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/account/orders/${encodeURIComponent(id)}/report`);
}
