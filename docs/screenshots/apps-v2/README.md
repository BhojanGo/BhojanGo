# The apps on QA: screenshots and side-by-sides (round 4)

Taken on 2026-11-15 on Android emulators against the QA environment (Railway), on the demo data
(QA reset with `tools/seed/demo.py`) and with the demo rider simulator running. The APKs were built on
GitHub (`.github/workflows/android-apk.yml`); the JavaScript came from Metro with the QA profile
(`tools/mobile/env-profile.sh qa`).

## What is here

- `<Board>.jpg`: a design board (`docs/design/screens/<Board>.html`, rendered by
  `tools/mobile/render_boards.py`) on the left, the app's screen on QA on the right
  (`tools/mobile/screens_compose.py`).
- `customer-phone/`, `rider-phone/`, `partner-phone/` (1080x2400), `partner-tablet/` (2560x1600): every
  screenshot the read-only QA flows took, in flow order.

Boards with no app screen here: `CustomerLoading`, `CustomerOutOfArea`, `CustomerPaymentFailed`,
`RiderOnboarding`, `PartnerOnboarding`. They need states that would change QA data (a failed payment, a
new account), and QA gets no test writes. Their flows run on the local stack.

## How they were taken (read-only on QA)

`tools/railway/maestro-qa.sh` runs, against QA, only the flows tagged `qa-readonly` and the `qa/`
folders. Those flows sign in with seed phones (OTP 123456 on QA) and only look:

- **Customer:** `qa-browse` (home, kitchen, dish, bag up to Pay, without paying), `qa-track` (the demo
  order on the live map), `account-pages` (opens every account page, saves nothing), `orders-receipt`
  (a past order's receipt and the report form, without sending).
- **Rider:** `qa/01-home`, `qa/02-demo-order`, `qa/03-earnings`, `qa/04-language`. The demo rider
  never goes online here; the simulator drives that account.
- **Partner:** `qa/01-orders`, `qa/02-rating-summary`, `qa/03-menu-photo` (the photo preview, never
  saved), `qa/04-language`.

Results: customer 4/4, rider 4/4, partner 4/4 on the phone, partner 4/4 on the tablet.

Maestro writes `takeScreenshot` files into each run's output folder
(`~/.maestro/tests/<run>/<flow>/takeScreenshot/...`), not the working directory; they were collected
from there.

## Notes for review

- Times on these screens use the emulator's time zone (US). A phone in the city shows local time.
- Tracking (`CustomerTracking.jpg`, `customer-phone/qa-05-tracking.jpg`) was retaken after the
  simulator fix (#99): the demo rider is on the map with the trail so far, ETA and distance left from
  realtime, the rider's name and the PIN. The PIN is the fixed one because the demo customer's phone is
  a fictional seed number.
