import type { MetadataRoute } from "next";

import { robotsRules } from "@/lib/indexing";
import { SITE } from "@/lib/server";

// Outside production (QA, staging, local) robots.txt blocks everything (lib/indexing.ts).
export default function robots(): MetadataRoute.Robots {
  return robotsRules(process.env.APP_ENV, SITE);
}
