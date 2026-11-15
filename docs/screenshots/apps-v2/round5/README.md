# Round 5 on QA: emulator evidence

Taken on 2026-11-15 on Android emulators against the QA environment (Railway, demo data after a reset), with
the read-only Maestro flows (`tools/railway/maestro-qa.sh`; nothing is ordered or saved on QA).

| Item | Screens | Flow | Result |
|---|---|---|---|
| 1 Tab bar never covers content (#101) | `customer-tabbar-{home,search,orders,account}.jpg`: the bottom of each tab, last item above the bar | `apps/customer/.maestro/tabbar-clearance.yaml` | 4/4 tabs (Hyderabad customer); also passes on Boise's longer lists |
| 2 Time zones (#104) | `customer-timezone-boise-phone-hyderabad-order.jpg`: the emulator is in America/Boise (status bar 12:15 pm); the Hyderabad order #74DD21 shows "paid 15 Nov, 11:52 pm" | `apps/customer/.maestro/qa-timezone.yaml` | Pass. The API says placed_at 18:22:27 UTC, time_zone Asia/Kolkata: 11:52 pm IST. The phone's own zone would show 11:22 am |
| 5 Partner app: portrait on phones (#102) | `partner-phone-portrait-*.jpg` | `apps/partner/.maestro/qa/05-phone-portrait.yaml` and qa/01–04 | Phone 5/5 |
| 5 Tablets keep landscape (#102) | `partner-tablet-landscape-*.jpg` | the same flows on the tablet emulator | Tablet 5/5 |

There is no order-detail screen in portrait here: QA's kitchens were closed at the time of the run (after 1 am in
Hyderabad), so no kitchen had an order to open. The order detail on phones is the same card as the tablet's.

Item 3 (the simulator's own riders, #103, #108) has no screen: on QA after the reset, the worker logs show every
demo delivery carried by `rider.sim.*` riders (Hyderabad `rider.sim.hyd.1`, Boise `rider.sim.boi.1`), and the rider
app's flows signed in as the manual demo rider (`rider.demo.hyd`) pass 4/4 without it being given any.
