# BhojanGo Delivery: Play Console location declarations

What to paste into Play Console for `com.bhojango.rider`, and how to film the video
Google asks for. Written for round 19 (2026-11-19). Nothing here has been submitted.

Two forms ask about location:

1. **App content > Sensitive app permissions > Location permissions**
   (`ACCESS_BACKGROUND_LOCATION`).
2. **App content > Foreground service permissions** (`FOREGROUND_SERVICE_LOCATION`,
   Android 14 and later).

Both ask for a video link. One video can serve both if it shows everything in the
shot list below. Upload it to YouTube as **Unlisted** (not Private) and paste the link.

## How the app behaves (check it still does before filing)

- Location is used only while the delivery partner is **online** (on shift). Going
  online asks for location "while using the app" (`apps/rider/lib/location.ts`
  `askForLocation`).
- Right after going online, if background access is not granted yet, the app shows
  the prominent disclosure (`apps/rider/lib/disclosure.tsx`), once per app run. The
  "Keep offers coming with the screen off" banner on the Drive tab opens it again.
  "Allow" opens the system prompt; "No thanks" closes it and location stays
  "while using the app".
- With background access, a foreground service runs with the notification
  "You're online" (`startLocationUpdatesAsync`, `foregroundService`). It stops when the
  delivery partner goes offline, signs out, deletes the account, or the server says
  they are offline (`stopTracking`).
- The app never asks for background location at start-up, sign-in or sign-up.

## The prominent disclosure (in the app, English)

Title: **Share your location in the background?**

> BhojanGo Delivery collects location data to offer you nearby deliveries and to show
> customers where their order is, even when the app is closed or not in use. This
> happens only while you're online; going offline stops it.
>
> Your location goes to BhojanGo and, during a delivery, to that order's customer. It
> isn't sold or used for ads.
>
> On the next screen, choose "Allow all the time".

Buttons: **Allow** (then the system prompt) and **No thanks**.

The keys are `rider.location.*` in `packages/i18n/messages/*.json` (8 languages).

## Form 1: Location permissions (background location)

**Which feature in your app needs access to location in the background?**

> Delivery offers and live order tracking while the delivery partner is online.

**Describe the feature and why it needs background location** (paste as is):

> BhojanGo Delivery is the app delivery partners use to deliver food orders. While a
> delivery partner is online (on shift), the app sends their location to BhojanGo
> every few seconds so we can offer them nearby orders and show the customer where
> their order is on the way. Delivery partners keep the phone in a mount or pocket and
> use a navigation app while riding, so our app is usually not on screen; without
> background location, offers stop and the customer's map freezes as soon as they
> switch to navigation or the screen turns off. Location is collected only while the
> delivery partner is online, a "You're online" notification is shown the whole time,
> and going offline stops it at once. We show a prominent disclosure explaining this
> before the system permission prompt, and the app works with "while using the app"
> location if they decline.

**Is background location core to the app?** Yes: receiving offers and delivering
orders is the app's main purpose; location is how orders are matched and tracked.

**Video link:** `{LOCATION_VIDEO_URL}` (see the shot list).

## Form 2: Foreground service (FOREGROUND_SERVICE_LOCATION)

**Foreground service type:** Location.

**Describe the task the user starts** (paste as is):

> When a delivery partner taps "Go online", the app starts a location foreground
> service with a visible "You're online" notification. It shares their location with
> BhojanGo while they are on shift so they get nearby delivery offers and customers
> can follow their order. It runs until they tap "Go offline" (or sign out).

**Impact if the task is deferred or interrupted** (paste as is):

> Offers would stop reaching the delivery partner and the customer's live map would
> stop updating in the middle of a delivery. The task must run continuously while the
> delivery partner is online, including when the screen is off or a navigation app is
> in front, so it cannot be deferred or run as a scheduled job.

**User-initiated:** Yes (the "Go online" button). **User can stop it:** Yes ("Go
offline", or signing out).

**Video link:** `{LOCATION_VIDEO_URL}` (the same video).

## Video shot list

Length: keep it short, about 30 seconds (no more than 60). Portrait screen recording
from a real Android phone (Android 14 or later, so the foreground service type
applies), with a fresh install so no permission is granted yet. Use a production or
review build (no "Test site" banner) and the store review delivery partner account
(README "Reviewer access"). No voice-over needed; add short captions if your editor
allows.

1. (0:00) Open BhojanGo Delivery, signed in as the review delivery partner, on the
   Drive tab. Caption: "Delivery partner app".
2. (0:03) Tap **Go online**. The system asks for location: choose **While using the
   app**.
3. (0:07) The prominent disclosure appears. Hold on it for 3 seconds so the whole text
   can be read. Caption: "Disclosure before the background permission".
4. (0:11) Tap **Allow**. Android opens the location permission page: choose **Allow
   all the time**, then go back to the app.
5. (0:17) Pull down the notification shade: show the **"You're online"** notification
   (the foreground service). Caption: "Foreground service while online".
6. (0:20) Press Home, open Google Maps (or turn the screen off and on), wait 3 seconds.
   Show that the location keeps updating: either the app's status pill still says
   online when you come back, or, better, a second screen (the admin Operations map,
   or the customer's order tracking) shows the delivery partner moving. Caption:
   "Location keeps being shared with the app in the background".
7. (0:27) Back in the app, tap **Go offline**. Pull down the shade: the notification is
   gone. Caption: "Going offline stops location".

Optional, if Google asks why the app is useful without background access: record a
second short clip that taps **No thanks** at step 4 and shows the app still going
online with "while using the app" location.

## After filing

- Play Console > Store listing: the full description must mention background
  location (see `delivery.md`, "Store listing").
- If Google refuses the background location declaration, the fall-back in
  README item 2 applies (foreground service started on going online, without
  `ACCESS_BACKGROUND_LOCATION`); test it on the target Expo SDK first.
