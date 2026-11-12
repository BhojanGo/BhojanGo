// Upload a photo or document to core_api (POST /uploads, multipart).
import { useSession, urls } from "@bhojango/mobile-core";

export async function uploadFile(uri: string, mime: string, purpose: "delivery_proof" | "rider_document"): Promise<string> {
  const send = async (token: string | null) => {
    const form = new FormData();
    form.append("purpose", purpose);
    const ext = mime === "application/pdf" ? "pdf" : mime === "image/png" ? "png" : "jpg";
    // React Native's FormData takes {uri, name, type} for a file.
    form.append("file", { uri, name: `upload.${ext}`, type: mime } as unknown as Blob);
    return fetch(`${urls.core}/api/v1/uploads`, { method: "POST", headers: token ? { authorization: `Bearer ${token}` } : {}, body: form });
  };
  let res = await send(useSession.getState().accessToken);
  if (res.status === 401) res = await send(await useSession.getState().refresh());
  const body = (await res.json().catch(() => null)) as { key?: string; detail?: { message?: string } | string } | null;
  if (!res.ok || !body?.key) {
    const d = body?.detail;
    throw new Error(typeof d === "string" ? d : d?.message ?? "The upload didn't go through. Try again.");
  }
  return body.key;
}
