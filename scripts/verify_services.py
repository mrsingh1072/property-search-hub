"""Read database schema and make one small AI test request; send no notifications."""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-only', action='store_true',
                        help='Check database tables and search RPC without requiring or calling an AI provider.')
    args = parser.parse_args(argv)
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    from scripts.check_config import configuration_status
    status = configuration_status()
    if not status['required']['database'] or (not args.database_only and not status['ready']):
        print('Database configuration is missing.' if args.database_only else 'Required configuration is missing. Run python scripts/check_config.py first.')
        return 1
    passed = True
    try:
        from database.supabase_client import get_client
        client = get_client()
        tables = {
            'properties': 'id,embedding', 'brokers': 'id', 'leads': 'id,broker_offer,customer_offer',
            'sessions': 'session_id', 'meetings': 'id', 'customers': 'id', 'broker_confirmations': 'id',
        }
        for table, columns in tables.items():
            client.table(table).select(columns).limit(1).execute()
            print(f'OK database table: {table}')
        client.rpc('match_properties', {'query_embedding': [0.0] * 384, 'match_count': 1}).execute()
        print('OK property search RPC')
    except Exception as exc:
        print(f'FAIL database: {type(exc).__name__}. Check credentials and all six migrations.')
        passed = False
    if not args.database_only:
        try:
            from agent.llm_client import complete
            response = complete([{'role': 'user', 'content': 'Reply with the single word OK.'}],
                                temperature=0, max_tokens=24)
            print('OK AI completion' if response.strip() else 'FAIL empty AI response')
            passed = passed and bool(response.strip())
        except Exception as exc:
            print(f'FAIL AI: {type(exc).__name__}. Check provider key, quota and configured model.')
            passed = False
    print('No notifications were sent and no records were changed.')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
