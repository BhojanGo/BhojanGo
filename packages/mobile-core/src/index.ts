// Shared by the Expo apps (customer, rider; partner from P19).

// Design system (P16): tokens, fonts and components; same tokens as @bhojango/ui on the web.
export * from "./ui/components";
export { fontScale, loadScriptFonts, useBrandFonts } from "./ui/fonts";
export { color, dark, displayFont, elevation, radius, space, textFont, touch } from "./ui/theme";
// Round 8: the fluid type scale (the only font sizes), language-aware faces, tabular figures, the dev font audit.
export { DENSE_FONT_SCALE, face, field, FLUID, fontAuditEnabled, MIN_READABLE, num, scriptFor, setAuditRoute, setTypeWidth, sizeAt,
  textStyles, type, TYPE_RANGES, TYPE_ROLES, TYPE_SCALE, typeScript, typeStyleFor, typeWidth } from "./ui/type";
export type { Script, TypeRole } from "./ui/type";
export { FontAudit } from "./ui/font-audit";
export { billTotal, receiptRefunds } from "@bhojango/ui/bill";
export { reorderToBag } from "@bhojango/ui/reorder";
// R24: what a kitchen statement below zero says (this week; still from earlier weeks), shared with admin.
export { belowZeroLines, type BelowZeroLine } from "@bhojango/ui/statement";
// Round 5: the floating tab bar's geometry and the room every tab screen leaves for it.
export { aboveTabBar, sceneEndSpace, TAB_BAR_BREATHING, TAB_BAR_GAP, TAB_BAR_HEIGHT, TAB_BAR_INSET_GAP, TAB_BAR_LIFT, tabBarBottom, tabBarClearance,
  tabBarZone } from "./tabbar";

// P17: generated API client, session and bag.
export { AdminAccountError, api, beforeSignOut, emailAuth, liveSocket, urls, useSession, wsHeaders, wsUrl } from "./session";
// R19: push notifications (Expo push tokens registered with core_api after sign-in, removed on sign-out).
export { registerPush, unregisterPush, usePushRegistration, type PushChannel, type PushModule } from "./push";
export { easProjectId, pushPlatform } from "./push-config";
// Round 8 (D5): Phone and Email as equal ways in; email + password, email codes, forgot password.
export { authErrorText, codeSendErrorText, EmailSignIn, SignInWays, waitText } from "./ui/signin";
export type { Way as SignInWay } from "./ui/signin";
export type { User } from "./session";
// R9: every GET gives up after 8 s; screens show LoadError (title, why, Retry) when their load fails.
export { createFirstLoad, FIRST_LOAD_TIMEOUT_MS, loadFailure, RequestTimeoutError, timeoutFetch } from "./load";
export type { LoadFailure, LoadState } from "./load";
// R27: a session refresh never hangs (the kitchen board's silent stall).
export { REFRESH_TIMEOUT_MS, RefreshTimeoutError, singleFlight } from "./refresh";
export { LoadError, loadErrorText, UnreachableScreen, useFirstLoad } from "./ui/load-error";
export type { LoadErrorProps } from "./ui/load-error";
export { cartItems, defaultPicks, useBag } from "./bag";
// B2: quick messages between the customer and the rider during an order.
export { QuickChat, useQuickMessages } from "./chat";
// R19: Account -> Legal and Delete account in the Kitchen and Delivery apps.
export { DeleteAccount, LegalLinks, legalUrl, SignInLegal } from "./account";
export { deleteAccountProblem, legalPageUrl } from "./account-text";
export type { AccountTone } from "./account";
export type { BagLine, OptionGroup, Pick } from "./bag";
export { ACTIVE_STATUSES, ApiError, errorMessage, quoteRefusal, unwrap, type QuoteRefusal } from "@bhojango/api-client";
export type { CoreSchemas, OrderStatus } from "@bhojango/api-client";

// Round 4: languages, the current country (Markets), formatting by the country's
// locale, and the test-site banner. See src/i18n.tsx for how a screen uses them.
export { I18nProvider, LANGUAGES, useCountry, useI18n, useKnownCountry, useLocaleStore, type LocaleRule } from "./i18n";
export type { CountryContext, I18n, Language, Translate } from "./i18n";
export { convertDistance, countryForCurrency, deviceLocale, e164, findCity, formatDate, formatMoney, formatNumber, formatTime, localeForCurrency,
  cityRegionCode, filterCities, hourIn, inZone, liveCityNames, partnerCountry, partnerLanguage, regionOf, resolveCountry } from "./locale";
export type { CountrySource, MarketCountry } from "./locale";
export { appEnv, isTestEnvironment, resolveAppEnv } from "./env";
export type { AppEnv } from "./env";
// Round 6: the header's language pill (globe + "EN"); no country selector. The pure
// helpers are @bhojango/i18n's, shared with the website.
export { chooseLanguage, detectCountry, formatPhone, languageList } from "@bhojango/i18n";
export { LanguagePicker, LanguagePill, PhoneCountryButton, TestBanner, WithTestBanner } from "./ui/locale";
export type { Tone } from "./ui/locale";
// R8: the screens' SafeAreaView (follows the test banner's insets; the native one padded the status bar twice).
export { SafeAreaView, type SafeAreaEdge } from "./ui/safe-area";
// R10: payout set-up (Stripe Connect Express and the rest): the Payouts screens' words and button.
export { payoutCopy, providerName, repayDay, STATEMENT_NOTES, STATEMENT_STATUSES, weekLabel, weekStatus, type WeekStatus } from "./payouts";
export type { PayoutAccount, PayoutCopy, PayoutSetup, PayoutState } from "./payouts";
