"""Build normalized Patna property documents from your supplied broker CSV.

This is an offline conversion: no geocoding, AI calls, or database writes.
"""
import argparse
import csv
import json
from pathlib import Path

from broker.csv_schema import validate_row
from broker.upload_handler import normalize_row
from city_config import INVENTORY_PATH


def build_documents(csv_path: Path, broker_id: str | None = None) -> list[dict]:
    with csv_path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not {'property_type', 'price_inr', 'address'}.issubset(reader.fieldnames or []):
            raise ValueError('CSV must contain property_type, price_inr and address columns.')
        rows = list(reader)
    errors = []
    for number, row in enumerate(rows, 1):
        errors.extend(validate_row(row, number))
    if errors:
        raise ValueError('\n'.join(errors))
    documents = [normalize_row(row, broker_id) for row in rows]
    ids = [doc['doc_id'] for doc in documents]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate external references: use one unique reference per listing.')
    return documents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_file', type=Path, help='Your genuine Patna listings CSV')
    parser.add_argument('--output', type=Path, default=INVENTORY_PATH)
    parser.add_argument('--broker-id')
    args = parser.parse_args()
    try:
        documents = build_documents(args.csv_file, args.broker_id)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Conversion failed: {exc}\n')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(documents, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Built {len(documents)} Patna document(s). No external services were contacted.')


if __name__ == '__main__':
    main()
