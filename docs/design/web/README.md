# Website design v2 (source of truth for the website rebuild)

Live board: https://claude.ai/artifact/9hWrw4yoyoziZeNffAQgGi (section "Website").
- `*.html`: each page as HTML with inline styles (exact colours, spacing, copy). Photos are referenced as `food/<slug>-800.webp` = `apps/web/public/food/`.
- `r_*.png`: rendered screenshot of each page. Match these.
- `WebDataRules.html`: what must come from data. Nothing city-, country- or currency-specific is typed into a template.
Desktop: WebLanding (first visit), WebHome (signed in), WebSignIn, WebOTP, WebCity, WebCities, WebKitchen, WebCustomise, WebCheckout, WebTracking, WebOrders, WebProfile, WebFavourites, WebNotInArea.
Mobile web (390 px): MWebHome, MWebMenu, MWebCheckout, MWebTracking, MWebSignIn.
