"""Create local configuration without overwriting existing credentials."""
import argparse
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def create_env(destination: Path) -> bool:
    content = (ROOT / ".env.example").read_text(encoding="utf-8")
    for name in ("JWT_SECRET", "BROKER_TOKEN", "BROKER_PASSWORD", "TELEGRAM_WEBHOOK_SECRET",
                 "WHATSAPP_VERIFY_TOKEN", "N8N_WEBHOOK_SECRET"):
        content = content.replace(f"\n{name}=\n", f"\n{name}={secrets.token_urlsafe(32)}\n")
    try:
        with destination.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError:
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    created = create_env(ROOT / ".env")
    print("Created .env with unique local secrets." if created else "Existing .env preserved.")
    print("Fill SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and at least one AI provider key in .env.")
    print("Broker username: broker. Read BROKER_PASSWORD in your local .env to sign in.")
    print("Check setup: python scripts/check_config.py")
    print("Start: python -m uvicorn api.main:app --host 127.0.0.1 --port 8000")


if __name__ == "__main__":
    main()
