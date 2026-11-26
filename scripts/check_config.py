"""Check configuration without printing credentials or contacting external services."""
import argparse
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def configured(name):
    value = os.environ.get(name, "").strip()
    return bool(value) and not value.lower().startswith(("your_", "gsk_your", "eaaxxxx", "use_a_"))


def configuration_status():
    url = urlparse(os.environ.get("SUPABASE_URL", ""))
    database = (url.scheme == "https" and bool(url.hostname)
                and url.hostname != "your-project.supabase.co"
                and configured("SUPABASE_SERVICE_ROLE_KEY"))
    ai = any(configured(n) for n in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"))
    secrets_ok = (len(os.environ.get("JWT_SECRET", "")) >= 32
                  and len(os.environ.get("ADMIN_SESSION_SECRET", "")) >= 32
                  and len(os.environ.get("ADMIN_PASSWORD", "")) >= 12
                  and bool(os.environ.get("ADMIN_USERNAME", "").strip()))
    required = {"database": bool(database), "ai_provider": ai, "local_secrets": secrets_ok}
    groups = {
        "email": ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD"),
        "telegram": ("TELEGRAM_BOT_TOKEN",),
        "whatsapp": ("WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_ACCESS_TOKEN", "WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN"),
        "google_login": ("GOOGLE_OAUTH_CLIENT_ID",),
        "n8n": ("N8N_LEAD_WEBHOOK_URL", "N8N_WEBHOOK_SECRET"),
        "sms": ("FAST2SMS_API_KEY",),
    }
    optional = {k: all(configured(n) for n in names) for k, names in groups.items()}
    optional["calendar"] = (any(configured(n) for n in
        ("GOOGLE_SERVICE_ACCOUNT_FILE", "GOOGLE_SERVICE_ACCOUNT_JSON", "GOOGLE_CALENDAR_SERVICE_ACCOUNT"))
        and any(configured(n) for n in ("BROKER_GOOGLE_CALENDAR_ID", "GOOGLE_CALENDAR_ID")))
    return {"ready": all(required.values()), "required": required, "optional": optional}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    status = configuration_status()
    for name, ok in status["required"].items():
        print(f"{'OK' if ok else 'MISSING'} required: {name}")
    for name, ok in status["optional"].items():
        print(f"{'CONFIGURED' if ok else 'DISABLED'} optional: {name}")
    print("Configuration only; credentials and database migrations still need a live check.")
    return 0 if status["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
