import os


site = {
    "name": "Puoric",
    "tagline": "Be Pure, Be Unique.",
    "description": "Premium skincare, haircare and personal care products crafted with purity and care.",
    "email": os.getenv("STORE_EMAIL", "").strip(),
    "phone": os.getenv("STORE_PHONE", "").strip(),
    "whatsapp": os.getenv("STORE_WHATSAPP_NUMBER", "").strip(),
    "address": os.getenv("STORE_ADDRESS", "").strip(),
    "copyright": "© 2026 Puoric. All Rights Reserved.",
    "instagram": os.getenv("STORE_INSTAGRAM_URL", "").strip(),
    "facebook": os.getenv("STORE_FACEBOOK_URL", "").strip(),
}