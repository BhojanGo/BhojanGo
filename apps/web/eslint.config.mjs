import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import typeScale from "@bhojango/config/eslint-rules";

// typeScaleLint: font sizes only from the type scale (text-display ... text-caption).
export default defineConfig([...nextVitals, ...typeScale.typeScaleLint, globalIgnores([".next/**", "out/**", "next-env.d.ts"])]);
