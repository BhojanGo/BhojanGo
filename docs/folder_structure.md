# Project Folder Structure

```text
BhojanGo/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── pr-checks.yml
│   │   └── security.yml
│   ├── CODEOWNERS
│   └── pull_request_template.md
├── apps/
│   ├── admin/
│   │   ├── src/
│   │   │   ├── app/
│   │   │   │   ├── analytics/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── dashboard/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── drivers/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── login/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── orders/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── pain-points/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── payments/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── pricing/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── restaurants/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── users/
│   │   │   │   │   └── page.tsx
│   │   │   │   ├── globals.css
│   │   │   │   ├── layout.tsx
│   │   │   │   └── page.tsx
│   │   │   ├── components/
│   │   │   │   ├── layout/
│   │   │   │   │   └── AdminLayout.tsx
│   │   │   │   └── providers.tsx
│   │   │   ├── lib/
│   │   │   │   └── api.ts
│   │   │   └── store/
│   │   │       └── auth.ts
│   │   ├── .env.local
│   │   ├── .eslintrc.json
│   │   ├── next-env.d.ts
│   │   ├── next.config.mjs
│   │   ├── package.json
│   │   ├── postcss.config.js
│   │   ├── tailwind.config.ts
│   │   ├── tsconfig.json
│   │   └── tsconfig.tsbuildinfo
│   ├── mobile/
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   │   ├── _layout.tsx
│   │   │   │   ├── login.tsx
│   │   │   │   └── signup.tsx
│   │   │   ├── (driver-tabs)/
│   │   │   │   ├── _layout.tsx
│   │   │   │   ├── active.tsx
│   │   │   │   ├── earnings.tsx
│   │   │   │   ├── home.tsx
│   │   │   │   └── profile.tsx
│   │   │   ├── (tabs)/
│   │   │   │   ├── _layout.tsx
│   │   │   │   ├── index.tsx
│   │   │   │   ├── orders.tsx
│   │   │   │   ├── profile.tsx
│   │   │   │   └── search.tsx
│   │   │   ├── order/
│   │   │   │   └── [id].tsx
│   │   │   ├── restaurant/
│   │   │   │   └── [id].tsx
│   │   │   ├── _layout.tsx
│   │   │   ├── cart.tsx
│   │   │   ├── checkout.tsx
│   │   │   └── wallet.tsx
│   │   ├── src/
│   │   │   ├── lib/
│   │   │   │   └── api.ts
│   │   │   └── store/
│   │   │       ├── auth.ts
│   │   │       └── cart.ts
│   │   ├── app.json
│   │   ├── babel.config.js
│   │   ├── package.json
│   │   ├── tailwind.config.js
│   │   └── tsconfig.json
│   └── web/
│       ├── e2e/
│       │   ├── .auth/
│       │   │   └── customer-state.json
│       │   ├── utils/
│       │   ├── .gitkeep
│       │   ├── auth.setup.ts
│       │   ├── cart.spec.ts
│       │   ├── checkout.spec.ts
│       │   ├── home.spec.ts
│       │   ├── orders.spec.ts
│       │   ├── profile.spec.ts
│       │   ├── restaurants.spec.ts
│       │   ├── utils.ts
│       │   └── wallet.spec.ts
│       ├── messages/
│       │   ├── en-IN.json
│       │   ├── en-US.json
│       │   └── hi-IN.json
│       ├── public/
│       │   └── images/
│       │       ├── menu/
│       │       │   ├── food_1.jpg
│       │       │   ├── food_10.jpg
│       │       │   ├── food_11.jpg
│       │       │   ├── food_12.jpg
│       │       │   ├── food_13.jpg
│       │       │   ├── food_14.jpg
│       │       │   ├── food_15.jpg
│       │       │   ├── food_16.jpg
│       │       │   ├── food_17.jpg
│       │       │   ├── food_18.jpg
│       │       │   ├── food_19.jpg
│       │       │   ├── food_2.jpg
│       │       │   ├── food_20.jpg
│       │       │   ├── food_21.jpg
│       │       │   ├── food_22.jpg
│       │       │   ├── food_23.jpg
│       │       │   ├── food_24.jpg
│       │       │   ├── food_25.jpg
│       │       │   ├── food_26.jpg
│       │       │   ├── food_27.jpg
│       │       │   ├── food_28.jpg
│       │       │   ├── food_29.jpg
│       │       │   ├── food_3.jpg
│       │       │   ├── food_30.jpg
│       │       │   ├── food_4.jpg
│       │       │   ├── food_5.jpg
│       │       │   ├── food_6.jpg
│       │       │   ├── food_7.jpg
│       │       │   ├── food_8.jpg
│       │       │   └── food_9.jpg
│       │       └── restaurants/
│       │           ├── amritsar-dhaba-hyderabad.jpg
│       │           ├── andhra-spice-pune.jpg
│       │           ├── bangkok-basil-los-angeles.jpg
│       │           ├── bbq-brothers-miami.jpg
│       │           ├── bbq-smokehouse-austin.jpg
│       │           ├── biryani-house-bengaluru.jpg
│       │           ├── biryani-house-mumbai.jpg
│       │           ├── biryani-house-pune.jpg
│       │           ├── burger-king-austin.jpg
│       │           ├── burger-king-boston.jpg
│       │           ├── burger-king-dallas.jpg
│       │           ├── burger-king-san-diego.jpg
│       │           ├── burrito-blaze-austin.jpg
│       │           ├── cairo-kitchen-phoenix.jpg
│       │           ├── canton-dim-sum-miami.jpg
│       │           ├── chaat-corner-pune.jpg
│       │           ├── chennai-chaat-house-jaipur.jpg
│       │           ├── chipotle-fresh-houston.jpg
│       │           ├── crepe-station-chicago.jpg
│       │           ├── dominos-pizza-chicago.jpg
│       │           ├── dominos-pizza-houston.jpg
│       │           ├── dominos-pizza-new-york.jpg
│       │           ├── dominos-pizza-san-antonio.jpg
│       │           ├── dominos-pizza-seattle.jpg
│       │           ├── dosa-express-bengaluru.jpg
│       │           ├── dosa-express-mumbai.jpg
│       │           ├── dosa-express-pune.jpg
│       │           ├── dunkin-donuts-chicago.jpg
│       │           ├── dunkin-donuts-los-angeles.jpg
│       │           ├── dunkin-donuts-phoenix.jpg
│       │           ├── dunkin-donuts-san-diego.jpg
│       │           ├── dunkin-donuts-seattle.jpg
│       │           ├── goan-flavors-chennai.jpg
│       │           ├── gujarati-thali-mumbai.jpg
│       │           ├── haldirams-bengaluru.jpg
│       │           ├── haldirams-mumbai.jpg
│       │           ├── haldirams-pune.jpg
│       │           ├── hatti-kaapi-bengaluru.jpg
│       │           ├── hatti-kaapi-mumbai.jpg
│       │           ├── hatti-kaapi-pune.jpg
│       │           ├── hawaiian-poke-new-york.jpg
│       │           ├── hyderabad-dum-hyderabad.jpg
│       │           ├── jaipur-junction-bengaluru.jpg
│       │           ├── karnataka-kitchen-delhi.jpg
│       │           ├── kathi-junction-bengaluru.jpg
│       │           ├── kathi-junction-mumbai.jpg
│       │           ├── kathi-junction-pune.jpg
│       │           ├── kerala-spice-chennai.jpg
│       │           ├── kfc-houston.jpg
│       │           ├── kfc-phoenix.jpg
│       │           ├── kfc-san-diego.jpg
│       │           ├── korean-bbq-house-phoenix.jpg
│       │           ├── maharajas-kitchen-bengaluru.jpg
│       │           ├── mamas-italian-miami.jpg
│       │           ├── mcdonalds-los-angeles.jpg
│       │           ├── mcdonalds-san-diego.jpg
│       │           ├── mcdonalds-seattle.jpg
│       │           ├── mexico-lindo-new-york.jpg
│       │           ├── milan-express-atlanta.jpg
│       │           ├── mysore-palace-kolkata.jpg
│       │           ├── noodle-nirvana-seattle.jpg
│       │           ├── north-indian-junction-jaipur.jpg
│       │           ├── patty-melt-philadelphia.jpg
│       │           ├── pizza-hut-dallas.jpg
│       │           ├── pizza-hut-miami.jpg
│       │           ├── ramen-yama-phoenix.jpg
│       │           ├── ribs-&-rubs-dallas.jpg
│       │           ├── saravana-bhavan-bengaluru.jpg
│       │           ├── saravana-bhavan-mumbai.jpg
│       │           ├── saravana-bhavan-pune.jpg
│       │           ├── sindhi-sweets-pune.jpg
│       │           ├── south-indian-sambar-kochi.jpg
│       │           ├── spice-garden-mumbai.jpg
│       │           ├── starbucks-new-york.jpg
│       │           ├── starbucks-phoenix.jpg
│       │           ├── starbucks-san-diego.jpg
│       │           ├── subway-houston.jpg
│       │           ├── subway-miami.jpg
│       │           ├── subway-new-york.jpg
│       │           ├── subway-phoenix.jpg
│       │           ├── taco-bell-miami.jpg
│       │           ├── taco-bell-philadelphia.jpg
│       │           ├── taco-bell-san-antonio.jpg
│       │           ├── tamil-nadu-delights-bengaluru.jpg
│       │           ├── tamil-taste-chennai.jpg
│       │           ├── thai-orchid-boston.jpg
│       │           ├── tokyo-ramen-dallas.jpg
│       │           └── wok-&-roll-philadelphia.jpg
│       ├── src/
│       │   ├── app/
│       │   │   ├── (auth)/
│       │   │   │   ├── forgot-password/
│       │   │   │   │   └── page.tsx
│       │   │   │   ├── login/
│       │   │   │   │   └── page.tsx
│       │   │   │   └── signup/
│       │   │   │       └── page.tsx
│       │   │   ├── cart/
│       │   │   │   └── page.tsx
│       │   │   ├── checkout/
│       │   │   │   ├── payment/
│       │   │   │   │   └── page.tsx
│       │   │   │   └── page.tsx
│       │   │   ├── help/
│       │   │   │   └── page.tsx
│       │   │   ├── orders/
│       │   │   │   ├── [id]/
│       │   │   │   │   └── page.tsx
│       │   │   │   └── page.tsx
│       │   │   ├── privacy/
│       │   │   │   └── page.tsx
│       │   │   ├── profile/
│       │   │   │   └── page.tsx
│       │   │   ├── restaurants/
│       │   │   │   ├── [id]/
│       │   │   │   │   └── page.tsx
│       │   │   │   └── page.tsx
│       │   │   ├── support/
│       │   │   │   └── page.tsx
│       │   │   ├── terms/
│       │   │   │   └── page.tsx
│       │   │   ├── wallet/
│       │   │   │   └── page.tsx
│       │   │   ├── globals.css
│       │   │   ├── layout.tsx
│       │   │   ├── page.tsx
│       │   │   ├── robots.ts
│       │   │   └── sitemap.ts
│       │   ├── components/
│       │   │   ├── home/
│       │   │   │   ├── FeaturedRestaurants.tsx
│       │   │   │   ├── HeroSection.tsx
│       │   │   │   └── HowItWorks.tsx
│       │   │   ├── layout/
│       │   │   │   ├── Footer.tsx
│       │   │   │   └── Navbar.tsx
│       │   │   ├── restaurant/
│       │   │   │   └── RestaurantCard.tsx
│       │   │   └── providers.tsx
│       │   ├── i18n/
│       │   │   └── request.ts
│       │   ├── lib/
│       │   │   └── api.ts
│       │   └── store/
│       │       ├── auth.ts
│       │       └── cart.ts
│       ├── test-results/
│       │   └── .last-run.json
│       ├── .env.local
│       ├── .eslintrc.json
│       ├── next-env.d.ts
│       ├── next.config.mjs
│       ├── package.json
│       ├── playwright.config.ts
│       ├── postcss.config.js
│       ├── tailwind.config.ts
│       ├── tsconfig.json
│       └── tsconfig.tsbuildinfo
├── docs/
│   ├── adr/
│   │   ├── ADR-001-monorepo-turborepo.md
│   │   ├── ADR-002-fastapi-python.md
│   │   ├── ADR-003-dynamodb-driver-locations.md
│   │   ├── ADR-004-razorpay-india-payments.md
│   │   ├── ADR-005-sns-sqs-messaging.md
│   │   ├── ADR-006-expo-react-native.md
│   │   ├── ADR-007-cognito-auth.md
│   │   ├── ADR-008-kong-api-gateway.md
│   │   ├── ADR-009-opensearch-restaurant-search.md
│   │   └── ADR-010-ecs-fargate-vs-eks.md
│   ├── 09_Testing_Strategy.md
│   ├── 10_Operations_Runbook.md
│   ├── 11_Integration_Setup_Guide.md
│   ├── BATCH_ENGINE_TECHNICAL_DESIGN.md
│   └── BHOJANGO_PLATFORM_TECHNICAL_DESIGN.md
├── generated/
│   ├── BhojanGo_Novel_Delivery_Engine_Ideas.md
│   ├── BhojanGo_Project_Report.md
│   ├── BhojanGo_Unique_Value_Assessment.md
│   ├── kimchi-session-2026-06-12T19-48-25-378Z_019ebd60-e8a2-7bac-93a6-e85ce3a87ac2.html
│   ├── Micro_Audit_BhojanGo.md
│   ├── Micro_Audit_BhojanGo_v2.md
│   └── start-all.sh
├── implementation_plan/
│   ├── .DS_Store
│   ├── IP.ND.01 - Generic Clone.md
│   ├── IP.ND.02 - Light Cosmetic Difference.md
│   ├── IP.ND.03 - Small Convenience Features.md
│   ├── IP.ND.04 - Demo Level Differentiation.md
│   ├── IP.ND.05 - Retention Focused Uniqueness.md
│   ├── IP.ND.06 - Marketplace Specific Differentiation.md
│   ├── IP.ND.07 - Smart Personalization.md
│   ├── IP.ND.08 - Strong Product Identity.md
│   ├── IP.ND.09 - Defensible Differentiation.md
│   ├── IP.ND.10 - Category Leading Experience.md
│   ├── IP.PR.01 - Broken Shell.md
│   ├── IP.PR.02 - Browsable Prototype.md
│   ├── IP.PR.03 - Partial Core Flow.md
│   ├── IP.PR.04 - Internal Demo Core Loop.md
│   ├── IP.PR.05 - Usable Closed Demo.md
│   ├── IP.PR.06 - Closed Beta Marketplace.md
│   ├── IP.PR.07 - Reliable Beta Product.md
│   ├── IP.PR.08 - Early Production Ready.md
│   ├── IP.PR.09 - Production Grade Competitive App.md
│   ├── IP.PR.10 - Mature Marketplace Platform.md
│   └── SP20-Master-Implementation-Sprint-Plan.md
├── infra/
│   ├── db/
│   │   └── init.sql
│   ├── kong/
│   │   └── kong.yml
│   ├── localstack/
│   │   └── init-aws.sh
│   └── terraform/
│       ├── modules/
│       │   ├── alb/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   ├── cloudwatch/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   ├── cognito/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   ├── ecr/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   ├── ecs/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   ├── iam/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   ├── kms/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   ├── opensearch/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   ├── rds/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   ├── redis/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   ├── s3/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   ├── secrets/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   ├── security_groups/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   ├── sqs_sns/
│       │   │   ├── main.tf
│       │   │   ├── outputs.tf
│       │   │   └── variables.tf
│       │   └── vpc/
│       │       ├── main.tf
│       │       ├── outputs.tf
│       │       └── variables.tf
│       ├── main.tf
│       ├── outputs.tf
│       └── variables.tf
├── logs/
├── packages/
│   ├── config/
│   │   ├── eslint.js
│   │   ├── package.json
│   │   ├── prettier.config.js
│   │   ├── tsconfig.base.json
│   │   ├── tsconfig.nextjs.json
│   │   └── tsconfig.react-native.json
│   ├── types/
│   │   ├── src/
│   │   │   ├── api.ts
│   │   │   ├── delivery.ts
│   │   │   ├── events.ts
│   │   │   ├── index.ts
│   │   │   ├── notification.ts
│   │   │   ├── order.ts
│   │   │   ├── payment.ts
│   │   │   ├── restaurant.ts
│   │   │   └── user.ts
│   │   ├── package.json
│   │   └── tsconfig.json
│   └── ui/
│       ├── src/
│       │   ├── components/
│       │   │   ├── Badge.tsx
│       │   │   ├── Button.tsx
│       │   │   ├── Card.tsx
│       │   │   ├── Input.tsx
│       │   │   ├── Modal.tsx
│       │   │   └── Spinner.tsx
│       │   ├── lib/
│       │   │   └── utils.ts
│       │   └── index.ts
│       ├── package.json
│       └── tsconfig.json
├── review_exports/
│   ├── .DS_Store
│   └── SPR-01_scope_review_v2.zip
├── scripts/
│   ├── seed/
│   │   ├── comprehensive_seed.py
│   │   ├── comprehensive_seed.sql
│   │   ├── run_all.sh
│   │   ├── seed_orders.py
│   │   ├── seed_restaurants.py
│   │   └── seed_users.py
│   ├── create_folder_structure.py
│   └── start-all.sh
├── services/
│   ├── batch-engine/
│   │   ├── src/
│   │   │   ├── api/
│   │   │   │   ├── middleware/
│   │   │   │   │   ├── auth.ts
│   │   │   │   │   └── validation.ts
│   │   │   │   ├── batch.controller.ts
│   │   │   │   └── routes.ts
│   │   │   ├── config/
│   │   │   │   └── index.ts
│   │   │   ├── db/
│   │   │   │   ├── migrations/
│   │   │   │   │   └── 001_create_batch_tables.sql
│   │   │   │   ├── repositories/
│   │   │   │   │   ├── batch.repository.ts
│   │   │   │   │   └── order-pool.repository.ts
│   │   │   │   └── connection.ts
│   │   │   ├── dto/
│   │   │   │   └── batch.dto.ts
│   │   │   ├── engine/
│   │   │   │   ├── batch-builder.ts
│   │   │   │   ├── batch-scorer.ts
│   │   │   │   └── route-optimizer.ts
│   │   │   ├── events/
│   │   │   │   ├── consumer.ts
│   │   │   │   └── publisher.ts
│   │   │   ├── services/
│   │   │   │   └── batch.service.ts
│   │   │   ├── types/
│   │   │   │   └── index.ts
│   │   │   ├── utils/
│   │   │   │   ├── geo.ts
│   │   │   │   └── logger.ts
│   │   │   └── main.ts
│   │   ├── tests/
│   │   │   ├── batch-creation.test.ts
│   │   │   └── batch-scorer.test.ts
│   │   ├── .env.example
│   │   ├── Dockerfile
│   │   ├── package-lock.json
│   │   ├── package.json
│   │   └── tsconfig.json
│   ├── delivery-svc/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── v1/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── delivery.py
│   │   │   │   │   ├── earnings.py
│   │   │   │   │   └── websocket.py
│   │   │   │   └── __init__.py
│   │   │   ├── core/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py
│   │   │   │   └── redis.py
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── delivery.py
│   │   │   │   └── earnings.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── dynamodb.py
│   │   │   │   ├── earnings.py
│   │   │   │   ├── eta.py
│   │   │   │   └── shifts.py
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── test_earnings.py
│   │   │   └── test_eta.py
│   │   ├── .dockerignore
│   │   ├── .env
│   │   ├── Dockerfile
│   │   ├── poetry.lock
│   │   └── pyproject.toml
│   ├── notification-svc/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── v1/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── notifications.py
│   │   │   │   └── __init__.py
│   │   │   ├── core/
│   │   │   │   ├── __init__.py
│   │   │   │   └── auth.py
│   │   │   ├── db/
│   │   │   │   ├── migrations/
│   │   │   │   │   ├── versions/
│   │   │   │   │   │   └── 0001_create_notification_tables.py
│   │   │   │   │   └── env.py
│   │   │   │   ├── __init__.py
│   │   │   │   └── base.py
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   └── notification.py
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   └── notification.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── dispatcher.py
│   │   │   │   ├── email.py
│   │   │   │   ├── fcm.py
│   │   │   │   ├── sms.py
│   │   │   │   ├── sqs_consumer.py
│   │   │   │   └── templates.py
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   └── test_templates.py
│   │   ├── .dockerignore
│   │   ├── .env
│   │   ├── alembic.ini
│   │   ├── Dockerfile
│   │   ├── poetry.lock
│   │   └── pyproject.toml
│   ├── order-svc/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── v1/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── orders.py
│   │   │   │   └── __init__.py
│   │   │   ├── core/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── events.py
│   │   │   │   ├── http_client.py
│   │   │   │   ├── idempotency.py
│   │   │   │   ├── redis.py
│   │   │   │   └── state_machine.py
│   │   │   ├── db/
│   │   │   │   ├── migrations/
│   │   │   │   │   ├── versions/
│   │   │   │   │   │   ├── 0001_create_orders_table.py
│   │   │   │   │   │   ├── 0002_money_to_numeric.py
│   │   │   │   │   │   └── 0003_pain_point_order_fields.py
│   │   │   │   │   └── env.py
│   │   │   │   ├── __init__.py
│   │   │   │   └── base.py
│   │   │   ├── middleware/
│   │   │   │   ├── __init__.py
│   │   │   │   └── correlation.py
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   └── order.py
│   │   │   ├── repositories/
│   │   │   │   ├── __init__.py
│   │   │   │   └── order.py
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   └── order.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── commission.py
│   │   │   │   ├── geo.py
│   │   │   │   └── order.py
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── test_commission.py
│   │   │   └── test_state_machine.py
│   │   ├── .coverage
│   │   ├── .dockerignore
│   │   ├── .env
│   │   ├── alembic.ini
│   │   ├── Dockerfile
│   │   ├── poetry.lock
│   │   └── pyproject.toml
│   ├── payment-svc/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── v1/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── payments.py
│   │   │   │   └── __init__.py
│   │   │   ├── core/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py
│   │   │   │   └── events.py
│   │   │   ├── db/
│   │   │   │   ├── migrations/
│   │   │   │   │   ├── versions/
│   │   │   │   │   │   ├── 0001_create_payment_tables.py
│   │   │   │   │   │   └── 0002_money_to_numeric.py
│   │   │   │   │   └── env.py
│   │   │   │   ├── __init__.py
│   │   │   │   └── base.py
│   │   │   ├── middleware/
│   │   │   │   ├── __init__.py
│   │   │   │   └── correlation.py
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   └── payment.py
│   │   │   ├── repositories/
│   │   │   │   ├── __init__.py
│   │   │   │   └── payment.py
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   └── payment.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── razorpay_svc.py
│   │   │   │   └── stripe_svc.py
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   └── test_wallet.py
│   │   ├── .dockerignore
│   │   ├── .env
│   │   ├── alembic.ini
│   │   ├── Dockerfile
│   │   ├── poetry.lock
│   │   └── pyproject.toml
│   ├── restaurant-svc/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── v1/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   └── restaurants.py
│   │   │   │   └── __init__.py
│   │   │   ├── core/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── cache.py
│   │   │   │   └── dependencies.py
│   │   │   ├── db/
│   │   │   │   ├── migrations/
│   │   │   │   │   ├── versions/
│   │   │   │   │   │   ├── 0001_create_restaurant_tables.py
│   │   │   │   │   │   ├── 0002_money_to_numeric.py
│   │   │   │   │   │   └── 0003_pain_point_pricing_radius.py
│   │   │   │   │   └── env.py
│   │   │   │   ├── __init__.py
│   │   │   │   └── base.py
│   │   │   ├── middleware/
│   │   │   │   ├── __init__.py
│   │   │   │   └── correlation.py
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── menu.py
│   │   │   │   ├── restaurant.py
│   │   │   │   └── review.py
│   │   │   ├── repositories/
│   │   │   │   ├── __init__.py
│   │   │   │   └── restaurant.py
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   └── restaurant.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── geo.py
│   │   │   │   ├── s3.py
│   │   │   │   └── search.py
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── main.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   └── test_geo.py
│   │   ├── .coverage
│   │   ├── .dockerignore
│   │   ├── .env
│   │   ├── alembic.ini
│   │   ├── Dockerfile
│   │   ├── poetry.lock
│   │   ├── pyproject.toml
│   │   └── restaurant_svc.log
│   └── user-svc/
│       ├── app/
│       │   ├── api/
│       │   │   ├── v1/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── addresses.py
│       │   │   │   ├── auth.py
│       │   │   │   └── users.py
│       │   │   └── __init__.py
│       │   ├── core/
│       │   │   ├── __init__.py
│       │   │   ├── dependencies.py
│       │   │   ├── logging.py
│       │   │   ├── redis.py
│       │   │   └── security.py
│       │   ├── db/
│       │   │   ├── migrations/
│       │   │   │   ├── versions/
│       │   │   │   │   └── 0001_create_users_table.py
│       │   │   │   ├── env.py
│       │   │   │   └── script.py.mako
│       │   │   ├── __init__.py
│       │   │   └── base.py
│       │   ├── middleware/
│       │   │   ├── __init__.py
│       │   │   ├── correlation.py
│       │   │   └── logging.py
│       │   ├── models/
│       │   │   ├── __init__.py
│       │   │   ├── address.py
│       │   │   └── user.py
│       │   ├── repositories/
│       │   │   ├── __init__.py
│       │   │   └── user.py
│       │   ├── schemas/
│       │   │   ├── __init__.py
│       │   │   └── user.py
│       │   ├── services/
│       │   │   ├── __init__.py
│       │   │   ├── auth.py
│       │   │   └── otp.py
│       │   ├── __init__.py
│       │   ├── config.py
│       │   └── main.py
│       ├── tests/
│       │   ├── __init__.py
│       │   ├── conftest.py
│       │   └── test_auth.py
│       ├── .dockerignore
│       ├── .env
│       ├── .env.example
│       ├── alembic.ini
│       ├── Dockerfile
│       ├── poetry.lock
│       ├── pyproject.toml
│       └── user_svc.log
├── tests/
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_batch_engine.py
│   │   ├── test_delivery_svc.py
│   │   ├── test_notification_svc.py
│   │   ├── test_order_svc.py
│   │   ├── test_payment_svc.py
│   │   ├── test_restaurant_svc.py
│   │   └── test_user_svc.py
│   ├── results/
│   │   ├── audit/
│   │   │   ├── .gitkeep
│   │   │   ├── audit_findings_and_priorities.md
│   │   │   └── audit_scores.md
│   │   ├── backend/
│   │   │   ├── api/
│   │   │   │   ├── health-check-matrix.md
│   │   │   │   └── menu-endpoint-root-cause.md
│   │   │   ├── migrations/
│   │   │   │   └── seed-verification.md
│   │   │   ├── seed-verification/
│   │   │   ├── service-startup/
│   │   │   │   └── service-boot-matrix.md
│   │   │   ├── .gitkeep
│   │   │   ├── summary.md
│   │   │   └── test_output.txt
│   │   ├── evidence/
│   │   │   ├── logs/
│   │   │   │   ├── docker-availability.log
│   │   │   │   ├── health-check-curl.log
│   │   │   │   ├── menu-endpoint-curl.log
│   │   │   │   ├── seed-count.log
│   │   │   │   └── start-script-run.log
│   │   │   ├── manifests/
│   │   │   │   └── SPR-01-evidence.md
│   │   │   └── summaries/
│   │   │       └── current_handoff.md
│   │   ├── frontend/
│   │   │   └── customer/
│   │   │       ├── screenshots/
│   │   │       └── page-audit.md
│   │   ├── playwright/
│   │   │   ├── index.html
│   │   │   └── summary.md
│   │   ├── .DS_Store
│   │   └── .gitignore
│   ├── .DS_Store
│   └── implementaion_plan.zip
├── .DS_Store
├── .env
├── .env.example
├── .gitignore
├── .gitleaks.toml
├── .npmrc
├── BLOCKERS.md
├── CONTRIBUTING.md
├── docker-compose.yml
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── README.md
└── turbo.json
```
