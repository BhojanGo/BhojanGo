// Language: the same list as the header's pill (the current country's Markets
// locales, each in its own script). There is no country selector: the country
// follows the delivery address ("Change city" on the home screen). Prices and
// dates keep the country's format whatever the language.
import { type Language, LanguagePicker, SafeAreaView, useCountry, useI18n } from "@bhojango/mobile-core";
import { ScrollView, Text } from "react-native";

import { updateMe } from "../../lib/account";
import { ScreenBar, Section, ui } from "../../lib/account-ui";

export default function LanguageScreen() {
  const { t } = useI18n();
  const { country } = useCountry();

  // Here (not on the header's pill) it is also remembered on the account (texts,
  // emails), as the website's account page does; a pair the API doesn't know is skipped.
  const remember = (lang: Language) => {
    if (!country) return;
    const locale = `${lang}-${country.code}` as NonNullable<Parameters<typeof updateMe>[0]["preferred_locale"]>;
    void updateMe({ preferred_locale: locale }).catch(() => undefined);
  };

  return (
    <SafeAreaView style={ui.screen} edges={["top", "left", "right"]}>
      <ScreenBar title={t("header.language")} testID="language-title" />
      <ScrollView contentContainerStyle={ui.scroll}>
        <Section title={country ? t("header.language_title", { country: country.name }) : t("header.language")} testID="language-section">
          <Text style={ui.muted}>{t("account.profile.language_note")}</Text>
          <LanguagePicker onChange={remember} />
        </Section>
      </ScrollView>
    </SafeAreaView>
  );
}
