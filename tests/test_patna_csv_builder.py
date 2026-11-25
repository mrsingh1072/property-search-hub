import csv
from pathlib import Path
import tempfile
import unittest

from build_rag_documents import build_documents
from scripts.validate_data import validate_documents


class PatnaCsvBuilderTests(unittest.TestCase):
    def make_csv(self, folder, rows):
        path = Path(folder) / 'patna.csv'
        with path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                'external_ref', 'property_type', 'price_inr', 'address', 'city', 'bhk'])
            writer.writeheader()
            writer.writerows(rows)
        return path

    def row(self, **updates):
        return {'external_ref': 'TEST001', 'property_type': 'flat', 'price_inr': '5000000',
                'address': 'Boring Road', 'city': 'Patna', 'bhk': '2', **updates}

    def test_valid_patna_csv_builds_normalized_document(self):
        with tempfile.TemporaryDirectory() as folder:
            documents = build_documents(self.make_csv(folder, [self.row()]), 'test-broker')
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]['location']['city'], 'Patna')
        self.assertEqual(documents[0]['location']['state'], 'Bihar')
        self.assertEqual(documents[0]['pricing']['total_price_inr'], 5000000)
        self.assertEqual(documents[0]['connectivity']['status'], 'pending_enrichment')
        self.assertEqual(validate_documents(documents), [])

    def test_header_only_template_is_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(build_documents(self.make_csv(folder, [])), [])

    def test_unsupported_city_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                build_documents(self.make_csv(folder, [self.row(city='OutsideMarket')]))

    def test_duplicate_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'Duplicate external references'):
                build_documents(self.make_csv(folder, [self.row(), self.row()]))

    def test_missing_required_columns_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'invalid.csv'
            path.write_text('address\nBoring Road\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'must contain'):
                build_documents(path)

    def test_json_validator_requires_array(self):
        self.assertTrue(validate_documents({'city': 'Patna'}))

    def test_json_validator_rejects_unsupported_city(self):
        with tempfile.TemporaryDirectory() as folder:
            documents = build_documents(self.make_csv(folder, [self.row()]))
        documents[0]['location']['city'] = 'OutsideMarket'
        self.assertTrue(validate_documents(documents))

    def test_json_validator_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            documents = build_documents(self.make_csv(folder, [self.row()]))
        self.assertTrue(validate_documents(documents + documents))


if __name__ == '__main__':
    unittest.main()
