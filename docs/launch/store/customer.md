# BhojanGo (customer app)

`apps/customer`. iOS bundle id and Android package `com.bhojango.app`. iPhone only
(`"supportsTablet": false`, `apps/customer/app.json:13`), portrait.

See [README.md](README.md) for the review risks that affect this app (items 3, 4, 5,
6, 7, 9 and 11).

## Listing text

| Field | Text | Limit |
|---|---|---|
| App name (both stores) | `BhojanGo` (if taken: `BhojanGo: Food Delivery`, 23) | 30 |
| App Store subtitle | `Order from local kitchens` (25) | 30 |
| Play short description | `Order from local kitchens. See every fee before you pay, then track your order.` (79) | 80 |
| Apple keywords | `food,delivery,restaurant,takeout,meals,kitchen,indian,biryani,curry,lunch,dinner,order,boise` (92) | 100 |
| Apple category | Primary: Food & Drink. Secondary: Lifestyle. | |
| Play category | Food & Drink | |
| Support URL | `{SUPPORT_URL}` | |
| Privacy policy URL | `{PRIVACY_URL}` | |
| Marketing URL (Apple, optional) | `{MARKETING_URL}` | |
| Contact email | `{SUPPORT_EMAIL}` | |
| Account deletion URL (Play) | `{DELETE_ACCOUNT_URL}` | |

Apple keywords: comma-separated, no spaces, no app name, no category name, no other
companies' names. Add "hyderabad" when India is listed.

### Long description (Play full description; App Store description)

Plain text, 1,400 characters or so (limit 4,000). Only list what the app does today.

```
BhojanGo brings food from local kitchens to your door.

Find a kitchen
Browse the kitchens that deliver to your address. Search by dish or cuisine, and save the places you like.

Order your way
Choose sizes, options and add-ons for each dish. Your bag keeps your choices until you are ready.

See the full bill before you pay
The bill lists the food, the delivery fee, any other charges, tax and the tip, line by line. What you see is what you are charged.

Tip your delivery partner
Pick a tip at checkout, or none.

Pay by card
Pay securely by card through our payment provider. Google Pay is available where supported. BhojanGo does not store your card number.

Follow your order
Watch your order on a live map from the kitchen to your door. Send your delivery partner a quick message while the order is on its way. Your phone number stays private.

If something goes wrong
Report a problem with an order from the app and add a photo. You can rate each order and tell the kitchen what you thought.

Your account
Sign in with your phone number or your email. Save your addresses, choose which messages you get, and use the app in English, Spanish, Hindi, Telugu, Tamil, Kannada, Marathi or Bengali. You can download your data or delete your account from the app at any time.

Where we deliver
BhojanGo delivers in Boise, Idaho. More cities will follow. If we do not deliver to your address yet, you can still browse kitchens in a city we serve.
```

Check before publishing: the language list matches `packages/i18n/messages/*.json`
(en, es, hi, te, ta, kn, mr, bn); "Google Pay" only if live in the listed country;
"Spanish" only if the Spanish text is reviewed (`packages/i18n/REVIEW.md`). Do not
mention Hyderabad until Indian payments work in the app (README item 4).

### Content rating notes

- No violence, sexual content, profanity, drugs, gambling or horror.
- No alcohol or tobacco sales (none found in the catalogue code). If added later,
  the rating and an age check change.
- Users can interact: quick messages with the delivery partner during an order
  (preset plus free text up to 140 characters, phone numbers masked).
- Shares location: the delivery address goes to the kitchen and the delivery partner
  for the order. The customer's live GPS position is not shared.
- Digital purchases: none. Payments are for food and delivery (physical goods).
- Unrestricted web access: no. Terms and Privacy open in the system browser.
- Expected: Apple 4+ (accept the questionnaire's result), IARC Everyone.

## Privacy: what the app collects

"Linked" means stored against the account. Nothing is used for tracking (no
advertising, no data brokers, no cross-app tracking, no analytics SDK).

| Data | Collected | Linked to user | Tracking | Purpose | Where in code |
|---|---|---|---|---|---|
| Name | Yes | Yes | No | App functionality (account, order for the kitchen and rider) | `UserResponse.full_name`; `apps/customer/lib/account.ts:258` (profile update) |
| Email address | Yes, if the user signs in with email | Yes | No | App functionality (sign-in, receipts) | `packages/mobile-core/src/ui/signin.tsx:96-108` |
| Phone number | Yes, if the user signs in with phone | Yes | No | App functionality (sign-in by SMS code, order contact) | `packages/mobile-core/src/session.ts:35-36`, `apps/customer/app/sign-in.tsx:38-41` |
| Physical address | Yes (delivery addresses) | Yes | No | App functionality (delivery) | `apps/customer/lib/account.ts:157-175` |
| Precise location | Yes, only when the user taps "use my location"; not in the background | Yes (sent with the signed-in request and the order) | No | App functionality (find the delivery zone, set the address) | `apps/customer/lib/where.ts:48-57`, `apps/customer/lib/account.ts:204-212` |
| Coarse location | Country hint from the IP address, server side | Not stored with the account as far as the code shows; confirm on the server | No | App functionality (country, currency, language) | `packages/mobile-core/src/i18n.tsx:12-13`, `:151` |
| Payment info | Yes. Card details are entered in Stripe's sheet and go to Stripe; BhojanGo keeps the Stripe customer id and saved-card brand and last 4 digits | Yes | No | App functionality (payments) | `apps/customer/lib/pay.ts:67-69`, `apps/customer/lib/stripeSheet.ts:26-43`, `apps/customer/app/account/payments.tsx` |
| Purchase history | Yes (orders, receipts) | Yes | No | App functionality | `apps/customer/app/(tabs)/orders.tsx`, `apps/customer/app/account/receipt/[id].tsx` |
| Photos | Yes, optional: a photo with a problem report | Yes | No | Customer support | `apps/customer/app/report/[id].tsx:34-45` |
| Messages (Apple: "Emails or text messages"; Google: "Other in-app messages") | Yes: quick messages with the delivery partner | Yes | No | App functionality | `packages/mobile-core/src/chat.tsx`, `apps/customer/app/order/[id].tsx:218-219` |
| Customer support | Yes: problem reports (reason, items, photo) | Yes | No | Customer support | `apps/customer/app/report/[id].tsx` |
| Other user content | Yes: order ratings and comments | Yes (comment shown to the kitchen without the name) | No | App functionality | `apps/customer/lib/account-rating.tsx` |
| User ID | Yes (account id) | Yes | No | App functionality | `packages/mobile-core/src/session.ts:24` |
| Device ID / push token | **No** (no push registration in the code; see README item 7) | | | | |
| Crash data, performance data | **No** (no crash SDK in the app) | | | | |
| Product interaction / analytics | **No** (no analytics SDK). The server keeps a security log of sign-ins (not analytics) | | | | `backend/core_api/modules/identity/service/events.py` |
| Contacts, calendar, health, browsing or search history, audio, advertising data | No | | | | |

Third parties that receive data to provide the service (service providers, so not
"sharing" under Google's definitions; list them in the privacy policy): Stripe (card
payments, `@stripe/stripe-react-native`), the SMS and email providers that send
sign-in codes, OpenFreeMap (map tiles; sees IP address and map area,
`apps/customer/components/LiveMap.tsx:22`), and the kitchen and delivery partner of
each order (name, delivery address, order).

- Encrypted in transit: Yes, provided the production URLs are `https://`
  (README item 3).
- Deletion: Yes. In the app: Account > Privacy > "Delete my account"
  (`apps/customer/app/account/privacy.tsx:52-64`, `DELETE /api/v1/users/me`). On the
  web: `{DELETE_ACCOUNT_URL}`. Orders are kept for tax without the name, street, map
  pin or notes (`backend/core_api/modules/identity/api/v1/users.py:70-76`).
- Data export: Yes, Account > Privacy > Download (`GET /api/v1/me/export`,
  `apps/customer/lib/account.ts:144`).

### App Store "nutrition label" answers

Data Linked to You: Contact Info (Name, Email Address, Phone Number, Physical
Address), Location (Precise Location), Financial Info (Payment Info), Purchases
(Purchase History), User Content (Photos or Videos, Emails or Text Messages, Customer
Support, Other User Content), Identifiers (User ID). Purpose for all: App
Functionality; for problem reports also Customer Support (not an Apple purpose; use
App Functionality). Data Used to Track You: none. Data Not Linked to You: none
(unless the server keeps the IP country hint separately; then Coarse Location, not
linked).

### Google Play Data safety answers

- Does the app collect or share user data? Yes, collects. Shared: No.
- All data encrypted in transit: Yes. Users can request deletion: Yes.
- Personal info: Name, Email address, Phone number, Address, User IDs. Collected,
  required (name, one of email/phone) or optional (addresses), App functionality,
  Account management.
- Financial info: User payment info (collected by the Stripe SDK), Purchase history.
  App functionality.
- Location: Precise location, optional, App functionality. Approximate location if
  the server stores the IP country hint.
- Messages: Other in-app messages. App functionality.
- Photos and videos: Photos, optional, App functionality (support).
- App activity: Other user-generated content (ratings and comments). App
  functionality.
- Not collected: Device or other IDs (until push is added), App info and
  performance, Web browsing, Contacts, Calendar, Audio, Files and docs, Health.

## Permissions

| Permission | Platform | Where declared | Text shown to the user | Requested in code | Status |
|---|---|---|---|---|---|
| Location when in use | iOS | `expo-location` plugin `locationWhenInUsePermission` | "BhojanGo uses your location only while you use the app, to find kitchens near you and set your delivery address." | `lib/where.ts:49`, `lib/account.ts:205` | Used. Set once, in the plugin (R19). |
| Location always (both keys) | iOS | None | None | Never requested | Removed (R19): the plugin's `locationAlwaysAndWhenInUsePermission` and `locationAlwaysPermission` are `false`, so neither key is written. |
| Camera | iOS / Android | `expo-image-picker` plugin, `app.json:59` | "BhojanGo uses the camera for a photo when you report a problem with an order." | `app/report/[id].tsx:36-38` | Used. |
| Photo library | iOS | `expo-image-picker` plugin, `app.json:60` | "BhojanGo lets you choose a photo when you report a problem with an order." | `app/report/[id].tsx:39` (no separate permission request; picker) | Used. |
| Microphone | iOS / Android | None | None | Never | Removed (R19): `expo-image-picker` `microphonePermission: false`. Confirm after prebuild. |
| `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION` | Android | `app.json` `android.permissions` | System dialog | As above | Used. |
| `POST_NOTIFICATIONS` | Android 13+ | `expo-notifications` | System dialog | Never requested | See README item 7. |
| `RECEIVE_BOOT_COMPLETED`, `VIBRATE` | Android | `app.json` `android.permissions` | None (normal) | Notifications | Keep only if push is added. |
| Background location | Both | Not declared | | | Correct: the customer app never needs it. |

Paths in this table are relative to `apps/customer/`.
