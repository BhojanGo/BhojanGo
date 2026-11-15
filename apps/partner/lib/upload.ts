// Upload a photo or document to core_api (POST /uploads, multipart). A failure
// throws an Error whose message is the API's reason, or "" (the screen then says
// "partner.upload.failed" in the partner's language).
import { useSession, urls } from "@bhojango/mobile-core";

export interface Uploaded {
  key: string;
  /** Menu photos only: where anyone can load it on core_api ("/api/v1/uploads/menu-photo/..."). */
  public_path?: string;
}

export async function uploadFile(uri: string, mime: string, purpose: "partner_document" | "menu_photo"): Promise<Uploaded> {
  const send = async (token: string | null) => {
    const form = new FormData();
    form.append("purpose", purpose);
    const ext = mime === "application/pdf" ? "pdf" : mime === "image/png" ? "png" : mime === "image/webp" ? "webp" : "jpg";
    // React Native's FormData takes {uri, name, type} for a file.
    form.append("file", { uri, name: `upload.${ext}`, type: mime } as unknown as Blob);
    return fetch(`${urls.core}/api/v1/uploads`, { method: "POST", headers: token ? { authorization: `Bearer ${token}` } : {}, body: form });
  };
  let res = await send(useSession.getState().accessToken);
  if (res.status === 401) res = await send(await useSession.getState().refresh());
  const body = (await res.json().catch(() => null)) as (Uploaded & { detail?: { message?: string } | string }) | null;
  if (!res.ok || !body?.key) {
    const d = body?.detail;
    throw new Error(typeof d === "string" ? d : d?.message ?? "");
  }
  return { key: body.key, public_path: body.public_path };
}

/** A menu photo's address for the item's image_url: core_api's public path, made absolute. */
export function menuPhotoUrl(publicPath: string): string {
  return `${urls.core}${publicPath}`;
}
