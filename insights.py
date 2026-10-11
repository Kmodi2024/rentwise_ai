"""Transparent rules over the dashboard's already-filtered records; no model calls."""
from analytics import occupancy_rate


def build_insights(properties, payments, expenses):
    findings = []
    notes = []
    names = properties.set_index('property_id')['property_name'].to_dict()
    for property_id, group in payments.groupby('property_id'):
        outstanding = (group.amount_due - group.amount_paid).clip(lower=0)
        records = group.loc[outstanding > 0].copy()
        if records.empty:
            continue
        records['Outstanding (USD)'] = outstanding.loc[records.index]
        total = records['Outstanding (USD)'].sum()
        findings.append(dict(
            title=f'Uncollected rent · {names.get(property_id, property_id)}',
            explanation=f'{len(records)} rent records have unpaid balances totaling ${total:,.2f}. '
                        'Overpayments on other records do not cancel these balances. This is not an overdue determination.',
            rule='Flag each record when amount due minus amount paid is greater than $0.',
            evidence=records[['payment_id', 'unit', 'due_date', 'status', 'amount_due', 'amount_paid', 'Outstanding (USD)']],
            action='Review the listed balances and confirm payment records before following up.',
        ))
    for row in properties.itertuples():
        occupancy = occupancy_rate(properties.loc[properties.property_id == row.property_id])
        if occupancy is None:
            notes.append(f'{row.property_name}: occupancy cannot be assessed because total units is zero or unavailable.')
            continue
        if occupancy < .9:
            findings.append(dict(
                title=f'Low occupancy · {row.property_name}',
                explanation=f'{row.occupied_units:g} of {row.units:g} units are occupied ({occupancy:.1%}), '
                            'below the 90% review threshold. This is the current snapshot, not occupancy during the selected dates.',
                rule='Flag a property when occupied units / total units is strictly below 90%.',
                evidence={'Occupied units': row.occupied_units, 'Total units': row.units,
                          'Vacant units': row.units - row.occupied_units, 'Occupancy (%)': occupancy * 100,
                          'Threshold (%)': 90},
                action='Check vacancy records and review leasing activity.',
            ))
    for (property_id, category), group in expenses.groupby(['property_id', 'category']):
        # Credits and zero/missing amounts are not a baseline for high expense detection.
        positive = group[group.amount > 0]
        if len(positive) < 4:
            notes.append(f'{names.get(property_id, property_id)} / {category}: high-expense checks need at least '
                         f'4 positive expense records; this selection has {len(positive)}.')
            continue
        median = positive.amount.median()
        threshold = max(2 * median, median + 500)
        for row in positive[positive.amount > threshold].itertuples():
            findings.append(dict(
                title=f'Unusually high expense · {names.get(property_id, property_id)} / {category}',
                explanation=f'Expense {row.expense_id} on {row.date:%b %d, %Y} is ${row.amount:,.2f}. '
                            f'It exceeds the ${threshold:,.2f} review threshold by ${row.amount-threshold:,.2f}. '
                            f'The median of {len(positive)} positive records is ${median:,.2f}. '
                            'A flag suggests review; it does not establish an error.',
                rule='Amount must be strictly greater than max(2 × median, median + $500). '
                     'The baseline includes the flagged record and uses only this property/category within the selected dates.',
                evidence={'Expense ID': row.expense_id, 'Date': row.date.date().isoformat(),
                          'Amount (USD)': row.amount, 'Median (USD)': median,
                          '2 × median (USD)': 2 * median, 'Median + $500 (USD)': median + 500,
                          'Threshold (USD)': threshold, 'Above threshold (USD)': row.amount - threshold,
                          'Positive baseline records': len(positive)},
                action='Compare the invoice and source record with typical spending in this category.',
            ))
    return findings, notes
