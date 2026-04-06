"""Notification templates per event type and locale."""
from typing import Final

# Template: {locale: {event_type: (title, body_template)}}
# Body templates support {order_id}, {restaurant_name}, {driver_name}, {eta} substitutions

TEMPLATES: Final[dict[str, dict[str, tuple[str, str]]]] = {
    "en-US": {
        "order_created": ("Order Placed!", "Your order #{order_id} has been placed. We're waiting for the restaurant to confirm."),
        "order_confirmed": ("Order Confirmed 🎉", "Great news! {restaurant_name} has confirmed your order #{order_id}."),
        "order_preparing": ("Cooking in Progress 👨‍🍳", "{restaurant_name} is preparing your order #{order_id}."),
        "order_ready": ("Order Ready for Pickup 🛵", "Your order #{order_id} is ready! Driver is on the way."),
        "order_picked_up": ("On the Way! 🚀", "{driver_name} has picked up your order and is heading to you. ETA: {eta}"),
        "order_delivered": ("Delivered! 🎊", "Your order #{order_id} has been delivered. Enjoy your meal!"),
        "order_cancelled": ("Order Cancelled", "Your order #{order_id} has been cancelled. A refund will be processed shortly."),
        "payment_succeeded": ("Payment Successful ✅", "Payment of {amount} {currency} received for order #{order_id}."),
        "payment_failed": ("Payment Failed ❌", "Payment for order #{order_id} failed. Please try again."),
        "driver_assigned": ("Driver Assigned 🛵", "{driver_name} is your driver for order #{order_id}."),
    },
    "en-IN": {
        "order_created": ("Order Placed!", "Your order #{order_id} has been placed. Waiting for restaurant confirmation."),
        "order_confirmed": ("Order Confirmed! 🎉", "{restaurant_name} has confirmed order #{order_id}."),
        "order_preparing": ("Being Prepared 👨‍🍳", "{restaurant_name} is preparing order #{order_id}."),
        "order_ready": ("Ready for Pickup 🛵", "Order #{order_id} is ready! Your delivery partner is coming."),
        "order_picked_up": ("Out for Delivery 🚀", "{driver_name} has picked up order #{order_id}. ETA: {eta}"),
        "order_delivered": ("Delivered! 🎊", "Order #{order_id} delivered. Enjoy your food!"),
        "order_cancelled": ("Order Cancelled", "Order #{order_id} cancelled. Refund will be processed."),
        "payment_succeeded": ("Payment Successful ✅", "₹{amount} received for order #{order_id}."),
        "payment_failed": ("Payment Failed ❌", "Payment for order #{order_id} failed. Please retry."),
        "driver_assigned": ("Delivery Partner Assigned 🛵", "{driver_name} will deliver order #{order_id}."),
    },
    "hi-IN": {
        "order_created": ("ऑर्डर दर्ज हो गया!", "आपका ऑर्डर #{order_id} दर्ज हो गया है। रेस्तरां की पुष्टि का इंतजार है।"),
        "order_confirmed": ("ऑर्डर कन्फर्म! 🎉", "{restaurant_name} ने आपका ऑर्डर #{order_id} कन्फर्म कर दिया।"),
        "order_preparing": ("खाना बन रहा है 👨‍🍳", "{restaurant_name} आपका ऑर्डर #{order_id} तैयार कर रहा है।"),
        "order_ready": ("पिकअप के लिए तैयार 🛵", "ऑर्डर #{order_id} तैयार है! डिलीवरी पार्टनर आ रहा है।"),
        "order_picked_up": ("डिलीवरी के रास्ते में 🚀", "{driver_name} ने ऑर्डर #{order_id} उठा लिया। ETA: {eta}"),
        "order_delivered": ("डिलीवर हो गया! 🎊", "ऑर्डर #{order_id} डिलीवर हो गया। खाने का आनंद लें!"),
        "order_cancelled": ("ऑर्डर रद्द", "ऑर्डर #{order_id} रद्द हो गया। रिफंड जल्द होगा।"),
        "payment_succeeded": ("भुगतान सफल ✅", "ऑर्डर #{order_id} के लिए ₹{amount} प्राप्त हुए।"),
        "payment_failed": ("भुगतान विफल ❌", "ऑर्डर #{order_id} का भुगतान विफल। पुनः प्रयास करें।"),
        "driver_assigned": ("डिलीवरी पार्टनर मिला 🛵", "{driver_name} आपका ऑर्डर #{order_id} डिलीवर करेगा।"),
    },
}

DEFAULT_LOCALE = "en-US"


def get_template(event_type: str, locale: str, **kwargs: str) -> tuple[str, str]:
    """Returns (title, body) for given event type and locale."""
    templates = TEMPLATES.get(locale, TEMPLATES[DEFAULT_LOCALE])
    fallback = TEMPLATES[DEFAULT_LOCALE]

    title_tmpl, body_tmpl = templates.get(event_type, fallback.get(event_type, ("BhojanGo", "You have a new notification.")))
    try:
        body = body_tmpl.format(**kwargs)
    except KeyError:
        body = body_tmpl

    return title_tmpl, body
