# BhojanGo Third-Party Integration Setup Guide

## 1. Stripe (USA Payments)

### Account Setup
1. Create account at [stripe.com](https://stripe.com)
2. Complete business verification (EIN, bank account)
3. Enable test mode for development

### API Keys (core-api only; never in GitHub)
- Dashboard → Developers → API Keys: `pk_test_*` (publishable) and `sk_test_*` (secret).
- core-api (Railway sealed variables):
  ```
  STRIPE_SECRET_KEY=sk_test_...
  STRIPE_PUBLISHABLE_KEY=pk_test_...     # handed to the web and app checkouts by the API
  STRIPE_WEBHOOK_SECRET=whsec_...        # from the webhook endpoint below
  PAYMENT_PROVIDER=auto                  # US -> Stripe when STRIPE_SECRET_KEY is set; India stays on the fake until Razorpay keys
  TAX_PROVIDER=auto                      # US sales tax from Stripe Tax when STRIPE_SECRET_KEY is set
  ```
- The website and the customer app need no Stripe variable: `POST /api/v1/payments/initiate`
  returns the publishable key and client secret (and the PaymentSheet customer + ephemeral
  key), `GET /api/v1/payments/provider?country=US` tells the app which checkout to open.
  The customer app's Stripe native module (`@stripe/stripe-react-native`, Google Pay enabled)
  needs a rebuilt APK.

### Webhook Setup
1. Dashboard → Developers → Webhooks → Add endpoint
2. URL: `https://<core-api host>/api/v1/payments/stripe/webhook`
3. Events (exactly `stripe_svc.WEBHOOK_EVENTS`):
   - `payment_intent.succeeded` (the order is placed)
   - `payment_intent.payment_failed`, `payment_intent.canceled` (the attempt failed; the order stays payable)
   - `charge.refunded`, `refund.created`, `refund.updated`, `refund.failed`, `charge.refund.updated` (refund status)
4. Copy the signing secret → `STRIPE_WEBHOOK_SECRET`. Deliveries are idempotent (`processed_webhook_events`).

### Idempotency
Every create at Stripe carries a key from our ids: Customer `cus:<user id>`, PaymentIntent
`<order id>:attempt-<n>`, Refund `refund:<refund id>` / `refund-in-full:<payment id>`, Tax calculation
`taxcalc:<quote id>`, Tax transaction `taxtx:<order id>`, Tax reversal `taxrev:<refund ref>`.

### Stripe Tax (US quotes)
The quote sends each cart line (prepared food, `txcd_40060003`) and each fee with the delivery
address; the fair bill's tax lines are Stripe's answer per jurisdiction. The calculation id is
kept with the quote and the order's pricing snapshot, turned into a tax transaction when the
payment succeeds, and reversed (partly) by refunds. Needs, in the Stripe account: Settings → Tax
→ head office address and default tax behaviour (`exclusive`), and a registration for every state
we deliver in (Dashboard → Tax → Registrations). Without a registration Stripe returns $0 with
`not_collecting` (the bill shows that $0 line); with Stripe Tax not set up, non-production quotes
show "Sales tax not calculated" ($0) and production refuses to quote (`payments/service/tax.py`).

### Testing
- GitHub CI: Stripe mocked (unit tests `payments/tests/test_stripe.py`, integration
  `core_api/integration/test_stripe_webhooks.py`).
- Real test mode: the `stripe-e2e` job on the Railway qa-runner (`tools/stripe_e2e/`, keys as
  sealed variables on the runner): `sh tools/railway/qa-runner.sh run stripe-e2e`.

## 2. Razorpay (India Payments)

### Account Setup
1. Create account at [razorpay.com](https://razorpay.com)
2. Complete KYC (PAN card, GST, bank verification)
3. Activate test mode

### API Keys
- Dashboard → Settings → API Keys → Generate
- Set in `.env`:
  ```
  RAZORPAY_KEY_ID=rzp_test_...
  RAZORPAY_KEY_SECRET=...
  ```

### Webhook Setup
1. Dashboard → Settings → Webhooks → Add New
2. URL: `https://api.bhojango.com/api/v1/payments/webhooks/razorpay`
3. Events: `payment.authorized`, `payment.captured`, `refund.processed`
4. Set `RAZORPAY_WEBHOOK_SECRET` from the webhook secret

### Testing
- Use test UPI ID: `success@razorpay`
- Test card: `4111 1111 1111 1111` (any future expiry, any CVV)

## 3. Twilio (SMS / OTP)

### Account Setup
1. Create account at [twilio.com](https://twilio.com)
2. Get Account SID and Auth Token from Console
3. Purchase phone numbers:
   - USA: +1 number for US OTPs
   - India: +91 number (requires DLT registration — see below)

### Environment Variables
```
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...       # USA
TWILIO_PHONE_NUMBER_IN=+91...   # India
```

### India DLT Registration
India requires DLT registration for SMS:
1. Register on your telecom provider's DLT portal
2. Register entity (business)
3. Register SMS headers (e.g., BHOJGO)
4. Register templates for OTP messages
5. Provide DLT registration IDs to Twilio

### Test Mode
Set `APP_ENV=test` to skip actual SMS sending — OTP will be logged to console.

## 4. Firebase Cloud Messaging (Push Notifications)

### Project Setup
1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create project "BhojanGo"
3. Add apps: iOS (bundle ID), Android (package name), Web

### Service Account
1. Project Settings → Service Accounts → Generate New Private Key
2. Download JSON key file
3. Set `FIREBASE_CREDENTIALS_JSON` in env (base64 encoded)

### APNs (iOS)
1. Apple Developer → Certificates → APNs Auth Key
2. Upload to Firebase → Project Settings → Cloud Messaging → iOS

### Testing
```bash
# Send test notification via FCM console
Firebase Console → Cloud Messaging → Send first message
```

## 5. Google Maps Platform

### API Key Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project → Enable APIs:
   - Maps JavaScript API
   - Places API
   - Geocoding API
   - Routes API
   - Distance Matrix API
3. Create API key → Restrict by HTTP referrer
4. Set `GOOGLE_MAPS_API_KEY` in env

### Budget Alerts
1. Billing → Budgets & Alerts → Create Budget
2. Set monthly budget ($200 recommended for dev)
3. Enable email alerts at 50%, 80%, 100%

## 6. SendGrid (Email)

### Account Setup
1. Create account at [sendgrid.com](https://sendgrid.com)
2. Verify sender domain (DNS records: CNAME, TXT)
3. Create API key with "Mail Send" permission only

### Environment Variables
```
SENDGRID_API_KEY=SG...
SENDGRID_FROM_EMAIL=noreply@bhojango.com
```

### Dynamic Templates
Create templates for:
- Order confirmation (template ID → `SENDGRID_ORDER_CONFIRMATION_TEMPLATE`)
- Delivery receipt
- OTP fallback (when SMS fails)
- Welcome email

## 7. AWS Cognito (Social Login Federation)

### User Pool Setup
1. AWS Console → Cognito → Create User Pool
2. Required attributes: email, name
3. Password policy: min 8 chars, uppercase, lowercase, number
4. MFA: Optional (SMS)

### App Client
1. Add app client (no client secret for mobile apps)
2. Set callback URLs:
   - `http://localhost:3000/auth/callback` (dev)
   - `https://bhojango.com/auth/callback` (prod)

### Identity Providers
**Google:**
1. Google Cloud Console → Credentials → OAuth 2.0 Client ID
2. Cognito → Federation → Identity Providers → Google
3. Enter Client ID and Client Secret

**Apple:**
1. Apple Developer → Services IDs → Configure Sign In with Apple
2. Cognito → Federation → Identity Providers → Apple
3. Enter Service ID, Team ID, Key ID, Private Key

### Environment Variables
```
COGNITO_USER_POOL_ID=us-east-1_...
COGNITO_CLIENT_ID=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
APPLE_CLIENT_ID=...
APPLE_TEAM_ID=...
APPLE_KEY_ID=...
```
