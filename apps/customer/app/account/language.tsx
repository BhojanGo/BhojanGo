// Language and country (the website header's two separate selectors). The
// languages are exactly the current country's (Markets locales). The country
// follows the delivery address; without one you choose it here (kept on the
// phone). Prices and dates keep the country's format whatever the language.
import { CountryPicker, LanguagePicker, useCountry, useI18n, type Language } from "@bhojango/mobile-core";
import { ScrollView, Text } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { updateMe } from "../../lib/account";
import { Row, ScreenBar, Section, Status, ui } from "../../lib/account-ui";

export default function LanguageScreen() {
  const { t } = useI18n();
  const { country, source, loading, error, reload } = useCountry();

  // Remember it on the account too (texts, emails), as the website does; a pair the API doesn't know is skipped.
  const remember = (lang: Language) => {
    if (!country) return;
    const locale = `${lang}-${country.code}` as NonNullable<Parameters<typeof updateMe>[0]["preferred_locale"]>;
    void updateMe({ preferred_locale: locale }).catch(() => undefined);
  };

  return (
    <SafeAreaView style={ui.screen} edges={["top", "left", "right"]}>
      <ScreenBar title={t("account.profile.language_country")} testID="language-title" />
      <ScrollView contentContainerStyle={ui.scroll}>
        <Section title={country ? t("header.language_title", { country: country.name }) : t("header.language")} testID="language-section">
          <Text style={ui.muted}>{t("account.profile.language_note")}</Text>
          <LanguagePicker onChange={remember} />
        </Section>

        <Section title={t("header.country_title")} testID="country-section">
          <Status loading={loading} error={error ? t("common.error") : null} onRetry={reload} />
          {source === "address" && country ? (
            <Row label={t("account.profile.country")} value={country.name} note={t("account.profile.country_note")} last />
          ) : (
            <>
              <Text style={ui.muted}>{t("header.country_note")}</Text>
              <CountryPicker />
            </>
          )}
        </Section>
      </ScrollView>
    </SafeAreaView>
  );
}
