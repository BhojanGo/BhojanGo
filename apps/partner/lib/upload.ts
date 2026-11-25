// Upload a photo or document to core_api (POST /uploads, multipart). A failure
// throws an Error whose message is the API's reason, or "" (the screen then says
// "partner.upload.failed" in the partner's language).
import { useSession, urls } from "@bhojango/mobile-core";

export interface Uploaded {
  key: string;
  /** Menu photos only: where anyone can load it on core_api ("/api/v1/uploads/menu-photo/..."). */
  public_path?: string;
}

/** One multipart POST through React Native's XMLHttpRequest. R39: the app's global fetch (Expo's) refuses RN's
 * {uri, name, type} file parts ("Unsupported FormDataPart implementation"), so no file ever uploaded. */
function post(url: string, form: FormData, token: string | null): Promise<{ status: number; text: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    if (token) xhr.setRequestHeader("authorization", `Bearer ${token}`);
    xhr.onload = () => resolve({ status: xhr.status, text: xhr.responseText });
    xhr.onerror = () => reject(new TypeError("Network request failed"));
    xhr.ontimeout = () => reject(new TypeError("Network request failed"));
    xhr.timeout = 60000;
    xhr.send(form);
  });
}

export async function uploadFile(uri: string, mime: string, purpose: "partner_document" | "menu_photo"): Promise<Uploaded> {
  const send = (token: string | null) => {
    const form = new FormData();
    form.append("purpose", purpose);
    const ext = mime === "application/pdf" ? "pdf" : mime === "image/png" ? "png" : mime === "image/webp" ? "webp" : "jpg";
    // React Native's FormData takes {uri, name, type} for a file.
    form.append("file", { uri, name: `upload.${ext}`, type: mime } as unknown as Blob);
    return post(`${urls.core}/api/v1/uploads`, form, token);
  };
  let res = await send(useSession.getState().accessToken);
  if (res.status === 401) res = await send(await useSession.getState().refresh());
  let body: (Uploaded & { detail?: { message?: string } | string }) | null = null;
  try {
    body = JSON.parse(res.text) as Uploaded & { detail?: { message?: string } | string };
  } catch {
    body = null;
  }
  if (res.status < 200 || res.status >= 300 || !body?.key) {
    const d = body?.detail;
    throw new Error(typeof d === "string" ? d : d?.message ?? "");
  }
  return { key: body.key, public_path: body.public_path };
}

/** A menu photo's address for the item's image_url: core_api's public path, made absolute. */
export function menuPhotoUrl(publicPath: string): string {
  return `${urls.core}${publicPath}`;
}
