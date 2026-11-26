"""Create local configuration without overwriting existing credentials."""
import argparse
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def create_env(destination: Path) -> bool:
    content = (ROOT / ".env.example").read_text(encoding="utf-8")
    for name in ("JWT_SECRET", "ADMIN_SESSION_SECRET", "ADMIN_PASSWORD", "TELEGRAM_WEBHOOK_SECRET",
                 "WHATSAPP_VERIFY_TOKEN", "N8N_WEBHOOK_SECRET"):
        content = content.replace(f"\n{name}=\n", f"\n{name}={secrets.token_urlsafe(32)}\n")
    try:
        with destination.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError:
        return False
    return True


def ensure_admin_settings(destination: Path) -> None:
    """Add missing local admin secrets without altering existing service credentials."""
    lines = destination.read_text(encoding='utf-8').splitlines(keepends=True)
    values = dict(line.strip().split('=', 1) for line in lines if '=' in line and not line.lstrip().startswith('#'))
    for name, value in {'ADMIN_USERNAME': 'admin', 'ADMIN_PASSWORD': secrets.token_urlsafe(32),
                        'ADMIN_SESSION_SECRET': secrets.token_urlsafe(48)}.items():
        if not values.get(name):
            lines = [line for line in lines if not line.startswith(name + '=')]
            lines.append(f'\n{name}={value}\n')
    destination.write_text(''.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    created = create_env(ROOT / ".env")
    ensure_admin_settings(ROOT / ".env")
    print("Created .env with unique local secrets." if created else "Existing service credentials preserved; admin settings checked.")
    print("Fill SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and at least one AI provider key in .env.")
    print("Admin username: admin. Read ADMIN_PASSWORD in your local .env; sign in at /admin/login.")
    print("Check setup: python scripts/check_config.py")
    print("Start: python -m uvicorn api.main:app --host 127.0.0.1 --port 8000")


if __name__ == "__main__":
    main()
