// The brand faces, loaded before the first screen draws, and the Noto Sans face
// for an Indian-script language, loaded when that language is chosen (I18nProvider).
// Only the weights the type scale uses: Familjen Grotesk 600; Hanken Grotesk and
// Noto Sans 400/600/700 (see ./type.ts).
// One import per weight (the package index would bundle all 9 weights and their italics).
import { FamiljenGrotesk_600SemiBold } from "@expo-google-fonts/familjen-grotesk/600SemiBold";
import { HankenGrotesk_400Regular } from "@expo-google-fonts/hanken-grotesk/400Regular";
import { HankenGrotesk_600SemiBold } from "@expo-google-fonts/hanken-grotesk/600SemiBold";
import { HankenGrotesk_700Bold } from "@expo-google-fonts/hanken-grotesk/700Bold";
import { NotoSansBengali_400Regular } from "@expo-google-fonts/noto-sans-bengali/400Regular";
import { NotoSansBengali_600SemiBold } from "@expo-google-fonts/noto-sans-bengali/600SemiBold";
import { NotoSansBengali_700Bold } from "@expo-google-fonts/noto-sans-bengali/700Bold";
import { NotoSansDevanagari_400Regular } from "@expo-google-fonts/noto-sans-devanagari/400Regular";
import { NotoSansDevanagari_600SemiBold } from "@expo-google-fonts/noto-sans-devanagari/600SemiBold";
import { NotoSansDevanagari_700Bold } from "@expo-google-fonts/noto-sans-devanagari/700Bold";
import { NotoSansKannada_400Regular } from "@expo-google-fonts/noto-sans-kannada/400Regular";
import { NotoSansKannada_600SemiBold } from "@expo-google-fonts/noto-sans-kannada/600SemiBold";
import { NotoSansKannada_700Bold } from "@expo-google-fonts/noto-sans-kannada/700Bold";
import { NotoSansTamil_400Regular } from "@expo-google-fonts/noto-sans-tamil/400Regular";
import { NotoSansTamil_600SemiBold } from "@expo-google-fonts/noto-sans-tamil/600SemiBold";
import { NotoSansTamil_700Bold } from "@expo-google-fonts/noto-sans-tamil/700Bold";
import { NotoSansTelugu_400Regular } from "@expo-google-fonts/noto-sans-telugu/400Regular";
import { NotoSansTelugu_600SemiBold } from "@expo-google-fonts/noto-sans-telugu/600SemiBold";
import { NotoSansTelugu_700Bold } from "@expo-google-fonts/noto-sans-telugu/700Bold";
import { loadAsync, useFonts } from "expo-font";

import type { Script } from "./type";

export function useBrandFonts(): boolean {
  const [loaded] = useFonts({
    FamiljenGrotesk_600SemiBold,
    HankenGrotesk_400Regular,
    HankenGrotesk_600SemiBold,
    HankenGrotesk_700Bold,
  });
  return loaded;
}

// Family names match familyFor() in ./type.ts.
const SCRIPT_FONTS: Record<Exclude<Script, "latin">, Record<string, number>> = {
  devanagari: { NotoSansDevanagari_400Regular, NotoSansDevanagari_600SemiBold, NotoSansDevanagari_700Bold },
  telugu: { NotoSansTelugu_400Regular, NotoSansTelugu_600SemiBold, NotoSansTelugu_700Bold },
  tamil: { NotoSansTamil_400Regular, NotoSansTamil_600SemiBold, NotoSansTamil_700Bold },
  kannada: { NotoSansKannada_400Regular, NotoSansKannada_600SemiBold, NotoSansKannada_700Bold },
  bengali: { NotoSansBengali_400Regular, NotoSansBengali_600SemiBold, NotoSansBengali_700Bold },
};

/** Load the Noto Sans faces for a script (no-op for Latin, cached by expo-font). */
export async function loadScriptFonts(script: Script): Promise<void> {
  if (script === "latin") return;
  await loadAsync(SCRIPT_FONTS[script]);
}
