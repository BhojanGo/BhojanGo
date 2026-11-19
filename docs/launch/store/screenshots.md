# Store screenshots and graphics

Sizes as published by Apple and Google in 2025–2026. Both stores change these from
time to time: check App Store Connect's "Screenshot specifications" page and Play
Console's upload hints on the day you upload.

## Rules that apply to every screenshot

- Take them from a **production** build (`EXPO_PUBLIC_APP_ENV=production`). The
  "Test site" banner must not appear (README item 3). The QA Maestro flows assert the
  banner (`apps/partner/.maestro/qa/01-orders.yaml`, `apps/rider/.maestro/qa/01-home.yaml`),
  so those two flows fail on a production build; use the store script's manual mode
  for those screens.
- Use realistic but invented data: demo kitchens, dishes and names. No real customer
  names, phone numbers or addresses.
- App Store screenshots must not show Android system bars or other Android
  imagery (Apple 2.3.10). Crop the status bar and navigation bar
  (`--crop-top` / `--crop-bottom` in the script), or take them on an iOS simulator.
- No alpha channel. Save as PNG (RGB) or JPEG.
- Text overlays are allowed; keep them plain and factual (no "best", "fastest",
  "#1").

## App Store (Apple)

1 to 10 screenshots per size, PNG or JPEG, RGB.

| Size | Accepted pixel sizes (portrait; landscape is the same swapped) | Needed for |
|---|---|---|
| iPhone 6.9" | 1320 x 2868, 1290 x 2796, 1260 x 2736 | All three apps. Required unless 6.5" is given. |
| iPhone 6.5" | 1284 x 2778, 1242 x 2688 | Required if no 6.9" set is uploaded. Upload one of 6.9" or 6.5"; smaller iPhone sizes are scaled from it. |
| iPad 13" | 2064 x 2752, 2048 x 2732 | **BhojanGo Kitchen only** (`supportsTablet: true`). The customer and Delivery apps are iPhone only. |

The script's targets: `ios69` = 1320 x 2868, `ios65` = 1284 x 2778,
`ipad13` = 2064 x 2752 (portrait) or 2752 x 2064 (landscape, used automatically
for landscape captures).

App icon: 1024 x 1024 PNG, no transparency, no rounded corners (Apple rounds it).
It comes from the build (`apps/*/assets/icon.png`, all three are 1024 x 1024 and
fully opaque). App previews (videos) are optional.

## Google Play

| Asset | Size | Count | Notes |
|---|---|---|---|
| Phone screenshots | Each side 320 to 3840 px; the long side at most twice the short side | 2 to 8 | 1080 x 1920 (9:16) is safe. A raw 1080 x 2400 emulator capture is 20:9, which is more than 2:1 and is refused; the script pads it to 9:16. At least 4 screenshots of 1080 px or more help the app appear in more places in Play. |
| 7" tablet screenshots | 320 to 3840 px, at most 2:1 | up to 8 | Kitchen app. Script target `play7`: 1200 x 1920 or 1920 x 1200. |
| 10" tablet screenshots | 1080 to 7680 px, at most 2:1 | up to 8 | Kitchen app. Script target `play10`: 1600 x 2560 or 2560 x 1600. |
| Feature graphic | 1024 x 500, JPEG or 24-bit PNG, no alpha | 1 | Required. Keep the logo and any words away from the edges. |
| App icon | 512 x 512, 32-bit PNG, up to 1 MB | 1 | Required. Export from the same source as `assets/icon.png`. |

Tablet screenshots are optional for the phone-only apps. For the Kitchen app,
upload both phone and tablet sets: kitchens mainly use tablets.

## Screens to capture

The Maestro flow in brackets already reaches the screen; it can drive the capture
(`tools/mobile/store_shots.sh --flow`). Flows marked "writes data" create orders or
change state: run them only against a local stack, never QA or production.

### BhojanGo (customer), phone

1. Home with kitchens near the address [`qa-browse.yaml`, shot `qa-01-home`]
2. A kitchen's menu [`qa-browse.yaml`, `qa-02-kitchen`]
3. Customising a dish [`qa-browse.yaml`, `qa-03-dish`]
4. The bag with the full bill and tip buttons [`qa-browse.yaml`, `qa-04-bag`]
5. Live tracking on the map [`qa-track.yaml`, `qa-05-tracking`; or `order-and-track.yaml`, writes data]
6. Quick messages with the rider [`messages.yaml`, `12-messages`]
7. Orders and a receipt [`orders-receipt.yaml`, `47-orders`, `48-receipt`]
8. Sign-in (phone and email) [`sign-in-email.yaml`, `01b-sign-in-email`]

Optional: language choice (`account-language.yaml`), report a problem
(`report-problem.yaml`, writes data).

### BhojanGo Kitchen, tablet (landscape) and phone (portrait)

1. Orders board with a new order [`orders.yaml`, `03-new-order`; QA: `qa/01-orders.yaml`]
2. Preparing and ready columns [`orders.yaml`, `04-preparing`, `05-ready`]
3. Menu with sold-out toggles [`menu.yaml`, `07-menu`, `07b-menu-sold-out`]
4. Dish photo [`qa/03-menu-photo.yaml`, `03-dish-photo-preview`]
5. Offers [`menu.yaml`, `08-create-offer`, writes data]
6. Ratings summary [`qa/02-rating-summary.yaml`]
7. Payouts [`menu.yaml`, `10-payouts`]
8. Help and call-back [`help.yaml`, `13-help`]

Phone set: the same screens through `qa/05-phone-portrait.yaml` and
`qa/common/phone-tour.yaml` (`portrait-orders`, `portrait-menu`, `portrait-payouts`).

### BhojanGo Delivery, phone

1. Drive tab, online [`qa/01-home.yaml`, asserts the test banner: use manual mode]
2. A delivery offer [`deliver.yaml`, `06-offer`, writes data]
3. A batch offer [`batch.yaml`, `18-batch-offer`, writes data]
4. Pickup [`deliver.yaml`, `07-pickup`]
5. Drop-off with photo or PIN [`deliver.yaml`, `08-dropoff`]
6. Earnings [`qa/03-earnings.yaml`, `03-earnings`]
7. Sign-up checklist [`onboarding.yaml`, `03-onboarding`]
8. SOS / safety [`sos.yaml`, `12-sos`]

Do not show the background location prompt in store screenshots; it belongs in the
Play declaration video.

## Making them

```
# Manual: you move through the app, the script captures on Enter.
tools/mobile/store_shots.sh --app customer --out ./store-shots/customer

# Driven by Maestro flows (local stack only), then sized for both stores.
tools/mobile/store_shots.sh --app kitchen --out ./store-shots/kitchen \
  --flow apps/partner/.maestro/orders.yaml --targets play-phone,play10,ipad13

# App Store sizes need the Android bars cropped (pixels in the raw capture).
tools/mobile/store_shots.sh --app delivery --out ./store-shots/delivery \
  --targets ios69,ios65,play-phone --crop-top 63 --crop-bottom 126
```

The script only talks to `adb` and, with `--flow`, Maestro. It refuses the serials
`ZY22FDFV9J` and `emulator-5556` and any device that is not an emulator. Output:
`<out>/raw/*.png` (as captured) and `<out>/<target>/*.png` (sized). Sizing needs
Python with Pillow; without it only the raw captures are written.
