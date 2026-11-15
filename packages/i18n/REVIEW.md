# Translations: needs native review

English (`messages/en.json`) is the source. Every other language was
**machine-translated** on 2026-11-15 for the website rebuild (web v2) and
**needs native review** before launch in that language. Until a reviewer signs
a language off here, treat its wording as a draft. Prices, numbers and dates are
never translated: they follow the country (see `index.js`, `formatLocale`).

| Language | File | Country (Markets locale) | Status |
|---|---|---|---|
| हिन्दी Hindi | `hi.json` | India (hi-IN) | needs native review |
| తెలుగు Telugu | `te.json` | India (te-IN) | needs native review |
| தமிழ் Tamil | `ta.json` | India (ta-IN) | needs native review |
| ಕನ್ನಡ Kannada | `kn.json` | India (kn-IN) | needs native review |
| मराठी Marathi | `mr.json` | India (mr-IN) | needs native review |
| বাংলা Bengali | `bn.json` | India (bn-IN) | needs native review |
| Español Spanish | `es.json` | United States (es-US) | needs native review |

`node --test` (test/i18n.test.js) fails if any language misses an English key,
and `scripts/check.js` (the package's lint) fails on an empty string or a
`{placeholder}` that differs from English. A new English key needs a
translation in every file (mark it here) before CI passes.

## Look at these first (all languages)

- `notify.consent`: consent to one email. Legal wording; "ask us to forget you" was
  rendered as "ask us to delete your details" in most languages.
- `account.privacy.note`, `account.privacy.confirm_body`: deleting an account and
  keeping orders for tax records without personal details. Legal wording.
- `account.receipt.tax_invoice`: the Indian GST tax invoice (Spanish "Factura
  fiscal" must not read as a Mexican CFDI). Telugu uses the loanword, Kannada the
  native word for "tax": pick one style.
- `checkout.held`, `checkout.payment_failed`: "the price is held", "you weren't charged".
- `home.riders_body`, `ride.pay_floor_*`: the riders' hourly minimum ("floor").
- `signin.agree_before` / `agree_and`: sentence fragments around the Terms and
  Privacy links; word order differs from English, check them assembled.
- `common.test_site_banner`: the strip on every page outside production (QA, staging,
  local); it must say plainly that kitchens are demos and nothing is really ordered or paid.
- `checkout.card_ending`, `account.payments.ending`: "{brand} ending {last4}" word order.

## Per language

- **Hindi, Marathi:** brand line `common.tagline` / `home.hero_title`;
  `home.greeting_afternoon` (no natural "good afternoon": नमस्ते / नमस्कार);
  `account.notifications.toggle` ("{channel} से {kind}"); Marathi treats किचन as neuter.
- **Telugu, Kannada:** case suffixes glued to names (`{city}లో`, `{city}ಯಲ್ಲಿ`)
  don't suit every city name (Kannada: ನಲ್ಲಿ after -u/-a, e.g. a neutral
  "{city} ನಗರದಲ್ಲಿ"); `city.plainly_title`; short labels `kitchen.badge_spicy`,
  `account.report.reason_quality`.
- **Tamil, Bengali:** Tamil suffixes after a time (`{time}க்குத்`, e.g. "7:30 PMக்கு")
  and after names; Bengali writes digits in plain text in Bengali numerals;
  Bengali greeting নমস্কার vs হ্যালো; Tamil `city.breadcrumb` label.
- **Spanish:** bag = "carrito", dish = "platillo", rider = "repartidor";
  `checkout.fair_bill` "La cuenta justa" ("cuenta" also means account);
  `account.report.ordered`, `account.report.how_many`, `kitchen.one_less/one_more`
  (gender), `track.away` (distance vs time), `common.delivery_fee` word order.

## The Expo apps (round 4: `app.*`, `rider.*`, `partner.*`)

The apps read the same files (`all-messages.js` bundles every language for
Metro) and reuse the website's keys where the words are the same (`checkout.*`,
`bill.*`, `header.language*`, `signin.mobile`). Their own keys, machine-translated
on 2026-11-15, needing the same native review:

- `app.test_banner`: the test-site strip on every screen of a non-production build.
- `app.units.km` / `app.units.mi`: a distance with its unit ("{value} km"); local
  abbreviations (कि.मी., కి.మీ., ...) need checking.
- `app.bill.kitchens_treat`, `app.bill.on_us`: who pays for free delivery (the fair bill).
- `app.phone.country_code`, `app.phone.choose_country`: the phone's country box.
- `app.home.banner`, `app.out_of_area.cooking_in` ({cities} is a comma list of
  city names: Telugu/Tamil/Kannada/Bengali suffixes glued to the last name),
  `app.out_of_area.leave_number`.
- Customer account area (round 4): `app.account.*` ("Keep my account" in the delete
  confirmation), `app.orders.past`, `app.rating.change` / `app.rating.until` ({date}),
  `app.payments.saved` / `offered` ({country}: Telugu, Tamil, Kannada and Bengali put
  the name after a "·" instead of a suffix) / `offered_note`, `app.addresses.required`,
  `app.report.add_photo` / `uploading`. `app.pay.apple_pay` / `google_pay` are brand
  names, kept in English. Everything else in the account screens reuses the website's
  `account.*`, `rating.*` and `bill.*` keys.
- `rider.earnings.distance`, `partner.offer.amount_off` ({amount} is formatted
  money), `partner.offer.flat_off`.
- Customer app discovery, kitchen and tracking (round 4, machine-translated
  2026-11-15; the screens reuse the website's `home.*`, `offers.*`, `kitchen.*`,
  `track.*`, `favourites.*` keys where the words are the same):
  `app.home.*` (where you are, the greetings `hello` / `hello_name` / `ask` by part
  of the day, `finding_kitchens` with {place} (an area name: suffix languages),
  `cuisine_near` with {cuisine} (a cuisine name)), `app.search.no_match`,
  `app.item.customise`, `app.bag.held` ({time} is m:ss), `app.out_of_area.*`
  ({place}: suffixes in te/ta/kn/bn), `app.track.progress` / `step_*` (short labels
  under the progress bar: keep them to one or two words) / `pin_a11y` (read aloud).

## The partner app (round 4, B3: every `partner.*` key)

Every word in apps/partner is now a `partner.*` key (285 new, machine-translated
on 2026-11-15 into all seven languages; `partner.offer.*` was already there).
Reviewers, look first at:

- `partner.orders.*`: the tablet is read across a kitchen: the buttons must stay
  short (`partner.orders.busy_short`, `pause_short` are used on phones and small
  tablets); `partner.orders.minutes` "{min} min" and the column titles.
- `partner.apply.steps.*`: the application steps are named by the app from the
  step key; `*_gst` / `*_other` follow the country's tax regime (Markets
  `tax_regime`: FSSAI licence and GST where it is "gst", a food permit and tax
  elsewhere). `partner.apply.date_hint` "DD/MM/YYYY" is a format hint (Spanish: AAAA).
- `partner.photo.*`: the dish photo screen and its preview; `partner.photo.preview_photo_note`
  names the website's "Add" button (`common.add`) in each language.
- `partner.ratings.*`: "New" (`common.new`) until 5 ratings, as on the website;
  `partner.ratings.chip` "★ {stars} · {count} ratings" sits in the header: keep it short.
  Plurals: `chip_new`, `new_until`, `from`, `bar`, `stars_label`.
- `partner.offers.*_over` / `*_all`: an offer's description with an amount
  ({amount}, {off} are formatted money) and a percent ({percent}).
- `partner.help.sign_out_note`: signing out signs the account out on every device.
- Plurals: `partner.orders.today_orders`, `partner.orders.bags`, `partner.payouts.orders`,
  `partner.apply.steps.menu_detail` (one/other; Hindi, Bengali and Kannada use "one" for 0 too).
