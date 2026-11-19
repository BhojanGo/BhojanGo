# App store readiness

Status on 2026-11-19: nothing is bought and no store accounts exist. These pages
prepare the three Expo apps for Apple App Store and Google Play review.

| App | Expo app | iOS bundle id / Android package | Page |
|---|---|---|---|
| BhojanGo (customers) | `apps/customer` | `com.bhojango.app` | [customer.md](customer.md) |
| BhojanGo Kitchen (kitchens, tablet and phone) | `apps/partner` | `com.bhojango.partner` | [kitchen.md](kitchen.md) |
| BhojanGo Delivery (riders) | `apps/rider` | `com.bhojango.rider` | [delivery.md](delivery.md) |

Also here:

- [screenshots.md](screenshots.md): sizes each store wants and the screens to capture.
- `tools/mobile/store_shots.sh`: captures screenshots from an Android emulator and
  sizes them for both stores.

Placeholders are written as `{LIKE_THIS}`. Fill them in when the accounts and
pages exist. Do not guess them.

| Placeholder | What it is |
|---|---|
| `{SUPPORT_URL}` | Public support page (both stores require one) |
| `{PRIVACY_URL}` | Public privacy policy, per country if needed |
| `{TERMS_URL}` | Terms of use |
| `{DELETE_ACCOUNT_URL}` | Public page that explains how to delete an account (Google Play requires a web link) |
| `{MARKETING_URL}` | Optional, App Store only |
| `{SUPPORT_EMAIL}` | Contact email shown on the listing |
| `{REVIEW_*}` | Reviewer test accounts (see "Reviewer access" below) |
| `{MIN_AGE}` | Minimum age for a customer account, as stated in the Terms |

## Accounts needed before any of this (not bought yet)

- Apple Developer Program, as an organisation (DeepTrics LLC). Needs a D-U-N-S number.
- Google Play Console, as an organisation. A personal Play account created now must
  run a closed test with at least 12 testers for 14 days before it can publish; an
  organisation account does not. Organisation sign-up also needs a D-U-N-S number.
- An Expo/EAS project per app. `extra.eas.projectId` is still `your-eas-project-id`
  in all three `app.json` files (`apps/*/app.json`, `extra.eas`).
- Production web pages for `{SUPPORT_URL}`, `{PRIVACY_URL}`, `{TERMS_URL}` and
  `{DELETE_ACCOUNT_URL}`.

Decide which legal entity publishes. One developer account per store can hold all
three apps. If India listings must be published by DeepTrics Software Solutions Pvt
Ltd, that is a second account per store.

## Likely review problems

Ordered by how likely each one is to stop a release. Each item gives the evidence,
the store rule, and the fix. None of these fixes has been made.

### 1. Kitchen and Delivery apps have no in-app account deletion (Apple: blocker)

- Evidence: only the customer app calls the delete endpoint
  (`apps/customer/app/account/privacy.tsx:52`, `packages/mobile-core/src/session.ts:129-131`).
  The Kitchen app's settings screen has sign-out only
  (`apps/partner/app/(kitchen)/help.tsx:35`). The Delivery app's Account tab has
  sign-out only (`apps/rider/app/(tabs)/account.tsx:49`).
- Accounts are created inside both apps: `apps/partner/app/join.tsx` and
  `apps/partner/app/apply.tsx` (kitchen application), `apps/rider/app/join.tsx`
  (rider sign-up). Apple guideline 5.1.1(v) then requires deletion inside the app.
- The backend endpoint exists: `DELETE /api/v1/users/me`
  (`backend/core_api/modules/identity/api/v1/users.py:64`), implemented in
  `backend/core_api/modules/identity/service/auth.py:258`.
- Fix: add "Delete account" with a confirmation sheet to both apps, reusing
  `useSession().deleteAccount`. In the Delivery app call `stopTracking()` first.
  For a kitchen owner, the server should also pause the kitchen's listing (or say
  that the kitchen is closed by support) so a deleted owner's kitchen does not keep
  taking orders.
- Related server gap: `delete_account` removes `RiderProfile` (date of birth,
  vehicle) but not `rider_documents` rows or the stored licence and insurance
  images (`auth.py:281`; model `backend/core_api/modules/identity/models/rider.py:11`).
  The user row is updated, not deleted, so the `ON DELETE CASCADE` never fires.
  Delete those rows and their stored files, or record why they are kept and for
  how long, and say so in the privacy policy and on the Data safety form.

### 2. Background location in the Delivery app (Google: declaration, disclosure and video; Apple: wording)

- Evidence: `ACCESS_BACKGROUND_LOCATION`, `FOREGROUND_SERVICE` and
  `FOREGROUND_SERVICE_LOCATION` (`apps/rider/app.json:34-36`);
  `UIBackgroundModes: ["location"]` (`apps/rider/app.json:18`);
  `isAndroidBackgroundLocationEnabled` and `isAndroidForegroundServiceEnabled`
  (`apps/rider/app.json:52-53`). The app asks for "while using" when the rider goes
  online (`apps/rider/lib/location.ts:56-59`), then shows a banner on the Drive tab
  that asks for "all the time" (`apps/rider/app/(tabs)/drive.tsx:196-199`,
  `apps/rider/lib/location.ts:67-74`). With background access it runs a foreground
  service task (`apps/rider/lib/location.ts:104-116`) and stops when the rider goes
  offline (`apps/rider/lib/location.ts:127-134`). That design is sound.
- Google Play needs all of these:
  1. A prominent in-app disclosure **before** the system prompt. The current banner
     text (`packages/i18n/messages/en.json:1152-1153`: "Keep offers coming with the
     screen off." / "Allow location 'all the time'; you can turn it off by going
     offline.") does not say that location is collected when the app is closed or
     not in use. Google expects words close to: "BhojanGo Delivery collects location
     data to offer you nearby deliveries and to show customers where their order is,
     even when the app is closed or not in use, while you are online." Show it as a
     dialog with "Allow" and "No thanks" buttons; "Allow" then opens the system
     prompt.
  2. The Permissions Declaration form for background location in Play Console, with
     a short video (unlisted link) that shows the disclosure, the prompt, and the
     feature working with the screen off.
  3. The foreground service declaration for `FOREGROUND_SERVICE_LOCATION`
     (Android 14 and later), also with a video.
  4. The listing's description must mention the background location use
     (see `delivery.md`).
- Expect Google to ask whether a foreground service alone is enough. On Android 10
  and later, a foreground service of type `location` started while the app is
  visible can keep getting location without `ACCESS_BACKGROUND_LOCATION`. The code
  only starts the service after "all the time" is granted
  (`apps/rider/lib/location.ts:101-118`). If the declaration is refused, the fall-back
  is to start the foreground service when the rider goes online and drop
  `ACCESS_BACKGROUND_LOCATION`; test whether `expo-location`'s
  `startLocationUpdatesAsync` allows that on the target Expo SDK.
- Apple: background location for a delivery app is accepted under 2.5.4, but the
  purpose strings must be specific. Two different "Always" texts are set: one in
  `ios.infoPlist` (`apps/rider/app.json:17`, "shares your location during an active
  delivery") and one in the `expo-location` plugin (`apps/rider/app.json:51`). The
  plugin's text wins at prebuild. The plugin also writes
  `NSLocationAlwaysUsageDescription` with Expo's generic default ("Allow $(PRODUCT_NAME)
  to access your location") because `locationAlwaysPermission` is not set. Generic
  strings are a common 5.1.1 rejection. Set `locationAlwaysPermission` and
  `locationWhenInUsePermission` in the plugin and remove the duplicates in
  `ios.infoPlist`. Check the final strings in the prebuilt `Info.plist`.

### 3. Store builds have no production configuration (Apple 2.1 and Play: app does not work)

- Evidence: there is no `eas.json` in the repo. The API addresses fall back to
  `http://localhost:8001` and `http://localhost:8004`
  (`packages/mobile-core/src/session.ts:15-19`), and the web address used for the
  Terms and Privacy links falls back to `http://localhost:3000`
  (`apps/customer/lib/plate.tsx:20`, used by `apps/customer/app/sign-in.tsx:15-17`).
  A release build without the variables opens on "can't reach BhojanGo" and its
  privacy link goes nowhere.
- The "Test site" banner: `resolveAppEnv` returns `production` for a release build
  that sets nothing (`packages/mobile-core/src/env.ts:15-19`), and the banner only
  shows outside production (`packages/mobile-core/src/ui/locale.tsx:193-195`). Good.
  The risk is a local release build on a machine where
  `tools/mobile/env-profile.sh qa` has written `apps/<app>/.env.local` with
  `EXPO_PUBLIC_APP_ENV=qa`: Expo reads `.env.local` when it bundles, so that build
  ships with the banner and the QA addresses. EAS cloud builds skip git-ignored
  files, so `.env.local` is not uploaded there.
- Fix: add `eas.json` with a `production` profile that sets
  `EXPO_PUBLIC_APP_ENV=production` and the production `EXPO_PUBLIC_CORE_URL`,
  `EXPO_PUBLIC_REALTIME_URL` and `EXPO_PUBLIC_WEB_URL` (all `https://`). Add a
  build-time check (for example in each `app.config.js`) that fails a production
  build when `EXPO_PUBLIC_APP_ENV` is not `production` or any URL is `http://` or
  `localhost`. Build store binaries on EAS, not from a working copy with `.env.local`.

### 4. Checkout can show a "Pay (test mode)" sheet in production (Apple 2.1, Play broken functionality)

- Evidence: the bag opens the app's own test sheet for every provider that is not
  Stripe (`apps/customer/app/bag.tsx:252`), and it treats a failed provider lookup
  as the fake provider (`apps/customer/app/bag.tsx:56`). The sheet's title is
  "Pay (test mode)" (`packages/i18n/messages/en.json:432`). In production the fake
  endpoints answer 404 (`backend/core_api/modules/payments/api/v1/payments.py:325-341`).
  So in India (server provider `razorpay`, which has no in-app checkout yet), or after
  a network error, a reviewer sees a test payment screen that then fails.
- Fix: show the test sheet only when `isTestEnvironment(appEnv())`. In production,
  a non-Stripe provider or a failed lookup should show "Payments aren't available
  here yet" with Retry. Either add Razorpay Checkout to the app before listing in
  India, or publish the first release only in the United States (Boise) and add
  India later.
- Payments themselves are fine: food delivery is a physical good and service, so
  card payment through Stripe (and Razorpay later) is allowed and in-app purchase
  is not required (Apple 3.1.3(e) and 3.1.5(a); Google Play Payments policy excludes
  physical goods). Tips to the delivery partner are for a real-world service and
  fall under the same rule. Say this in the review notes so the reviewer does not
  ask. Apple Pay is not configured (`apps/customer/lib/stripeSheet.ts:43`,
  `apps/customer/test/stripeSheet.test.ts:26`); Google Pay is enabled in the Stripe
  plugin (`apps/customer/app.json:53`).

### 5. Reviewers cannot receive the sign-in code (both stores: "unable to sign in")

- Sign-in is phone + SMS code or email (password, email code, or new account)
  (`apps/customer/app/sign-in.tsx:1-2`, shared `EmailSignIn` in
  `packages/mobile-core/src/ui/signin.tsx:96`). The Kitchen and Delivery apps use the
  same two ways (`apps/partner/app/sign-in.tsx:67-70`, `apps/rider/app/sign-in.tsx:74-77`).
- The fixed test codes are switched off in production for phones
  (`backend/core_api/modules/identity/service/otp.py:52-57`) and email
  (`backend/core_api/modules/identity/service/email_codes.py:28-34`). That is right,
  but it means a reviewer can only sign in with **email and password**.
- Fix: create reviewer accounts in production that sign in with email and password,
  and enter them in App Store Connect (App Review Information) and Play Console
  (App access). See "Reviewer access" below.

### 6. Purpose strings that are generic, wrong or unused (Apple 5.1.1)

- Customer: `NSLocationAlwaysAndWhenInUseUsageDescription` says "for real-time
  delivery tracking" (`apps/customer/app.json:17`), but the app only asks for
  "while using" (`apps/customer/lib/where.ts:49`, `apps/customer/lib/account.ts:205`)
  and tracking uses the rider's position, not the customer's. Make the text accurate
  ("only while you use the app, to find kitchens and set your delivery address") or
  leave it out if the `expo-location` plugin allows. The plugin is added without
  options (`apps/customer/app.json:39`), so it also writes Expo's generic
  `NSLocationAlwaysUsageDescription`. Set the plugin's strings explicitly.
- Microphone: the `expo-image-picker` plugin (all three apps) and the `expo-audio`
  plugin (Kitchen, `apps/partner/app.json:40`) add a microphone usage string and,
  on Android, `RECORD_AUDIO` unless told not to. No app records audio or video
  (the Kitchen app only plays a sound: `apps/partner/lib/board.ts:51`). Set
  `microphonePermission: false` on `expo-image-picker`, and
  `microphonePermission: false` / `recordAudioAndroid: false` on `expo-audio`.
  Confirm after `expo prebuild` that no `NSMicrophoneUsageDescription` or
  `RECORD_AUDIO` remains.
- Android photo permissions: check the merged manifest after prebuild for
  `READ_MEDIA_IMAGES` / `READ_MEDIA_VIDEO`. Google's Photo and Video Permissions
  policy only allows them for apps whose core use is photos. The apps only pick one
  image at a time, which the system photo picker covers. Block them with
  `android.blockedPermissions` if a plugin adds them.
- Kitchen `WAKE_LOCK` (`apps/partner/app.json:31`) is not needed for
  `useKeepAwake` (`apps/partner/app/_layout.tsx:15`), which keeps the screen on with a
  window flag. Harmless, but can be removed.

### 7. Push notifications are declared but never registered

- Evidence: `expo-notifications` is configured in the customer and Delivery apps
  (`apps/customer/app/_layout.tsx:15`, `apps/rider/app/_layout.tsx:15`) and in the
  Kitchen app's plugin list (`apps/partner/app.json`), but no app calls
  `requestPermissionsAsync` or `getExpoPushTokenAsync` / `getDevicePushTokenAsync`.
  The server has a token field (`fcm_token`, cleared in `auth.py:272`) that nothing
  fills. The customer app still shows "push" switches
  (`apps/customer/lib/account.ts:43`).
- Not a rejection by itself, but: on Android 13 and later the rider's "You're
  online" foreground-service notification is hidden until notification permission
  is granted, and a reviewer who turns on "push" sees nothing arrive.
- Fix: either register for push (ask for permission at a moment that explains why,
  send the token to the server) before release, or hide the push switches. Update
  the privacy answers ("Device ID") if tokens are added.

### 8. Privacy policy link inside the Kitchen and Delivery apps (Apple 5.1.1(i))

- The customer sign-in screen links to Terms and Privacy
  (`apps/customer/app/sign-in.tsx:95-101`). The Kitchen and Delivery apps have no
  link to the privacy policy anywhere (no match for "privacy" in `apps/partner/app`
  or `apps/rider/app`). Apple needs the policy reachable in the app as well as on
  the listing.
- Fix: add Terms and Privacy links to both sign-in screens and to the settings /
  Account screens. Also add them to the customer Account tab.

### 9. User-generated content: quick messages (Apple 1.2), photos, ratings

- Customers and riders exchange preset messages and free text up to 140 characters
  while an order is active (`backend/core_api/modules/orders/api/v1/messages.py:1-8`,
  `:38-45`; UI `packages/mobile-core/src/chat.tsx`). Phone-like digits are masked and
  the conversation closes when the order ends. There is no "report" or "block" in the
  chat.
- Apple 1.2 asks apps with user content for a filter, a way to report, a way to
  block, and contact details. A chat limited to one live order is lower risk, but
  reviewers do ask. Fix: add "Report" in the chat sheet that opens a support ticket
  with the conversation attached, and say in the review notes how chat is limited.
- Ratings: customers leave stars and a comment
  (`apps/customer/lib/account-rating.tsx`). Comments are shown only to the kitchen,
  without the customer's name (`apps/partner/lib/ratings.tsx:4`). Customers see only
  the star average (`apps/customer/app/restaurant/[id].tsx:51`). Not public user
  content.
- Photos: report-a-problem photos (customer) and delivery proof (rider) go to
  BhojanGo only. Dish photos from kitchens (`apps/partner/app/(kitchen)/menu.tsx:272-278`)
  are public; make sure admins can remove one.

### 10. Minimum age and content rating

- Riders: the minimum age comes from the country's rules and is checked on sign-up
  (`apps/rider/app/join.tsx:3-4`, `:54-56`; server `RiderApply.date_of_birth` in
  `backend/core_api/modules/identity/api/v1/signup.py:37-45`).
- Customers: no age gate. No alcohol or age-restricted goods were found in the
  catalogue code. State the minimum age (`{MIN_AGE}`) in the Terms. If alcohol is
  ever sold, the age rating, an age check and per-country legal review are needed.
- Rating questionnaires: answer "no" to violence, sexual content, gambling and so
  on. Answer "yes" to messaging between users (quick messages) and, for Google, to
  "users can interact" and "shares location" (Delivery app; customer delivery
  address goes to the rider). Expect Apple 4+ (or the next tier if the messaging
  answer raises it) and IARC "Everyone" / PEGI 3 / equivalent.

### 11. Smaller items

- Hidden component gallery: `bhojango://gallery` opens a design screen with a
  "Language and test site" section in every build (`apps/customer/app/gallery.tsx:1-2`,
  `:93`). Guard it with `isTestEnvironment` or remove it from release builds.
- Report a problem asks for the camera first and silently falls back to the photo
  library if camera access is refused (`apps/customer/app/report/[id].tsx:36-39`).
  Allowed, but a choice ("Take photo" / "Choose photo") is clearer to reviewers.
- Map tiles come from OpenFreeMap with OpenStreetMap data
  (`apps/customer/components/LiveMap.tsx:2`, `:22`). Keep the attribution visible.
  The tile server sees the phone's IP address and map area; mention it in the
  privacy policy.
- Export compliance: the apps use only HTTPS. Set
  `ios.config.usesNonExemptEncryption: false` so each upload does not ask.
- Apple privacy manifest: Expo modules ship their own `PrivacyInfo.xcprivacy`.
  Check the build's merged manifest in Xcode/EAS output; add `ios.privacyManifests`
  in `app.json` if Apple's upload email lists missing required-reason APIs.
- Sign in with Apple is **not** required: no app offers Google or another
  third-party sign-in (no Google/Apple sign-in code in `apps/customer`,
  `apps/partner`, `apps/rider` or `packages/mobile-core`). The server has
  `google_id` / `apple_id` fields (`auth.py:270-271`) for the website. If Google
  sign-in is ever added to an iOS app, Sign in with Apple (or an equivalent private
  option) must be added too (Apple 4.8).
- No tracking: no analytics, advertising or crash SDK is in any app (no Sentry,
  Firebase Analytics, Amplitude and so on). Sentry exists only on the server and only
  if `SENTRY_DSN` is set (`backend/shared/config.py:309`). No App Tracking
  Transparency prompt is needed.
- Kitchen and Delivery are apps for workers. Apple sometimes asks whether such apps
  should be "Unlisted". Both allow public sign-up from the app, so a public listing
  is fine; say so in the review notes.

## Reviewer access

Create these in **production** before submitting. They sign in with email and
password (codes are not sent to reviewers). Record them only in the store consoles
and the team's password manager, not in this repo.

| Account | For | Needs |
|---|---|---|
| `{REVIEW_CUSTOMER_EMAIL}` | BhojanGo | A saved address inside the Boise delivery zone, so the reviewer sees kitchens and the bag even when testing from outside Idaho. Mention the "Change city" browse option. |
| `{REVIEW_KITCHEN_EMAIL}` | BhojanGo Kitchen | Linked to an approved kitchen that real customers cannot order from (paused or in a hidden test zone), with a few menu items and photos, and some past orders and ratings. |
| `{REVIEW_RIDER_EMAIL}` | BhojanGo Delivery | An approved rider (documents done) in Boise, with some past deliveries and earnings. |

Review notes to paste (adapt per app):

> BhojanGo is a food delivery service. It delivers only inside its live cities
> (currently Boise, Idaho, United States). Sign in with the email and password above
> ("Email" tab, then "Password"). Payments are for food and delivery (physical goods
> and services) and go through Stripe; tips go to the delivery partner for a
> real-world service. No digital goods are sold. Quick messages between a customer
> and their rider are open only while an order is on its way; numbers are masked and
> the chat closes when the order is delivered. Accounts can be deleted in the app:
> {WHERE_IN_APP}.

For the Delivery app add a short screen recording link showing going online, the
location disclosure and an offer, because a reviewer cannot receive a real order.

## Checklist before the first submission

- [ ] Fix items 1 to 4 above (deletion, rider location disclosure, production build
      profile, test payment sheet).
- [ ] Decide item 7 (push) and item 9 (report in chat).
- [ ] Pages live: `{SUPPORT_URL}`, `{PRIVACY_URL}`, `{TERMS_URL}`, `{DELETE_ACCOUNT_URL}`.
- [ ] Reviewer accounts created in production.
- [ ] `expo prebuild` per app; read the generated `Info.plist` and merged
      `AndroidManifest.xml` and compare with the permission tables in the app pages.
- [ ] Screenshots from a **production** build (no test banner), per `screenshots.md`.
- [ ] Privacy answers copied from the app pages into App Store Connect and Play
      Console. Re-check them after any change that adds an SDK or a new field.
