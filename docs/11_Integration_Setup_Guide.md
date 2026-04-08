# BhojanGo Third-Party Integration Setup Guide

## 1. Stripe (USA Payments)

### Account Setup
1. Create account at [stripe.com](https://stripe.com)
2. Complete business verification (EIN, bank account)
3. Enable test mode for development

### API Keys
- **Test keys:** Dashboard → Developers → API Keys
- Copy `pk_test_*` (publishable) and `sk_test_*` (secret)
- Set in `.env`:
  ```
  STRIPE_SECRET_KEY=sk_test_...
  STRIPE_PUBLISHABLE_KEY=pk_test_...
  ```

### Webhook Setup
1. Dashboard → Developers → Webhooks → Add endpoint
2. URL: `https://api.bhojango.com/api/v1/payments/webhooks/stripe`
3. Events to subscribe:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `charge.refunded`
   - `charge.refund.updated`
4. Copy signing secret → set `STRIPE_WEBHOOK_SECRET` in env

### Testing
```bash
stripe trigger payment_intent.succeeded  # Using Stripe CLI
```

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
