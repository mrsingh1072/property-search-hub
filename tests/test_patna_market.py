import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import requests
from fastapi.testclient import TestClient

from api.main import app
from agent.intent_extractor import _empty_requirements, _normalise, _postprocess
from broker.csv_schema import validate_row
from broker.upload_handler import normalize_row
from city_config import CITY, STATE, INVENTORY_PATH
from enrichment import geocoder, poi_finder
from rag.retriever import retrieve


class PatnaMarketTests(unittest.TestCase):
    def test_new_requirements_use_patna(self):
        self.assertEqual(_empty_requirements()['city'], CITY)
        self.assertEqual(_normalise({})['city'], CITY)

    def test_patna_localities_are_not_landmarks(self):
        for text, expected in [('Boring Road', 'Boring Road'), ('kankar bagh', 'Kankarbagh'),
                               ('Saguna Mor', 'Saguna More'), ('bailey rd', 'Bailey Road')]:
            result = _postprocess(_empty_requirements(), f'I want a flat in {text}')
            self.assertEqual(result['area'], expected)
            self.assertIsNone(result['named_landmark'])

    def test_locality_in_city_field_is_corrected(self):
        result = _postprocess({**_empty_requirements(), 'city': 'Kankarbagh'}, 'in Kankarbagh')
        self.assertEqual((result['city'], result['area']), ('Patna', 'Kankarbagh'))

    def test_new_listing_uses_bihar_and_patna(self):
        result = normalize_row({'property_type': 'flat', 'price_inr': 5000000,
                                'address': 'Boring Road', 'city': ''})
        self.assertEqual(result['location']['city'], CITY)
        self.assertEqual(result['location']['state'], STATE)

    def test_outside_market_listing_is_rejected_instead_of_relabelled(self):
        row = {'property_type': 'flat', 'price_inr': 5000000, 'address': 'Outside coverage', 'city': 'OutsideMarket'}
        self.assertTrue(validate_row(row, 1))
        with self.assertRaises(ValueError):
            normalize_row(row)

    def test_import_reference_is_stable_and_scoped_to_broker(self):
        row = {'external_ref': '001', 'property_type': 'flat', 'price_inr': 5000000, 'address': 'Boring Road'}
        first = normalize_row(row, 'broker-a')['doc_id']
        self.assertEqual(first, normalize_row(row, 'broker-a')['doc_id'])
        self.assertNotEqual(first, normalize_row(row, 'broker-b')['doc_id'])
        self.assertIn('PATNA_', first)

    @patch('rag.retriever.search_properties', return_value=[])
    @patch('rag.retriever.embed_text', return_value=[0.1] * 384)
    def test_search_fallback_keeps_patna_filter(self, embed, search):
        self.assertEqual(retrieve('2 bhk', {'city': CITY, 'area': 'Boring Road'}), [])
        self.assertEqual(search.call_count, 2)
        for call in search.call_args_list:
            self.assertEqual(call.kwargs['filter_city'], CITY)

    @patch('rag.retriever.search_properties')
    @patch('rag.retriever.embed_text')
    def test_explicit_other_city_is_not_silently_changed(self, embed, search):
        self.assertEqual(retrieve('OutsideMarket homes', {'city': 'OutsideMarket'}), [])
        embed.assert_not_called()
        search.assert_not_called()

    @patch('embeddings.generate_embeddings.get_client')
    @patch('embeddings.generate_embeddings.embed_batch')
    def test_empty_patna_inventory_needs_no_model_or_database(self, embed, client):
        from embeddings.generate_embeddings import run
        self.assertEqual(json.loads(INVENTORY_PATH.read_text()), [])
        run()
        embed.assert_not_called()
        client.assert_not_called()

    def test_batch_import_rejects_legacy_inventory(self):
        from embeddings.generate_embeddings import load_properties
        with tempfile.TemporaryDirectory() as folder:
            legacy = Path(folder) / 'legacy.json'
            legacy.write_text(json.dumps([{'doc_id': 'old', 'location': {'city': 'OutsideMarket'}}]))
            with patch('embeddings.generate_embeddings.RAG_JSON_PATH', legacy):
                with self.assertRaises(ValueError):
                    load_properties()

    @patch('database.supabase_client.get_client')
    def test_database_boundary_rejects_old_inventory_without_contacting_db(self, client):
        from database.supabase_client import upsert_property
        with self.assertRaises(ValueError):
            upsert_property({'location': {'city': 'OutsideMarket'}}, 'old listing', [0.0] * 384)
        client.assert_not_called()

    @patch('database.supabase_client.get_client')
    def test_database_boundary_rejects_wrong_state(self, client):
        from database.supabase_client import upsert_property
        with self.assertRaises(ValueError):
            upsert_property({'location': {'city': CITY, 'state': 'OtherState'}}, 'bad state', [0.0] * 384)
        client.assert_not_called()

    @patch('enrichment.enrich_properties.get_coordinates', return_value=None)
    def test_failed_batch_geocoding_clears_stale_location(self, lookup):
        from enrichment.enrich_properties import enrich_single
        result = enrich_single({'doc_id': 'new', 'location': {'city': CITY},
                                'connectivity': {'latitude': 0.0, 'longitude': 0.0}})
        self.assertEqual(result['connectivity'], {'status': 'pending_enrichment'})

    @patch('enrichment.geocoder._try_nominatim')
    def test_address_query_uses_patna_bihar(self, lookup):
        geocoder.geocode_address('Boring Road')
        lookup.assert_called_once_with('Boring Road, Patna, Bihar, India')

    @patch('enrichment.geocoder._try_nominatim')
    def test_old_city_cannot_use_patna_geocoder(self, lookup):
        self.assertIsNone(geocoder.geocode_address('Outside coverage', 'OutsideMarket', 'OtherState'))
        lookup.assert_not_called()

    @patch('enrichment.geocoder._geocode_limited')
    def test_nominatim_rejects_out_of_market_coordinates(self, lookup):
        lookup.return_value = SimpleNamespace(latitude=0.0, longitude=0.0, raw={})
        with patch.dict(geocoder._LANDMARK_CACHE, {}, clear=True):
            self.assertIsNone(geocoder._try_nominatim('test query in Patna'))

    @patch('enrichment.geocoder._geocode_limited')
    def test_nominatim_does_not_use_city_center_as_property(self, lookup):
        lookup.return_value = SimpleNamespace(latitude=25.61, longitude=85.14, raw={'addresstype': 'city'})
        with patch.dict(geocoder._LANDMARK_CACHE, {}, clear=True):
            self.assertIsNone(geocoder._try_nominatim('unknown property'))

    @patch('enrichment.geocoder.requests.get')
    def test_photon_search_bias_is_patna_and_rejects_outside_market(self, get):
        get.return_value.json.return_value = {'features': [{'geometry': {'coordinates': [0.0, 0.0]}}]}
        with patch.dict(geocoder._LANDMARK_CACHE, {}, clear=True):
            self.assertIsNone(geocoder._try_photon('test place'))
        self.assertEqual(get.call_args.kwargs['params']['lat'], 25.61)
        self.assertEqual(get.call_args.kwargs['params']['lon'], 85.14)

    @patch('enrichment.poi_finder._query_elements', side_effect=requests.Timeout)
    def test_failed_poi_lookup_returns_unknown_distances(self, query):
        result = poi_finder.find_nearby_pois(25.61, 85.14)
        self.assertEqual(result['poi_status'], 'unavailable')
        self.assertIsNone(result['metro_distance_km'])
        self.assertIsNone(result['hospital_distance_km'])
        self.assertEqual(result['fixed_anchors'], {})

    @patch('enrichment.poi_finder._query_elements')
    def test_real_pois_exclude_other_cities_and_unfinished_metro(self, query):
        query.return_value = [
            {'lat': 25.615, 'lon': 85.145, 'tags': {'name': 'Test hospital', 'amenity': 'hospital'}},
            {'lat': 0.0, 'lon': 0.0, 'tags': {'name': 'OutsideMarket hospital', 'amenity': 'hospital'}},
            {'lat': 25.611, 'lon': 85.141, 'tags': {'name': 'Unfinished metro', 'railway': 'station',
                                                'station': 'subway', 'construction': 'yes'}},
        ]
        result = poi_finder.find_nearby_pois(25.61, 85.14)
        self.assertEqual(result['hospital_name'], 'Test hospital')
        self.assertGreater(result['hospital_distance_km'], 0)
        self.assertIsNone(result['metro_distance_km'])
        self.assertEqual(result['distance_kind'], 'straight_line')

    @patch('enrichment.poi_finder._query_elements')
    def test_no_poi_request_for_outside_market_coordinates(self, query):
        result = poi_finder.find_nearby_pois(0.0, 0.0)
        self.assertEqual(result['poi_status'], 'unavailable')
        query.assert_not_called()

    @patch('scripts.check_config.configuration_status', return_value={'required': {'database': True}})
    @patch('database.supabase_client.get_client')
    def test_browse_and_featured_are_scoped_to_patna(self, get_client, status):
        query = MagicMock()
        for name in ['select', 'eq', 'order', 'limit']:
            getattr(query, name).return_value = query
        query.execute.return_value = SimpleNamespace(data=[])
        get_client.return_value.table.return_value = query
        client = TestClient(app)
        for route in ['/api/properties/browse', '/api/featured']:
            query.reset_mock()
            self.assertEqual(client.get(route).status_code, 200)
            self.assertIn((('city', 'Patna'), {}), [(c.args, c.kwargs) for c in query.eq.call_args_list])


if __name__ == '__main__':
    unittest.main()
