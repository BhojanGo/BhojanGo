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
the store rule, and the fix. Round 19 (2026-11-19) fixed items 1, 2 (in the app),
5, 6 (purpose strings and microphone), 8 (Kitchen and Delivery) and 9 (quick
messages); each says so in a **Status** line. The rest is still open.

### 1. Kitchen and Delivery apps have no in-app account deletion (Apple: blocker)

**Status (R19): fixed.** BhojanGo Kitchen: Help and settings > "Account and legal" >
"Delete my account" (`apps/partner/app/account.tsx`, also linked from the application
screen). BhojanGo Delivery: Account tab > "Delete account"
(`apps/rider/app/(tabs)/account.tsx`), which stops location sharing first. Both use the
shared confirmation sheet (`packages/mobile-core/src/account.tsx`) with the customer
app's wording rules. Server (`delete_account`, `identity/service/auth.py`): a delivery
partner's `rider_documents` rows and their stored licence and insurance photos are
deleted; a kitchen owner's kitchens close at once and leave every listing
(`paused_reason` `owner_deleted`); deletion waits with HTTP 409 `MONEY_OWED` (the app
shows the amount) while a payout statement is unpaid, or `ORDERS_IN_PROGRESS`. The
customer app has no such wait: customers are never owed payouts. An admin's erasure
request skips the wait (support settles any payout by hand). Update the privacy
policy and Data safety answers to say documents are deleted with the account.

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

**Status (R19): fixed in the app; the Play Console forms and the video are still to
do.** The prominent disclosure (`apps/rider/lib/disclosure.tsx`, keys
`rider.location.*`) shows right after going online (once per app run, and from the
Drive tab banner) before the system prompt, with "Allow" and "No thanks". Background
location is asked for and used only while online; the task also stops when the server
says the partner is offline. The `expo-location` plugin now sets all three iOS strings
and the `infoPlist` copies are gone. Declaration texts and the video shot list:
[play-location-declaration.md](play-location-declaration.md).

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

**Status (R19): fixed** by `tools/review_accounts.py` (email and password accounts in a
hidden review city; see "Reviewer access"). Run it in production at go-live.

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

**Status (R19): purpose strings and microphone fixed.** Customer: the "always" location
keys are gone (plugin options `false`) and the when-in-use text is accurate. Delivery:
see item 2. Microphone: `microphonePermission: false` on `expo-image-picker` in all
three apps, and `microphonePermission: false` / `recordAudioAndroid: false` on
`expo-audio` in the Kitchen app. Still to check after `expo prebuild`: no
`NSMicrophoneUsageDescription` or `RECORD_AUDIO`, the photo permissions below, and
`WAKE_LOCK`. Also note `expo-audio` still adds `UIBackgroundModes: audio` by default
(`enableBackgroundPlayback`); the Kitchen app plays its alert only in the foreground,
so consider `enableBackgroundPlayback: false` before submitting (Apple 2.5.4).

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

**Status (R19): fixed for Kitchen and Delivery.** Privacy policy and Terms of use open the
account country's pages on the website (`/privacy?country=XX`, `/terms?country=XX`,
base `EXPO_PUBLIC_WEB_URL`): Kitchen: Help and settings > "Account and legal";
Delivery: Account tab > "Legal". Still open: links on the Kitchen and Delivery sign-in
screens and on the customer Account tab, and `EXPO_PUBLIC_WEB_URL` in the production
build profile (item 3).

- The customer sign-in screen links to Terms and Privacy
  (`apps/customer/app/sign-in.tsx:95-101`). The Kitchen and Delivery apps have no
  link to the privacy policy anywhere (no match for "privacy" in `apps/partner/app`
  or `apps/rider/app`). Apple needs the policy reachable in the app as well as on
  the listing.
- Fix: add Terms and Privacy links to both sign-in screens and to the settings /
  Account screens. Also add them to the customer Account tab.

### 9. User-generated content: quick messages (Apple 1.2), photos, ratings

**Status (R19): report and block fixed.** In the quick messages sheet (customer and
Delivery apps; the Kitchen app has no chat): press and hold a message, or tap "Report",
to report it with a reason (a `chat_report` ticket in the admin support queue with the
conversation), and "Block" in the header (per pair of people: the blocker no longer
receives that person's messages or pushes). Dish photo removal by admins is not checked.

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

Reviewers sign in with **email and password** (sign-in codes are not sent to them).
The accounts are made by one command, run **once, in production, at go-live**
(it may also be tried on a dev stack; it refuses on QA):

```sh
# inside the production core-api container (Railway: the core-api service's shell)
python tools/review_accounts.py --email-domain <a domain the team owns>
# options: --country US (default) --region US-ID --code US-ID-REV
#          --centre LAT,LNG (open sea; required outside the US) --postal-code 83702
```

It creates, in one transaction (`backend/tools/review_accounts.py`):

| Account | App | What it has |
|---|---|---|
| `review.customer@<domain>` | BhojanGo | A customer with a saved "Home" address inside the review zone, so the home screen shows the review kitchen wherever the reviewer is. |
| `review.kitchen@<domain>` | BhojanGo Kitchen | The owner of "BhojanGo Review Kitchen": approved, open around the clock, with a small menu (mains, breads, drinks). |
| `review.delivery@<domain>` | BhojanGo Delivery | An approved delivery partner: phone step, licence, insurance and background check marked done (no document images are stored). |

- **The review zone is hidden.** The command adds a city "App Review" (code
  `<region>-REV`) whose only zone is a square of open sea, about 11 km across (for
  the US: the North Pacific around 30N 140W, far from any coast), so no real address
  is ever inside it. The city's Markets settings say `review_only: true` and list the
  three account ids in `review_accounts` (`core_api/modules/markets/service/review.py`).
  Everyone else never sees it: it is left out of the city lists, the website's
  directory and city pages, the address search, locate and discover, and the public
  kitchen lists; the review kitchen's page and menu answer 404 to anyone but the
  review accounts. Pricing refuses everyone else there too (R20), so nobody else can
  order in the review city.
- **Passwords** are random and printed **once** at the end. Copy them straight into
  App Store Connect, Play Console and the team's password manager; they are not
  written to a file or the logs, and never go in this repo.
- **Idempotent by refusing**: if the review city or any of the three emails already
  exists, it changes nothing and exits with an error. To start over, delete those rows.
- After running it, sign in once with each account on a production build and check:
  the customer sees "BhojanGo Review Kitchen" and can price a cart (if sales tax needs
  a real postal code, rerun on a fresh database with `--postal-code`), the kitchen app
  opens the kitchen, the Delivery app shows the partner as ready to go online.
- No delivery partner is ever near the zone, so an order placed there is not offered
  to anyone real, and the review delivery partner gets no offers. That is why the
  Delivery app's notes point to a screen recording.

### A reviewer's order, end to end (R20)

A reviewer can place a real order in the customer app and watch it arrive, without
paying and without anyone working the review kitchen:

- **It costs $0.00, and no card is charged.** In the review city only, and only for
  the review customer, the bag shows the usual fair bill (food, delivery fee, fees,
  tip) and then one more line, "App review: no charge", paid by BhojanGo, so "You
  pay" is $0.00 (pricing engine `review`, `core_api/modules/pricing/service/engine.py`).
  The button reads "Place order" instead of "Pay $0.00" and no payment sheet opens:
  the server places the order as it is made, with a zero payment of its own (provider
  `review`); Stripe (payments and Stripe Tax) is never called. Any other account, or
  the review customer in any other city, prices and pays as usual; everyone else is
  refused a price in the review city. Review orders never appear on payout statements.
- **The order moves on its own.** The worker's review simulator (`REVIEW_SIM=1`,
  `backend/worker/app/demo_sim/review.py`) plays the review kitchen and the review
  delivery partner: about 20 seconds after the order is placed the kitchen accepts and
  starts cooking, and "Review Delivery" is assigned; 2 minutes later the food is ready,
  45 seconds later it is picked up, and 3 minutes later it is delivered (about 6
  minutes in all). The customer app shows each step (order screen, push messages); the
  map has no moving delivery partner, as nobody sends a location. It touches only
  orders of a review-only city whose customer and kitchen owner are both its review
  accounts, and core_api's step endpoint (`/internal/review/orders/{id}/step`, signed)
  refuses every other order. The demo rider simulator (`DEMO_RIDER_SIM`) is still
  refused in production.
- **Turn it on and off.** `REVIEW_SIM` on the production worker is `"0"` in
  `.railway/railway.ts`. Set it to `"1"` there and apply before you submit a build
  (each new version of an app is reviewed again, so on for every submission), and back
  to `"0"` once the stores have approved it. With it off, a review order still costs
  nothing, but nobody accepts it: the kitchen's accept timeout cancels it after 3
  minutes. See [go-live.md](../go-live.md).

### App Store Connect "App Review Information" / Play Console "App access"

Choose "All or some functionality is restricted" (Play) and enter the email and
password of that app's account. Notes per app:

**BhojanGo** (`review.customer@<domain>`)

> BhojanGo is a food delivery service. It delivers only inside its live cities.
> Sign in with the email and password above ("Email" tab, then "Password"). This
> account has a saved address in a test area with one test kitchen, "BhojanGo Review
> Kitchen", so you can browse its menu, add dishes to the bag and place an order from
> anywhere. Orders from this account cost $0.00 and no card is charged; the test
> kitchen and a test delivery partner then take the order through to delivered in
> about six minutes, so you can follow it in the app. Payments are for food and
> delivery (physical goods and services) and go through Stripe; tips go to the
> delivery partner for a real-world service. No digital goods are sold. Quick
> messages between a customer and their delivery partner are open only while an
> order is on its way; numbers are masked, a message can be reported or the person
> blocked, and the chat closes when the order is delivered. The account can be
> deleted in the app: Account, Privacy and your data, Delete my account.

**BhojanGo Kitchen** (`review.kitchen@<domain>`)

> BhojanGo Kitchen is the app restaurants use to take BhojanGo orders, run on a
> tablet or phone in the kitchen. Sign in with the email and password above ("Email"
> tab, then "Password"). The account owns a test kitchen that real customers cannot
> see. You can open and close the kitchen, pause orders, edit the menu (dish names,
> prices, photos, sold out), see payouts and ask support for a call back. Kitchens
> sign up in the app; it is a public listing for restaurant partners. The account can
> be deleted in the app: Help and settings, Account and legal, Delete my account.

**BhojanGo Delivery** (`review.delivery@<domain>`)

> BhojanGo Delivery is the app delivery partners use to receive and deliver
> BhojanGo orders. Sign in with the email and password above ("Email" tab, then
> "Password"). The account is an approved delivery partner. Delivery offers depend
> on real orders near the partner, so a reviewer will not receive one; this video
> shows going online, the location disclosure, an offer and a delivery: {VIDEO_URL}.
> Location is used only while the partner is online (on shift), including in the
> background with a visible notification, to offer nearby deliveries and show
> customers where their order is; going offline stops it. Delivery partners sign up
> in the app; it is a public listing. The account can be deleted in the app:
> Account, Delete account, Delete my account.

## Checklist before the first submission

- [x] Item 1 (in-app deletion) and item 2 in the app (disclosure, strings): round 19.
- [ ] Item 2 in Play Console: both declarations and the video
      ([play-location-declaration.md](play-location-declaration.md)).
- [ ] Fix items 3 and 4 (production build profile, test payment sheet).
- [ ] Decide item 7 (push). Item 9 (report and block in chat): done in round 19.
- [ ] Pages live: `{SUPPORT_URL}`, `{PRIVACY_URL}`, `{TERMS_URL}`, `{DELETE_ACCOUNT_URL}`.
- [ ] Reviewer accounts created in production.
- [ ] `REVIEW_SIM` on for the production worker while a build is in review; place one
      review order on a production build and see it delivered; off after approval.
- [ ] `expo prebuild` per app; read the generated `Info.plist` and merged
      `AndroidManifest.xml` and compare with the permission tables in the app pages.
- [ ] Screenshots from a **production** build (no test banner), per `screenshots.md`.
- [ ] Privacy answers copied from the app pages into App Store Connect and Play
      Console. Re-check them after any change that adds an SDK or a new field.
