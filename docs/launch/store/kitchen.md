# BhojanGo Kitchen (partner app)

`apps/partner`. iOS bundle id and Android package `com.bhojango.partner`. Runs on
tablets and phones: `"supportsTablet": true`, `"requireFullScreen": true`
(`apps/partner/app.json:13-14`), any orientation; tablets lock to landscape and
phones to portrait (`apps/partner/lib/layout.ts:31-34`). iPad screenshots are
therefore required on the App Store.

See [README.md](README.md) for the review risks that affect this app (items 1, 3, 5,
6, 7, 8 and 11). Item 1 (no in-app account deletion) and item 8 (no privacy link)
must be fixed before submitting to Apple.

## Listing text

| Field | Text | Limit |
|---|---|---|
| App name | `BhojanGo Kitchen` (16) | 30 |
| App Store subtitle | `Orders and menu for kitchens` (28) | 30 |
| Play short description | `For BhojanGo partner kitchens: take orders, update your menu, see your payouts.` (79) | 80 |
| Apple keywords | `restaurant,orders,menu,tablet,kitchen,partner,merchant,food,delivery,payouts,owner,manager` (90) | 100 |
| Apple category | Primary: Business. Secondary: Food & Drink. | |
| Play category | Business | |
| Support URL | `{SUPPORT_URL}` | |
| Privacy policy URL | `{PRIVACY_URL}` | |
| Contact email | `{SUPPORT_EMAIL}` | |
| Account deletion URL (Play) | `{DELETE_ACCOUNT_URL}` | |

### Long description

```
BhojanGo Kitchen is the app for kitchens and restaurants that sell on BhojanGo. Keep it open on a tablet at the counter, or use it on your phone.

Take orders
New orders arrive with a sound and stay on screen until you accept them. Move each order from new to preparing to ready, so the delivery partner knows when to come. The screen stays on while the app is open.

Pause when you are busy
Pause new orders for 15, 30 or 60 minutes, or until you turn them back on.

Keep your menu up to date
Mark dishes as sold out, set preparation time, add dish photos from the camera or your gallery, set your opening hours and create offers.

See how you are doing
Check your ratings and the latest comments from customers, and your payouts.

Get help
Ask BhojanGo to call you back about an order, a payout, your menu or your account.

Join BhojanGo
New kitchens can apply from the app: tell us about your kitchen, add the licence and tax details your country requires, connect a bank account through our payment partner, and we check everything before your kitchen goes live.

The app works in English and in the other languages BhojanGo supports in your country. You need a BhojanGo partner account to use it.
```

### Content rating notes

- Business tool. No violence, sexual content, gambling or the like.
- Users can interact: no direct messaging with customers. Kitchens see customers'
  rating comments without names (`apps/partner/lib/ratings.tsx:4`).
- Shares location: no device location. The kitchen address is shown to customers.
- Digital purchases: none.
- Expected: Apple 4+, IARC Everyone.

## Privacy: what the app collects

Nothing is used for tracking. No analytics, advertising or crash SDK.

| Data | Collected | Linked to user | Tracking | Purpose | Where in code |
|---|---|---|---|---|---|
| Name | Yes (the person signing up) | Yes | No | App functionality, account | `apps/partner/app/join.tsx`; server `KitchenApply.full_name` (`backend/core_api/modules/identity/api/v1/signup.py:55`) |
| Email address | Yes, if signing in with email | Yes | No | Sign-in | `apps/partner/app/sign-in.tsx:67-70` |
| Phone number | Yes, if signing in with phone | Yes | No | Sign-in | `apps/partner/app/sign-in.tsx` |
| Physical address | Yes: the kitchen's street, area and postal code | Yes (owner's business) | No | App functionality (customers see the kitchen) | `signup.py:56-63`; `apps/partner/app/join.tsx` |
| Precise or coarse location | **No** device location (the map point comes from the chosen city, `apps/partner/app/join.tsx:40`) | | | | |
| Other info: business licence and tax ids | Yes (India): FSSAI number and expiry, licence document (PDF or image), GSTIN | Yes | No | App functionality (legal requirement to list a kitchen) | `apps/partner/app/apply.tsx:178`, `:214-220`, `:290`; `backend/core_api/modules/catalog/models/restaurant.py:64-81` |
| Files and docs | Yes: the licence document | Yes | No | App functionality | `apps/partner/app/apply.tsx:178` (`expo-document-picker`) |
| Financial info: bank account | **Not by the app.** The bank account is entered on the payment provider's own page in the browser (Stripe Connect or Razorpay) | | | | `apps/partner/app/apply.tsx:274-278` |
| Financial info: payouts | Yes: payout amounts and status | Yes | No | App functionality | `apps/partner/app/(kitchen)/payouts.tsx` |
| Photos | Yes: dish photos (public on the menu) | Yes | No | App functionality | `apps/partner/app/(kitchen)/menu.tsx:272-278` |
| Customer support | Yes: call-back requests (topic and note) | Yes | No | Customer support | `apps/partner/app/(kitchen)/help.tsx:52-60` |
| Other user content | Yes: menu items, prices, offers, hours | Yes | No | App functionality | `apps/partner/app/(kitchen)/menu.tsx` |
| User ID | Yes | Yes | No | App functionality | `packages/mobile-core/src/session.ts:24` |
| Device ID / push token | **No** (no push registration; README item 7) | | | | |
| Audio | **No**. The app plays an alert sound; it never records | | | | `apps/partner/lib/board.ts:51` |
| Crash, performance, analytics | No | | | | |

Customer data the kitchen sees (customer first name, order items, rating comments
without names) is not collected from the kitchen user, so it is not declared here; it
is declared in the customer app.

- Encrypted in transit: Yes, with `https://` production URLs (README item 3).
- Deletion: **not in the app yet** (README item 1). Until it is, the Apple review
  will fail. On the web: `{DELETE_ACCOUNT_URL}`. Server endpoint exists
  (`DELETE /api/v1/users/me`). Licence documents and tax ids are business records;
  decide how long they are kept after an account is deleted and say so in the
  privacy policy.

### App Store "nutrition label" answers

Data Linked to You: Contact Info (Name, Email Address, Phone Number, Physical
Address), Financial Info (Other Financial Info: payouts), User Content (Photos or
Videos, Customer Support, Other User Content), Identifiers (User ID), Other Data
(licence and tax ids, licence document). Purpose: App Functionality. Data Used to
Track You: none.

### Google Play Data safety answers

- Collects: Yes. Shares: No. Encrypted in transit: Yes. Deletion request: Yes
  (after README item 1; the web link counts for Play now).
- Personal info: Name, Email address, Phone number, Address, User IDs, Other info
  (licence and tax ids). App functionality, Account management.
- Financial info: Other financial info (payouts). App functionality.
- Photos and videos: Photos. App functionality.
- Files and docs: Yes (licence document). App functionality.
- App activity: Other user-generated content (menu, offers). App functionality.
- Not collected: Location, Messages, Audio, Device or other IDs, App info and
  performance, Contacts, Calendar, Health, Web browsing.

## Permissions

| Permission | Platform | Where declared | Text shown to the user | Requested in code | Status |
|---|---|---|---|---|---|
| Camera | iOS | `app.json:17` and `expo-image-picker` plugin `app.json:45` | "BhojanGo Kitchen uses the camera to take photos of your dishes for your menu." | `app/(kitchen)/menu.tsx:272` | Used. The same text is set twice; keep the plugin one. |
| Photo library | iOS | `app.json:18` and plugin `app.json:44` | "BhojanGo Kitchen lets you choose photos of your dishes for your menu." | `app/(kitchen)/menu.tsx:272` | Used. |
| Microphone | iOS / Android | Added by default by `expo-image-picker` and `expo-audio` plugins | Expo default | Never | Unused. Turn off in both plugins (README item 6). |
| `CAMERA` | Android | `app.json:28` | System dialog | `app/(kitchen)/menu.tsx:272` | Used. |
| `WAKE_LOCK` | Android | `app.json:31` | None (normal) | Not needed by `useKeepAwake` (`app/_layout.tsx:15`) | Can be removed. |
| `RECEIVE_BOOT_COMPLETED`, `VIBRATE` | Android | `app.json` | None (normal) | Notifications plugin | Keep only if push is added. |
| `POST_NOTIFICATIONS` | Android 13+ | `expo-notifications` plugin | System dialog | Never requested | README item 7. |
| Location | Both | Not declared | | Not used | Correct. |
| Files (document picker) | Both | None needed (system picker) | | `app/apply.tsx:178` | Correct. |

Paths in this table are relative to `apps/partner/`.
