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
- Round 5 (the partner app on phones, portrait): `partner.orders.ready_short` "Ready"
  (the third tab's label on a phone, beside a count: one short word; Spanish is
  plural, "Listos", for the orders), `partner.orders.open_order` "Open order {order}"
  (read aloud on an order in the phone's list; {order} is "#A1B2 · customer name").
- Plurals: `partner.orders.today_orders`, `partner.orders.bags`, `partner.payouts.orders`,
  `partner.apply.steps.menu_detail` (one/other; Hindi, Bengali and Kannada use "one" for 0 too).

## Backend messages and quick messages (round 5)

Every notification and quick message is now written in all eight languages
(machine-translated on 2026-11-15; Hindi and Telugu existed for the worker's
messages, Tamil, Kannada, Marathi, Bengali and Spanish are new). They live in
Python, not in these files, because the backend images can't read
`packages/` (their build context is `backend/`):

- `backend/worker/app/services/messages.py`: push title and body (SMS sends
  "BhojanGo: <body>", email wraps the same words): `order_placed`, `order_accepted`,
  `order_preparing`, `driver_assigned`, `order_picked_up`, `order_almost_there`,
  `order_message` (title only: "Message from {name}"), `order_delivered`,
  `order_cancelled_refunded`, `order_cancelled_unpaid`, `payment_failed`, `refund_items`,
  `partner_new_order`, `payout_paid`; `ARRIVING` ("Arriving around {eta}."), `ITEMS`
  ("{n} item(s)"), `EMAIL_FOOTER`, `EMAIL_TOTAL`, `EMAIL_ORDER`.
- `backend/shared/texts.py`: the quick messages `QUICK_PRESETS` (rider: `at_kitchen`,
  `on_my_way`, `outside`, `cant_find`, `running_late`; customer: `leave_at_door`,
  `coming_down`, `ring_bell`, `ask_guard`), `NAMES` (`your_rider`, `the_customer`,
  used when someone has no name), `OTP_SMS` (the sign-in code), `WELCOME` (the
  welcome email: `subject`, `hello`, `hello_anon`, `body`, `signoff`).
- `app.chat.*` here (the apps' message sheet): `title` "Message {name}", `new`
  (plural), `note`, `close`, `empty`.

`python tools/i18n/check_locales.py` (`make ci-i18n`, in GitHub's Repo checks)
fails if any of these, or any key in these files, is missing or empty in a
language that a live or beta country lists in Markets, or a backend text's
`{placeholders}` differ from English. Reviewers, look first at:

- **India SMS (DLT):** every SMS text must match its DLT-registered template word
  for word, so a reviewed wording has to be registered (or re-registered) with
  the operator before it goes live. Keys are `<message>_<language>` (e.g.
  `order_picked_up_ta`, `otp_bn`); the variables are the `{placeholders}` in order.
  SMS with Indic scripts or ₹ is UCS-2 (70 characters a part): the tests keep each
  message to three parts, which is why the Tamil cancellation and payment-failed
  bodies are shorter than English ("{restaurant} ஆர்டர் {code} ரத்தானது").
- **Gendered verbs (Hindi, Marathi):** a rider or customer can be anyone, so the
  quick messages avoid gendered first-person verbs: Hindi `at_kitchen` "...इंतज़ार है",
  `on_my_way` / `coming_down` use the plural "आ रहे हैं"; Marathi uses the neutral
  "येत आहे" / "पाहत आहे". Check they read naturally.
- **Names as subjects:** `{rider}` can be "Your rider" in the language
  (`NAMES.your_rider`) when the rider has no name: Hindi "आपका राइडर ने" should be
  oblique ("आपके राइडर ने"); check every language's sentences with the fallback.
- **Suffixes after {placeholders}:** Telugu/Kannada/Tamil/Bengali glue case suffixes
  to `{restaurant}`, `{code}`, `{period}`, `{eta}` (`{restaurant}ನಿಂದ`, `{code}-க்கு`,
  `{period}-এর`, `{eta}க்கு`): kitchen names ending in a consonant may need a joiner.
- **Spanish:** "tú" throughout (as on the website); `order_delivered` "Buen provecho.";
  `payment_failed` title "No se pudo cobrar"; `partner_new_order` "Acéptalo antes de
  las {accept_by}" assumes {accept_by} is a time.
- **Bengali numerals:** "৫–৭ দিন" in the refund messages, matching the website.
- **The email footer** keeps the English brand line "The honest table." in Spanish
  ("La mesa honesta"); the Indian languages use the tagline ("Real food. Fair prices.").

## Round 6

- `checkout.min_order` "The minimum order in {zone} is {amount}" (machine-translated
  2026-11-15): shown in the bag and at checkout when the bag is under the delivery
  area's minimum. {zone} is the area's name, {amount} is formatted by the country
  ("$15", "₹149"); check the word order around both in every language.

## Header and home (round 6: language pill, location line, who gets your money)

Machine-translated 2026-11-15: `header.language_pill` ("Language: {language}", the pill's
spoken name), `location.label`, `location.place` ("{city}, {country}": the country is the
2-letter code, kept as is), `location.change_city`, `cities.choose_title`, `cities.choose_note`,
`bill.example_in` ("On a {total} order in {city}": Indian languages glue a case suffix to
`{city}` and `{total}`; check with a city name ending in a consonant).

## Round 8 wording: delivery partner, kitchen partner, app names (E6)

People who deliver are **delivery partners** (never "rider", "driver" or "courier" in text a
person reads); restaurants are **kitchen partners** (or just "kitchen" where natural); the
apps are **BhojanGo**, **BhojanGo Kitchen** (was Partner) and **BhojanGo Delivery** (was
Rider). App names are brand names and stay in English in every language. Keys keep their
code names (`bill.rider`, `track.your_rider`, `ride.*`, `rider.*`); only the values changed.
`python tools/i18n/check_wording.py` (make ci-i18n) fails on "rider" (and its spellings
below) or an old app name in any message value, backend text, app name or app UI string.

| Language | delivery partner | to deliver | kitchen partner | was ("rider") |
|---|---|---|---|---|
| Hindi | डिलीवरी पार्टनर | डिलीवरी करें | किचन पार्टनर | राइडर |
| Telugu | డెలివరీ పార్ట్‌నర్ (-ల, -కు) | డెలివరీ చేయండి | కిచెన్ పార్ట్‌నర్ | రైడర్ |
| Tamil | டெலிவரி பார்ட்னர் (-கள், -ருக்கு) | டெலிவரி செய்யுங்கள் | கிச்சன் பார்ட்னர் | ரைடர் |
| Kannada | ಡೆಲಿವರಿ ಪಾರ್ಟ್ನರ್ (-ಗಳು, -ಗೆ) | ಡೆಲಿವರಿ ಮಾಡಿ | ಕಿಚನ್ ಪಾರ್ಟ್ನರ್ | ರೈಡರ್ |
| Marathi | डिलिव्हरी पार्टनर (-ला) | डिलिव्हरी करा | किचन पार्टनर | रायडर |
| Bengali | ডেলিভারি পার্টনার (-রা, -কে, -এর) | ডেলিভারি করুন | কিচেন পার্টনার | রাইডার |
| Spanish | repartidor (already in use: natural, and not "rider") | repartir | cocina asociada | rider |

Machine-translated 2026-11-15, all languages (needs native review): `header.ride_with_us`,
`footer.ride`, `signin.ride`, `home.riders_title`, `ride.meta_title`, `ride.title` ("Deliver
with BhojanGo"), `home.riders_eyebrow`, `ride.eyebrow` ("For delivery partners"),
`home.riders_cta` ("Start delivering"), `bill.rider` ("Delivery partner"), `bill.rider_tip`
("Delivery partner + tip", the "Who gets your money" card), `bill.line_tip`,
`home.step3_body`, `home.order_rider`, `city.faq_tip_a`, `city.faq_tip_presets`,
`city.soon_body`, `checkout.rider_note`, `checkout.tip_title`, `checkout.tip_note`,
`track.pin_long`, `track.s_finding`, `track.your_rider`, `track.rider_card`,
`track.map_rider`, `signin.partner_q`, `signin.partner_note` ("Kitchens use BhojanGo
Kitchen; delivery partners use BhojanGo Delivery."), `signin.promise_tip`,
`account.addresses.location_hint`, `meta.description`, `ride.pay_more`, `ride.apply_step1`,
`ride.apply_note`, `app.track.pin_a11y`, `app.bill.on_us` ("BhojanGo's treat": free delivery
BhojanGo pays for, next to "Kitchen's treat"), `rider.brand` / `partner.brand` (the app
names, English everywhere), `rider.sign_in.hero`, `rider.code.wrong_account`,
`rider.join.title`, `rider.join.city`, `rider.checklist.ready_title`,
`rider.checklist.almost_title`, `rider.document.private`, `rider.drive.notice_body` ("ride"
became "deliver"), `partner.split.sub`, `partner.sign_in.sub`, `partner.code.wrong_account`,
`partner.apply.title` ("Kitchen partner application"), `partner.apply.menu_note` ("account
manager"), `partner.orders.ready_note`, `partner.orders.finding_rider`, `partner.help.support`
("Kitchen partner support"). Backend: `names.your_rider` ("Your delivery partner", the name
in push/SMS/chat when a delivery partner has none) and `driver_assigned.title` ("Delivery
partner on the way to the kitchen").

## Round 8 (location line and Change city)

Machine-translated 2026-11-15: `location.set` ("Set your delivery location": a button that
opens the address box), `location.delivers_here` ("We deliver here", after the visitor's
town from their IP), `cities.other_countries` (the "Other countries" disclosure on Change
city), `cities.no_match_in` ("No city in {country} by that name yet.": `{country}` is the
country's Markets name in English; Indian languages glue a case suffix to it).

## Sign-in emails (round 8, D5)

Machine-translated on 2026-11-15, all eight languages, in `backend/shared/texts.py`
`AUTH_EMAILS`: the 6-digit code email (`code.subject`, `code.body`), "you already
have an account" (`exists.*`), the password-reset link (`reset.*`), "your password
was changed" (`changed.*`) and "the email on your account was changed"
(`email_replaced.*`). Check that the reset and changed emails read as calm and
trustworthy (no alarm, no blame), and that "code" / "password" use the words people
know from other apps in each language.

## Deliver with BhojanGo (round 8, F8: `deliver_page.*`)

Every `deliver_page.*` key (the website's /deliver and /deliver/app pages: pay, requirements,
how it works, the get-started form, FAQ) was machine-translated on 2026-11-15 in all seven
languages and needs native review. Look at these first:

- `pay_cadence_body`, `pay_weekly_title`: `{day}` is a weekday name already in the page's
  language (Intl, e.g. "సోమవారం"); check the case ending around it.
- `pay_trip_body`, `faq_pay_a`: `{unit}` is the short unit Intl writes ("km", "mi" or the
  script's own form); `{base}`, `{per_unit}`, `{per_minute}` are formatted money.
- `hero_card_title`, `pay_title`, `pay_note`, `req_sub`, `req_age_body`, `faq_vehicle_a`:
  `{city}` / `{country}` come from Markets in English ("Hyderabad", "India"); Telugu, Tamil,
  Bengali and Marathi glue a case ending to them, Kannada writes "{city} ನಗರದಲ್ಲಿ".
- `doc_*`: the document names must match the BhojanGo Delivery app's checklist words.
  "Driving licence" (India) and "Driver's license" (US) translate the same in the Indian
  languages; Tamil avoids ஓட்டுநர் உரிமம் (it contains the word for "driver").
- `gs_terms`: "{terms}" and "{privacy}" become links named by `gs_terms_link` and
  `gs_privacy_link`; Spanish matches their gender ("los Términos…", "la Política…").
- `gs_err_*`: the sign-up refusals (a number that orders food, a kitchen or admin account,
  a city we don't serve).

## Round 8: not-found and error pages (workstream P)

Machine-translated 2026-11-15: `errors.title_404`, `errors.body_404`, `errors.title_error`,
`errors.body_error`, `errors.try_again`, `errors.go_home`, `errors.where_we_deliver`,
`errors.help`, `errors.popular` (the website's 404 and error pages). The tone is informal
and reassuring ("It's not you"); check Hindi/Marathi/Bengali read as polite, and that
`errors.help` matches the footer's "Help centre" wording in each language.

## Round 8: cancelling an order (workstream P)

Machine-translated 2026-11-15: `track.cancel`, `track.cancel_until` ({time} is a clock time),
`track.cancel_before_accept`, `track.cancel_title`, `track.cancel_refund` ({amount} is formatted
money, {method} the payment method's label from `account.pay.*`: "UPI", "Card"; Indian languages
glue a case suffix to `{method}`), `track.cancel_nothing`, `track.cancel_yes`, `track.cancel_keep`,
`track.cancelling`, `track.cancel_too_late`, `track.cancel_failed`, `track.refunded`,
`track.refund_pending`. Check the confirmation reads as a calm question, not a warning.

## Add your kitchen (round 8, F7: every `kitchen_join.*` key)

Machine-translated 2026-11-15, all 7 languages: the /partner landing page, the
application form and the application steps on the web. Look at these first:
`kitchen_join.consent` (legal: agreeing to the Terms and the Privacy policy; `{terms}`
and `{privacy}` become links, so each language may move them), `kitchen_join.customer_body`
(an account that becomes a kitchen's can no longer order food), the FAQ answers
(`faq_*_a`: fees, payouts, approval; they describe the product, no promises of time),
and `why_payout_body` (plural on the hold days). Backend: `kitchen_applied.*` in
`backend/shared/texts.py` (the email a new kitchen partner gets). The documents list on the
page (FSSAI, GSTIN, PAN, bank; health permit, EIN, bank) is Markets data seeded in
`tools/seed/data.py` with its own translations, editable in admin Markets -> country.

## Help centre (round 8 F9)

Machine-translated 2026-11-15: all `helpcentre.*` keys (the /help page: search, topics,
article pages, the "Was this helpful?" vote and the contact-support form). Needs native
review. Points to check:
- **Terms:** "article" is लेख / కథనం / கட்டுரை / ಲೇಖನ / लेख / আর্টিকেল / artículo;
  "support" follows the existing `account.report.ticket` wording (सपोर्ट, సపోర్ట్,
  உதவிக் குழு, ಸಪೋರ್ಟ್, सपोर्ट, সাপোর্ট, soporte); "payouts" is transliterated
  (पेआउट, పేఅవుట్, ...), Spanish "pagos".
- **Suffixes after {placeholders}:** `in_topic`, `fallback_note` ({language}),
  `results_for` / `no_results_title` ({query} in quotes) glue case suffixes in
  Telugu/Bengali (`{topic}లో`, `{topic}-এ`, `“{query}”-এর`); check with real topic and
  language names.
- **Plurals:** Hindi/Marathi/Bengali use the same form for one and other where the noun
  doesn't change; Bengali uses "১০" in `form_invalid`.
- **Spanish:** "tú" throughout; kitchen partners are "Cocinas asociadas", delivery
  partners "Socios repartidores".

## Terms and Privacy pages (round 8, F10)

Machine-translated 2026-11-15: the whole `legal.*` group, the chrome around the Terms of use
and Privacy notice (the documents themselves are English for now; other languages show
`legal.english_only`). Check first:

- `legal.draft_banner` "Draft: pending legal review": shown on every legal page outside
  production; it must read as "not final, a lawyer still has to approve it".
- `legal.unavailable` "{country}: we're preparing our {document}. ...": {document} is
  `legal.terms` or `legal.privacy` (Indian languages may need a case suffix on it).
- `legal.notice_updated` / `legal.notice_agree`: the strip a signed-in person sees once after
  a new version is published; "By continuing to use BhojanGo you agree to the new versions" is
  legal wording.
- `legal.older`, `legal.history_replaced`, `legal.history_effective`: {date} is formatted by the
  country ("20 November 2026"); check the word order around it.

## Apps: can't reach BhojanGo (round 9)

Machine-translated 2026-11-16: `app.load_error.*`, the error state every app screen shows when
its data can't load (no connection, our servers too slow or down), with its Retry button.
Check first: `title` names the brand ("Can't reach BhojanGo"); `offline` must not blame the
person ("we couldn't connect"); `retry` is a button label, short enough for a 160 px button.
Spanish uses "Reintentar" for the button and "tú" in the sentences.

Also machine-translated 2026-11-16: `app.payment_failed.*`, the customer app's "Payment didn't go
through" screen (it was English-only). `not_charged` is a promise about money: check it says
"you have not been charged" and that the bank reverses any hold, nothing more. "UPI" stays as is.

## Delivery partner sign-up: age and vehicle (round 9)

Machine-translated on 2026-11-16 into all seven languages; needs native review.

- Changed: `rider.checklist.detail.background_progress`, `background_waiting`,
  `needed_background_check`, `deliver_page.doc_background_check_body`,
  `deliver_page.faq_approval_a` ("usually 2–5 days" became "We'll let you know by
  SMS and email"; the product owner's wording), `deliver_page.step1_body` (now lists
  date of birth and vehicle).
- New, website: `deliver_page.gs_dob`, `gs_dob_help`, `gs_dob_under`, `gs_dob_invalid`,
  `gs_vehicle`, `gs_err_vehicle`, `gs_rules_failed`. New, BhojanGo Delivery app:
  `rider.join.dob`, `dob_day`, `dob_month`, `dob_year`, `dob_help`, `dob_under`,
  `dob_invalid`, `vehicle`, `rules_failed`. `{age}` is the country's minimum age in
  years (Markets); check "{age} or older" reads naturally with a number in each language.
- `gs_dob_help` / `rider.join.dob_help` promise we use the date of birth only to check
  the age: legal wording, keep it that narrow.
- Backend (shared/texts.py `DELIVERY_SIGN_UP`): `under_age`, `vehicle`, `dob`, the
  refusals POST /riders/apply sends in the form's language.
- Help article `become-a-delivery-partner` (en, hi, es seed): the sign-up step and the
  background-check line changed to match.
- Report a problem (round 9 page review): `account.report.photo_add`, `photo_remove`
  (the page's own photo button, replacing the browser's untranslated "Choose File")
  and `account.report.need` (why Send report is still greyed out).

## US payments through Stripe (round 10)

Machine-translated on 2026-11-16 into all seven languages; needs native review.

- New, website and customer app: `checkout.stripe_title`, `stripe_loading`, `stripe_unavailable`,
  `stripe_note`, `stripe_test_hint`, `return_title`, `return_body`, `return_slow_title`,
  `return_failed_title`, `return_missing`, `back_to_checkout`, `view_order`, `stripe_update_app`.
- `stripe_note` is a promise about card data ("BhojanGo never sees your full card number"):
  keep it that narrow. `stripe_test_hint` shows only with a Stripe test key; the card number
  4242 4242 4242 4242 stays in Latin digits in every language (it is typed as is).
- "Stripe", "BhojanGo", "CVC" and "Google Pay" stay in Latin script.

## Kitchen app Help: call-back request didn't load (round 10)

Machine-translated on 2026-11-16 into all seven languages; needs native review.

- New, BhojanGo Kitchen app: `partner.help.earlier_failed`, the title of the error (with
  Retry) when the kitchen's open call-back request can't be loaded.
