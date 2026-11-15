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
