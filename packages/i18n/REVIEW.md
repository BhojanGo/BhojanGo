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

## The rider app (round 4, B2: every `rider.*` key)

Every word in apps/rider is now a `rider.*` key (243 new, machine-translated on
2026-11-15 into all seven languages; `rider.earnings.distance` was already there).
Reviewers, look first at:

- `rider.checklist.steps.*` / `rider.checklist.detail.*`: the onboarding steps are
  named by the app now, not the API, so one name serves every country (India's
  "Vehicle RC and insurance" became the general "Vehicle insurance": native
  reviewers may want the local document's name).
- `rider.offer.*`: the offer sheet is read in a few seconds: short words matter
  (`rider.offer.batch_title` is capitals in English; Indic scripts have no case).
  `rider.offer.minutes` "~{min} min", `rider.offer.per_hour` "{amount}/hr" and
  `rider.earnings.hours` "{value} h" use local abbreviations (मिनट, నిమి, நிமி, ...).
- `rider.earnings.floor_in`, `rider.earnings.below_floor`, `rider.earnings.above_floor`
  follow a bold amount ("{amount} per active hour floor" + "in {city}. ..."): the
  two pieces must read as one sentence; Telugu/Tamil/Kannada/Bengali suffixes are
  glued to {city} (`{city}లో`, `{city} இல்`, `{city} ನಲ್ಲಿ`, `{city}-এ`).
- `rider.sos.*`: the emergency number ({number}) is Markets data (`emergency_number`
  in the country's settings); `rider.sos.intro_local` is said when a country has none.
- `rider.drive.elsewhere_*`: shown when the rider is online on another device (or
  the QA demo simulator drives the demo rider): plain wording matters.
- `rider.account.sign_out_note`: signing out signs out every device (the API's
  logout revokes every session).
- Plurals: `rider.offer.bags`, `rider.offer.seconds_left`, `rider.delivery.items`,
  `rider.payouts.deliveries` (one/other; Hindi, Bengali and Kannada use "one" for 0 too).

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
- `rider.earnings.distance`, `partner.offer.amount_off` ({amount} is formatted
  money), `partner.offer.flat_off`.
