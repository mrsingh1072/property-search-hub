"""Explicit live notification test to recipients you supply. Not an automated test."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phone', required=True, help='Your permitted test recipient phone')
    parser.add_argument('--email', required=True, help='Your permitted test recipient email')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    from notifications.email_notifier import _send as email_send
    from notifications.whatsapp_notifier import _send as whatsapp_send
    email_ok = email_send(args.email, 'ApnaGhar integration test',
                          '<p>This is your ApnaGhar notification test.</p>',
                          'This is your ApnaGhar notification test.')
    whatsapp_ok = whatsapp_send(args.phone, 'This is your ApnaGhar notification test.')
    print(f'Email accepted: {email_ok}; WhatsApp accepted: {whatsapp_ok}')
    return 0 if email_ok and whatsapp_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
