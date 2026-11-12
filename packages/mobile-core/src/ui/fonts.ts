// Load the two brand typefaces in every app before the first screen draws.
import { FamiljenGrotesk_500Medium, FamiljenGrotesk_600SemiBold, FamiljenGrotesk_700Bold } from "@expo-google-fonts/familjen-grotesk";
import {
  HankenGrotesk_400Regular,
  HankenGrotesk_500Medium,
  HankenGrotesk_600SemiBold,
  HankenGrotesk_700Bold,
  HankenGrotesk_800ExtraBold,
} from "@expo-google-fonts/hanken-grotesk";
import { useFonts } from "expo-font";

export function useBrandFonts(): boolean {
  const [loaded] = useFonts({
    FamiljenGrotesk_500Medium,
    FamiljenGrotesk_600SemiBold,
    FamiljenGrotesk_700Bold,
    HankenGrotesk_400Regular,
    HankenGrotesk_500Medium,
    HankenGrotesk_600SemiBold,
    HankenGrotesk_700Bold,
    HankenGrotesk_800ExtraBold,
  });
  return loaded;
}
