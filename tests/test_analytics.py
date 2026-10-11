import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from analytics import SCHEMAS, load_data, filter_records, portfolio_totals, occupancy_rate
from insights import build_insights


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.properties = pd.DataFrame([
            dict(property_id='A', property_name='Same', units=4, occupied_units=4),
            dict(property_id='B', property_name='Same', units=6, occupied_units=3),
        ])
        self.payments = pd.DataFrame([
            dict(payment_id='1', property_id='A', unit=1, due_date=pd.Timestamp('2025-01-05'), amount_due=100, amount_paid=100, status='Paid'),
            dict(payment_id='2', property_id='B', unit=1, due_date=pd.Timestamp('2025-02-05'), amount_due=100, amount_paid=50, status='Unpaid'),
        ])
        self.expenses = pd.DataFrame([
            dict(expense_id='1', property_id='A', date=pd.Timestamp('2025-01-15'), category='Repair', amount=25),
            dict(expense_id='2', property_id='B', date=pd.Timestamp('2025-02-15'), category='Repair', amount=150),
        ])

    def test_cash_flow_and_weighted_occupancy(self):
        totals = portfolio_totals(self.properties, self.payments, self.expenses)
        self.assertEqual(totals['income'], 150)
        self.assertEqual(totals['due'], 200)
        self.assertEqual(totals['expenses'], 175)
        self.assertEqual(totals['cash'], -25)
        self.assertEqual(totals['occupancy'], .7)

    def test_shared_filters_and_inclusive_boundaries(self):
        pay = filter_records(self.payments, ['A'], '2025-01-05', '2025-01-15', 'due_date')
        ex = filter_records(self.expenses, ['A'], '2025-01-05', '2025-01-15', 'date')
        self.assertEqual(portfolio_totals(self.properties.iloc[:1], pay, ex)['cash'], 75)
        self.assertTrue(filter_records(self.expenses, ['B'], '2025-01-01', '2025-01-31', 'date').empty)
        self.assertTrue(filter_records(self.payments, [], '2025-01-01', '2025-12-31', 'due_date').empty)
        with self.assertRaises(ValueError):
            filter_records(self.payments, ['A'], '2025-02-01', '2025-01-01', 'due_date')

    def test_empty_totals(self):
        totals = portfolio_totals(self.properties.iloc[:0], self.payments.iloc[:0], self.expenses.iloc[:0])
        self.assertEqual(totals['cash'], 0)
        self.assertIsNone(totals['occupancy'])

    def test_invalid_occupancy(self):
        for units, occupied in [(0, 0), (4, 5), (4, -1), (None, 2), (4, None)]:
            with self.subTest(units=units, occupied=occupied):
                p = pd.DataFrame([dict(units=units, occupied_units=occupied)])
                self.assertIsNone(occupancy_rate(p))

    def load_fixture(self, expenses):
        frames = {name: pd.DataFrame(columns=columns) for name, columns in SCHEMAS.items()}
        frames['properties.csv'] = self.properties
        frames['expenses.csv'] = expenses
        with patch('analytics.pd.read_csv', side_effect=lambda path, **kwargs: frames[path.name].copy()):
            return load_data(Path('unused'))

    def test_exact_duplicates_do_not_inflate_expenses(self):
        ex = pd.concat([self.expenses, self.expenses.iloc[:1]], ignore_index=True)
        _, _, cleaned, _, notes = self.load_fixture(ex)
        self.assertEqual(cleaned.amount.sum(), 175)
        self.assertTrue(any('exact duplicate' in note for note in notes))

    def test_conflicting_ids_excluded_but_distinct_ids_retained(self):
        extra = self.expenses.iloc[:1].copy()
        extra['amount'] = 999
        _, _, cleaned, _, notes = self.load_fixture(pd.concat([self.expenses, extra], ignore_index=True))
        self.assertEqual(cleaned.amount.sum(), 150)
        self.assertTrue(any('conflicting' in note for note in notes))
        extra = self.expenses.iloc[:1].copy()
        extra['expense_id'] = '3'
        _, _, cleaned, _, _ = self.load_fixture(pd.concat([self.expenses, extra], ignore_index=True))
        self.assertEqual(cleaned.amount.sum(), 200)

    def test_missing_values_columns_and_invalid_dates(self):
        ex = pd.DataFrame([dict(property_id='A', date='bad', amount='invalid'),
                           dict(property_id='A', date='2025-01-15', amount=None)])
        _, _, cleaned, _, notes = self.load_fixture(ex)
        self.assertEqual(cleaned.amount.sum(), 0)
        self.assertTrue(cleaned.category.eq('Unknown').all())
        self.assertEqual(len(filter_records(cleaned, ['A'], '2025-01-01', '2025-01-31', 'date')), 1)
        self.assertTrue(notes)

    def test_missing_and_zero_byte_files(self):
        for error in [FileNotFoundError(), pd.errors.EmptyDataError('empty')]:
            with patch('analytics.pd.read_csv', side_effect=error):
                *frames, notes = load_data('unused')
            self.assertTrue(all(frame.empty for frame in frames))
            self.assertEqual(len(notes), 4)

    def test_anomaly_threshold_and_sample_size(self):
        ex = pd.DataFrame([dict(expense_id=str(i), property_id='A', date=pd.Timestamp('2025-01-15'),
                                category='Repair', amount=amount) for i, amount in enumerate([100, 100, 100, 600, 601, 0, -500])])
        findings, _ = build_insights(self.properties.iloc[:1], self.payments.iloc[:0], ex)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['evidence']['Threshold (USD)'], 600)
        self.assertEqual(findings[0]['evidence']['Amount (USD)'], 601)
        self.assertEqual(findings[0]['evidence']['Positive baseline records'], 5)
        findings, notes = build_insights(self.properties.iloc[:1], self.payments.iloc[:0], ex.iloc[:3])
        self.assertFalse(findings)
        self.assertTrue(notes)

    def test_unpaid_balances_not_cancelled_by_overpayments(self):
        payments = self.payments.copy()
        payments['property_id'] = 'A'
        payments.loc[0, 'amount_paid'] = 200
        findings, _ = build_insights(self.properties.iloc[:1], payments, self.expenses.iloc[:0])
        self.assertEqual(findings[0]['evidence']['Outstanding (USD)'].sum(), 50)

    def test_occupancy_threshold_and_empty_insights(self):
        p = self.properties.iloc[:1].copy()
        p['units'], p['occupied_units'] = 10, 9
        findings, _ = build_insights(p, self.payments.iloc[:0], self.expenses.iloc[:0])
        self.assertFalse(findings)
        p['occupied_units'] = 8
        findings, _ = build_insights(p, self.payments.iloc[:0], self.expenses.iloc[:0])
        self.assertEqual(findings[0]['evidence']['Occupancy (%)'], 80)
        self.assertEqual(build_insights(p.iloc[:0], self.payments.iloc[:0], self.expenses.iloc[:0]), ([], []))


if __name__ == '__main__':
    unittest.main()
