# BhojanGo Delivery (rider app)

`apps/rider`. iOS bundle id and Android package `com.bhojango.rider`. iPhone only
(`"supportsTablet": false`, `apps/rider/app.json:13`), portrait, dark interface.

See [README.md](README.md) for the review risks that affect this app (items 1, 2, 3,
5, 6, 7, 8 and 9). Items 1 (no in-app deletion), 2 (background location) and 8 (no
privacy link) must be fixed before submitting.

## Listing text

| Field | Text | Limit |
|---|---|---|
| App name | `BhojanGo Delivery` (17) | 30 |
| App Store subtitle | `Deliver food with BhojanGo` (26) | 30 |
| Play short description | `Deliver food for BhojanGo: go online, take nearby orders, track your earnings.` (78) | 80 |
| Apple keywords | `courier,driver,rider,deliveries,earn,gig,food,orders,flexible,work,partner,bike,boise` (85) | 100 |
| Apple category | Primary: Business. Secondary: Navigation. | |
| Play category | Business (Maps & Navigation is the other fit) | |
| Support URL | `{SUPPORT_URL}` | |
| Privacy policy URL | `{PRIVACY_URL}` | |
| Contact email | `{SUPPORT_EMAIL}` | |
| Account deletion URL (Play) | `{DELETE_ACCOUNT_URL}` | |

Avoid earnings claims ("earn up to ...") in any field. They are unverifiable and
reviewers question them.

### Long description

The background location paragraph is required by Google Play for apps that use
background location; keep it.

```
BhojanGo Delivery is the app for delivery partners who deliver food for BhojanGo.

Go online when you want to
Go online to get delivery offers near you, and go offline when you are done. You choose when you work.

Accept or pass
Each offer shows the pickup, the drop-off and what you earn for it before you accept. Some offers include more than one order from the same kitchen.

Pick up and drop off
Follow the steps for each order: arrive at the kitchen, pick up, and deliver. Finish with a photo at the door or the customer's PIN. Send the customer a quick message if you need to; phone numbers stay private.

Earnings and payouts
See what you earned today and this week, and your payouts. Payouts go to the bank account you connect through our payment partner.

Safety
Use the SOS screen to call your local emergency number and tell BhojanGo's safety team where you are.

Sign up in the app
Tell us your name, date of birth, vehicle and city, then add your licence and insurance. We check your documents before you can go online.

Location use
While you are online, BhojanGo Delivery collects your location, including when the app is closed or not in use, to offer you nearby deliveries and to show customers where their order is. It stops when you go offline. You can choose to share your location only while the app is open.

The app works in English and in the other languages BhojanGo supports in your country. You need to be old enough to deliver under the rules of your country.
```

Check before publishing: "what you earn for it before you accept" matches the offer
screen (`apps/rider/.maestro/deliver.yaml`, screenshot `06-offer`); the background
check wording if a provider is named in the app.

### Content rating notes

- No violence, sexual content, gambling or the like.
- Users can interact: quick messages with the customer during an order.
- Shares location: yes. The rider's live position is shown to the customer of the
  active order.
- Digital purchases: none.
- Expected: Apple 4+ (or the questionnaire's result), IARC Everyone. The service
  itself needs an adult, which the sign-up enforces; that does not change the
  content rating.

## Privacy: what the app collects

Nothing is used for tracking. No analytics, advertising or crash SDK.

| Data | Collected | Linked to user | Tracking | Purpose | Where in code |
|---|---|---|---|---|---|
| Name | Yes | Yes | No | App functionality, account (first name shown to customers) | `apps/rider/app/join.tsx`; `RiderApply.full_name` (`backend/core_api/modules/identity/api/v1/signup.py:42`) |
| Email address | Yes, if signing in with email | Yes | No | Sign-in | `apps/rider/app/sign-in.tsx:74-77` |
| Phone number | Yes, if signing in with phone | Yes | No | Sign-in, safety team contact | `apps/rider/app/sign-in.tsx` |
| Date of birth | Yes | Yes | No | App functionality (minimum age check) | `apps/rider/app/join.tsx:29-56`; `RiderProfile.date_of_birth` (`backend/core_api/modules/identity/models/rider.py:45`) |
| Other info: vehicle type, city | Yes | Yes | No | App functionality | `signup.py:43-45` |
| Precise location | Yes: every few seconds while online, in the background if "all the time" is allowed; once for SOS | Yes | No | App functionality (offers, live tracking for the customer, safety) | `apps/rider/lib/location.ts:32-46`, `:99-125`; `apps/rider/app/sos.tsx:27` |
| Photos | Yes: delivery proof photo at the door; photos of licence and insurance | Yes | No | App functionality (proof of delivery, identity and eligibility checks) | `apps/rider/app/delivery/[id].tsx:153-164`; `apps/rider/app/document.tsx:23-30`; upload `apps/rider/lib/upload.ts:6` |
| Other info: driving licence and insurance details | Yes (as photos, reviewed by BhojanGo) | Yes | No | App functionality | `RiderDocument` (`backend/core_api/modules/identity/models/rider.py:11-33`) |
| Financial info: bank account | **Not by the app.** Entered on the payment provider's page in the browser | | | | `apps/rider/app/payouts.tsx:72-75` |
| Financial info: earnings and payouts | Yes | Yes | No | App functionality | `apps/rider/app/(tabs)/earnings.tsx`, `apps/rider/app/payouts.tsx` |
| Messages | Yes: quick messages with the customer | Yes | No | App functionality | `apps/rider/app/delivery/[id].tsx:321-329`, `packages/mobile-core/src/chat.tsx` |
| Customer support / safety | Yes: SOS alerts with location | Yes | No | App functionality (safety) | `apps/rider/app/sos.tsx:27` |
| User ID | Yes | Yes | No | App functionality | `packages/mobile-core/src/session.ts:24` |
| Background check | **Not in the app.** The checklist says it starts after insurance and the result comes by SMS and email (`backend/core_api/modules/identity/api/v1/riders.py:137-141`). If a provider collects more (for example a US Social Security number), it does so outside the app; name it in the privacy policy. | | | | |
| Device ID / push token | **No** (README item 7) | | | | |
| Crash, performance, analytics | No | | | | |

Third parties (service providers; list in the privacy policy): the payment provider
for payouts (Stripe Connect or Razorpay), the SMS and email providers for sign-in
codes, the background check provider if one is used, and the customer of each order
(first name and live position during the delivery).

- Encrypted in transit: Yes, with `https://` production URLs (README item 3). Note
  that the background task posts to `urls.realtime` (`apps/rider/lib/location.ts:36`).
- Deletion: **not in the app yet** (README item 1). Also, the server keeps the
  licence and insurance records and images after deletion today (README item 1).
  On the web: `{DELETE_ACCOUNT_URL}`.

### App Store "nutrition label" answers

Data Linked to You: Contact Info (Name, Email Address, Phone Number), Location
(Precise Location), Financial Info (Other Financial Info: earnings and payouts),
User Content (Photos or Videos, Emails or Text Messages, Customer Support),
Identifiers (User ID), Other Data (date of birth, vehicle, licence and insurance
details). Purpose: App Functionality. Data Used to Track You: none.

### Google Play Data safety answers

- Collects: Yes. Shares: No (the customer seeing the rider's position is part of
  the service the rider starts by going online; re-check this answer against Play's
  current definition of "sharing" when filling the form).
- Encrypted in transit: Yes. Deletion request: Yes (web link now; in app after
  README item 1).
- Location: Precise location, collected in the background as well. App
  functionality.
- Personal info: Name, Email address, Phone number, User IDs, Other info (date of
  birth, vehicle, licence and insurance details). App functionality, Account
  management, Fraud prevention, security and compliance (eligibility checks).
- Financial info: Other financial info (earnings, payouts). App functionality.
- Photos and videos: Photos. App functionality.
- Messages: Other in-app messages. App functionality.
- Not collected: Device or other IDs, App info and performance, Contacts, Calendar,
  Audio, Health, Web browsing, Files and docs (documents are photos).

Also in Play Console for this app: the Location permissions declaration (background
location) and the Foreground service declaration, each with a video (README item 2).

## Permissions

| Permission | Platform | Where declared | Text shown to the user | Requested in code | Status |
|---|---|---|---|---|---|
| Location when in use | iOS | `app.json:16` | "BhojanGo Delivery uses your location to show nearby deliveries and share your position with customers." | `lib/location.ts:57` (going online, `app/(tabs)/drive.tsx`) | Used. Expo's plugin may replace it with its default unless `locationWhenInUsePermission` is set; set it to this text. |
| Location always and when in use | iOS | `app.json:17` and plugin `app.json:51` (the plugin's wins) | Plugin: "BhojanGo Delivery shares your location while you are online, even with the screen off, so you get nearby offers and customers can follow their order." | `lib/location.ts:68`, from the Drive tab banner (`app/(tabs)/drive.tsx:196-199`) | Used. Remove the `infoPlist` copy so there is one text. |
| Location always | iOS | Added by `expo-location` default | Expo default ("Allow $(PRODUCT_NAME) to access your location") | `lib/location.ts:68` | Generic: set `locationAlwaysPermission` (README item 2). |
| Background mode `location` | iOS | `app.json:18-20` | Blue status bar indicator (`showsBackgroundLocationIndicator: true`, `lib/location.ts:109`) | `lib/location.ts:104` | Used. |
| Camera | iOS / Android | `app.json:21`, plugin `app.json:78` | "BhojanGo Delivery uses the camera for photos at the door and of your documents." | `app/delivery/[id].tsx:153`, `app/document.tsx:23` | Used. |
| Photo library | iOS | `app.json:22`, plugin `app.json:79` | "BhojanGo Delivery lets you choose a photo of your documents." | `app/document.tsx:23` | Used. |
| Microphone | iOS / Android | Added by `expo-image-picker` default | Expo default | Never | Unused. Set `microphonePermission: false`. |
| `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION` | Android | `app.json` | System dialog | `lib/location.ts:57` | Used. |
| `ACCESS_BACKGROUND_LOCATION` | Android | `app.json:34`, plugin `app.json:52` | System dialog ("Allow all the time" in Settings) | `lib/location.ts:68` | Used. Needs a stronger prominent disclosure, the Play declaration and a video (README item 2). |
| `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_LOCATION` | Android | `app.json:35-36`, plugin `app.json:53` | Ongoing "You're online" notification (`lib/location.ts:110-114`) | `lib/location.ts:104-116` | Used. Needs the Play foreground service declaration. |
| `POST_NOTIFICATIONS` | Android 13+ | `expo-notifications` plugin | System dialog | Never requested | Without it the "You're online" notification is hidden (README item 7). |
| `RECEIVE_BOOT_COMPLETED`, `VIBRATE` | Android | `app.json` | None (normal) | Notifications plugin | Keep only if push is added. |

Paths in this table are relative to `apps/rider/`.
