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

- `stack-*` screenshots and the side-by-sides `CustomerLoading`, `CustomerOutOfArea`,
  `CustomerPaymentFailed`, `RiderOnboarding`, `PartnerOnboarding`: states that change data, so they were
  taken on a throwaway stack instead of QA (below).

## The five states QA can't show (throwaway stack on GitHub)

Reaching these writes data (a failed payment, new accounts, a held request), and QA gets no test writes.
`.github/workflows/app-screens.yml` brings up its own stack on a GitHub runner (Docker Compose, backend
profile, seed and demo seed, demo rider off), installs the debug APKs on an Android emulator (API 34;
Pixel 6 for the customer and rider apps, Pixel Tablet for the partner app; JavaScript from Metro on the
runner) and runs the flows in `apps/<app>/.maestro/stack/` with `tools/mobile/stack-screens.sh`. Those flows
aren't tagged `qa-readonly`, and `tools/railway/maestro-qa.sh` never runs `stack/`. Run it from the
Actions tab or by pushing to a `screens/*` branch; the screenshots are the `app-stack-screens-phone` and
`app-stack-screens-tablet` artifacts.

Taken on 2026-11-15 by run
[43745906719](https://github.com/BhojanGo/BhojanGo/actions/runs/43745906719):

- **CustomerLoading** (`customer-phone/stack-loading`): the seed customer's home while the kitchens
  load. The app talks to core through `tools/mobile/slow_proxy.py`, which holds `GET /discover` until the
  flow lets it go.
- **CustomerOutOfArea** (`customer-phone/stack-out-of-area`): a brand-new customer whose only address
  (made through the API before the app signs in) is in Nampa, Idaho, outside every zone.
- **CustomerPaymentFailed** (`customer-phone/stack-payment-failed`): a bag at Spice Route Kitchen, Pay,
  then Decline on the local fake checkout (payment method `fake_decline`).
- **RiderOnboarding** (`rider-phone/stack-onboarding`): the seed rider still signing up (3 of 5,
  insurance needed now), as on the board. `stack-signup` and `stack-onboarding-new` are a brand-new rider
  signing up (1 of 5).
- **PartnerOnboarding** (`partner-tablet/stack-onboarding`): a brand-new kitchen applies from the tablet
  (`stack-join`) and lands on step 2, the FSSAI licence, with the number and date typed in. No licence
  document is uploaded, so the upload box shows where the board shows a file.

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
