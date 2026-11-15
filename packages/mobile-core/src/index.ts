// Shared by the Expo apps (customer, rider; partner from P19).

// Design system (P16): tokens, fonts and components; same tokens as @bhojango/ui on the web.
export * from "./ui/components";
export { useBrandFonts } from "./ui/fonts";
export { color, dark, displayFont, elevation, FONT_FILES, radius, space, textFont, touch, typeStyle } from "./ui/theme";
export { billTotal } from "@bhojango/ui/bill";
// Round 5: the floating tab bar's geometry and the room every tab screen leaves for it.
export { aboveTabBar, TAB_BAR_BREATHING, TAB_BAR_GAP, TAB_BAR_HEIGHT, TAB_BAR_INSET_GAP, TAB_BAR_LIFT, tabBarBottom, tabBarClearance } from "./tabbar";

// P17: generated API client, session and bag.
export { api, urls, useSession, wsUrl } from "./session";
export type { User } from "./session";
export { cartItems, defaultPicks, useBag } from "./bag";
// B2: quick messages between the customer and the rider during an order.
export { QuickChat, useQuickMessages } from "./chat";
export type { BagLine, OptionGroup, Pick } from "./bag";
export { ACTIVE_STATUSES, ApiError, errorMessage, unwrap } from "@bhojango/api-client";
export type { CoreSchemas, OrderStatus } from "@bhojango/api-client";

// Round 4: languages, the current country (Markets), formatting by the country's
// locale, and the test-site banner. See src/i18n.tsx for how a screen uses them.
export { I18nProvider, LANGUAGES, useCountry, useI18n, useKnownCountry, useLocaleStore } from "./i18n";
export type { CountryContext, I18n, Language, Translate } from "./i18n";
export { convertDistance, countryForCurrency, deviceLocale, e164, findCity, formatDate, formatMoney, formatNumber, formatTime, localeForCurrency,
  liveCityNames, regionOf, resolveCountry } from "./locale";
export type { CountrySource, MarketCountry } from "./locale";
export { appEnv, isTestEnvironment, resolveAppEnv } from "./env";
export type { AppEnv } from "./env";
export { CountryPicker, LanguagePicker, PhoneCountryButton, TestBanner, WithTestBanner } from "./ui/locale";
export type { Tone } from "./ui/locale";
