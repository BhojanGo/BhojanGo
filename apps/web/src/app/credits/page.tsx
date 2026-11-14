// Photo credits, generated from docs/design/photos/LICENSES.md by tools/photos/credits.py
// (never edit photo-credits.json by hand; make ci checks it is up to date).
import type { Metadata } from "next";

import { Prose } from "@/components/Prose";
import credits from "@/content/photo-credits.json";

export const metadata: Metadata = { title: "Photo credits", description: "The photographers whose work appears on BhojanGo, and their licenses." };

type Credit = { slug: string; title: string; source: string; creator: string; license: string; licenseUrl: string; changes: string };

export default function Credits() {
  const list = credits as Credit[];
  return (
    <Prose
      title="Photo credits"
      intro="Some of the food photos on BhojanGo are shared by their photographers under Creative Commons licenses. Thank you."
      sections={[
        {
          id: "photos",
          title: "Photos",
          body: list.length ? (
            <ul className="space-y-3">
              {list.map((c) => (
                <li key={c.slug}>
                  <a href={c.source} className="font-semibold text-peacock hover:underline" rel="noopener noreferrer">{c.title || c.slug}</a>
                  {" by "}{c.creator}{", "}
                  <a href={c.licenseUrl} className="text-peacock hover:underline" rel="noopener noreferrer license">{c.license}</a>
                  {c.changes ? <span className="text-muted"> ({c.changes.toLowerCase()} by BhojanGo)</span> : null}
                </li>
              ))}
            </ul>
          ) : <p>Every photo we use is in the public domain.</p>,
        },
      ]}
    />
  );
}
