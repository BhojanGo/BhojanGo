// A photo for a problem report (B5): uploaded first, then sent with the report by its key.
import { urls, useSession } from "@bhojango/mobile-core";

export async function uploadPhoto(uri: string, mime: string): Promise<string> {
  const send = async (token: string | null) => {
    const form = new FormData();
    form.append("purpose", "problem_photo");
    const ext = mime === "image/png" ? "png" : mime === "image/webp" ? "webp" : "jpg";
    // React Native's FormData takes {uri, name, type} for a file.
    form.append("file", { uri, name: `problem.${ext}`, type: mime } as unknown as Blob);
    return fetch(`${urls.core}/api/v1/uploads`, { method: "POST", headers: token ? { authorization: `Bearer ${token}` } : {}, body: form });
  };
  let res = await send(useSession.getState().accessToken);
  if (res.status === 401) res = await send(await useSession.getState().refresh());
  const body = (await res.json().catch(() => null)) as { key?: string; detail?: { message?: string } | string } | null;
  if (!res.ok || !body?.key) {
    const d = body?.detail;
    throw new Error(typeof d === "string" ? d : d?.message ?? "The photo didn't upload. Try again, or send without it.");
  }
  return body.key;
}
