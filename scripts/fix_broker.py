"""Register your broker profile using explicitly supplied contact details."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from city_config import AREAS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', default='broker_001')
    parser.add_argument('--name', required=True)
    parser.add_argument('--email', required=True)
    parser.add_argument('--phone', required=True)
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    from database.supabase_client import get_client
    get_client().table('brokers').upsert({
        'id': args.id, 'name': args.name, 'phone': args.phone,
        'email': args.email, 'areas': list(AREAS), 'is_active': True,
    }).execute()
    print(f'Broker profile saved: {args.id}')


if __name__ == '__main__':
    main()
