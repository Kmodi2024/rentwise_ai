import unittest
import pandas as pd
from market import compare_market
from analytics import load_data


class MarketTests(unittest.TestCase):
    def setUp(self):
        self.properties = pd.DataFrame([dict(property_id='A', property_name='Test', zip_code='02108', monthly_rent_per_unit=1500)])
        self.market = pd.DataFrame([{'RegionName': '02108', '2025-01-31': 2000, '2025-02-28': 2200}])

    def test_zip_matching_dates_and_rent_difference(self):
        result = compare_market(self.properties, self.market, '2025-01-01', '2025-01-31')
        self.assertEqual(result['Area typical rent (USD/month)'].iloc[0], 2000)
        self.assertEqual(result['Difference (USD/month)'].iloc[0], -500)
        self.assertEqual(result['Difference (%)'].iloc[0], -25)
        result = compare_market(self.properties, self.market, '2025-01-01', '2025-02-28')
        self.assertEqual(result['Area typical rent (USD/month)'].iloc[0], 2100)
        self.assertEqual(result['Months available'].iloc[0], 2)

    def test_unmatched_missing_and_wrong_geography(self):
        market = self.market.copy()
        market['RegionName'] = '10001'
        self.assertTrue(compare_market(self.properties, market, '2025-01-01', '2025-02-28')['Difference (%)'].isna().all())
        market['RegionName'] = 'Boston'
        with self.assertRaises(ValueError):
            compare_market(self.properties, market, '2025-01-01', '2025-02-28')
        with self.assertRaises(ValueError):
            compare_market(self.properties, self.market, '2024-01-01', '2024-02-28')
        market = self.market.copy()
        market['2025-01-31'] = 0
        market['2025-02-28'] = None
        self.assertTrue(compare_market(self.properties, market, '2025-01-01', '2025-02-28')['Difference (%)'].isna().all())

    def test_sample_zip_leading_zeros_preserved(self):
        properties, *_ = load_data('data')
        self.assertEqual(properties.zip_code.iloc[0], '02108')
        self.assertTrue(properties.full_address.notna().all())

    def test_spreadsheet_headers_and_duplicate_months(self):
        market = self.market.rename(columns={'2025-01-31': '1/31/2025', '2025-02-28': '2/28/2025'})
        result = compare_market(self.properties, market, '2025-01-01', '2025-02-28')
        self.assertEqual(result['Area typical rent (USD/month)'].iloc[0], 2100)
        self.assertEqual(result['First market month'].iloc[0], '2025-01')
        self.assertEqual(result['Last market month'].iloc[0], '2025-02')
        market['2025-01-31'] = 2000
        with self.assertRaises(ValueError):
            compare_market(self.properties, market, '2025-01-01', '2025-02-28')

    def test_provided_file_matches_all_sample_zips(self):
        properties, *_ = load_data('data')
        market = pd.read_csv('data/Zip_zori_uc_sfrcondomfr_sm_month.csv', dtype={'RegionName': 'string'})
        result = compare_market(properties, market, '2023-10-01', '2026-09-30')
        self.assertTrue(result['Area typical rent (USD/month)'].notna().all())
        self.assertTrue(result['Months available'].eq(35).all())
        self.assertTrue(result['Last market month'].eq('2026-08').all())
