"""Send one live WhatsApp test to an explicitly supplied permitted recipient."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phone', help='Your permitted test recipient with country code')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    from notifications.whatsapp_notifier import _send
    ok = _send(args.phone, 'Hello from ApnaGhar. Your WhatsApp integration test.')
    print('Message accepted by WhatsApp.' if ok else 'Message failed; check local configuration.')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
