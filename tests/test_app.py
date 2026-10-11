import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from analytics import SCHEMAS

APP = Path(__file__).resolve().parents[1] / 'app.py'


class DashboardTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()

    def tearDown(self):
        st.cache_data.clear()

    def test_real_data_totals_all_views_and_filters(self):
        pay = pd.read_csv(APP.parent / 'data/payments.csv')
        ex = pd.read_csv(APP.parent / 'data/expenses.csv')
        app = AppTest.from_file(str(APP)).run()
        for page in ['Overview', 'Financial Analytics', 'Rent Tracking', 'Maintenance', 'AI Insights']:
            app.sidebar.radio[0].set_value(page).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[0].value, f'${pay.amount_paid.sum():,.0f}')
            self.assertEqual(app.metric[2].value, f'${pay.amount_paid.sum()-ex.amount.sum():,.0f}')
        app.sidebar.multiselect[0].set_value(['P02'])
        app.date_input[0].set_value(date(2025, 1, 1))
        app.date_input[1].set_value(date(2025, 3, 31))
        app.sidebar.radio[0].set_value('Financial Analytics').run()
        fp = pay[(pay.property_id == 'P02') & pay.due_date.between('2025-01-01', '2025-03-31')]
        fe = ex[(ex.property_id == 'P02') & ex.date.between('2025-01-01', '2025-03-31')]
        self.assertFalse(app.exception)
        table = app.dataframe[-1].value
        self.assertEqual(len(table), 1)
        self.assertEqual(table['Net Cash Flow'].iloc[0], fp.amount_paid.sum()-fe.amount.sum())
        self.assertAlmostEqual(table['Collection Rate (%)'].iloc[0], 100*fp.amount_paid.sum()/fp.amount_due.sum())
        app.sidebar.multiselect[0].set_value(['P01', 'P02']).run()
        self.assertFalse(app.exception)
        expected = pay[pay.property_id.isin(['P01', 'P02']) & pay.due_date.between('2025-01-01', '2025-03-31')].amount_paid.sum()
        self.assertEqual(app.metric[0].value, f'${expected:,.0f}')
        app.sidebar.button(key='clear_all_properties').click().run()
        self.assertFalse(app.sidebar.multiselect[0].value)
        app.sidebar.button(key='select_all_properties').click().run()
        self.assertEqual(len(app.sidebar.multiselect[0].value), 5)
        app.sidebar.multiselect[0].set_value([]).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.metric)
        self.assertIn('No data matches', app.info[0].value)

    def test_same_name_properties_do_not_mix_and_missing_occupancy_is_unavailable(self):
        frames = {name: pd.DataFrame(columns=columns) for name, columns in SCHEMAS.items()}
        frames['properties.csv'] = pd.DataFrame([
            dict(property_id='A', property_name='Same', units=4, occupied_units=None),
            dict(property_id='B', property_name='Same', units=4, occupied_units=4),
        ])
        frames['expenses.csv'] = pd.DataFrame([
            dict(expense_id='1', property_id='A', date='2025-01-15', amount=25),
            dict(expense_id='2', property_id='B', date='2025-01-15', amount=999),
        ])
        original_read_csv = pd.read_csv
        def read_fixture(path, **kwargs):
            name = Path(path).name
            return frames[name].copy() if name in frames else original_read_csv(path, **kwargs)
        with patch('analytics.pd.read_csv', side_effect=read_fixture):
            app = AppTest.from_file(str(APP)).run()
            app.sidebar.multiselect[0].set_value(['A']).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.metric[1].value, '$25')
            self.assertEqual(app.metric[3].value, 'N/A')
            for page in ['Financial Analytics', 'Rent Tracking', 'Maintenance', 'AI Insights']:
                app.sidebar.radio[0].set_value(page).run()
                self.assertFalse(app.exception)
            app.sidebar.radio[0].set_value('Rent Tracking').run()
            self.assertEqual(app.metric[6].value, 'N/A')
            app.date_input[0].set_value(date(2025, 1, 1))
            app.date_input[1].set_value(date(2025, 1, 2)).run()
            self.assertFalse(app.exception)
            self.assertIn('No data matches', app.info[0].value)

    def test_no_csvs_shows_empty_state(self):
        with patch('analytics.pd.read_csv', side_effect=FileNotFoundError()):
            app = AppTest.from_file(str(APP)).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('No dated records' in message.value for message in app.info))
