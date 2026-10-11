from pathlib import Path
import pandas as pd

SCHEMAS = {
    'properties.csv': ['property_id', 'property_name', 'units', 'monthly_rent_per_unit', 'occupied_units', 'street_address', 'city', 'state', 'zip_code', 'country', 'full_address'],
    'payments.csv': ['payment_id', 'property_id', 'unit', 'month', 'due_date', 'amount_due', 'amount_paid', 'payment_date', 'status'],
    'expenses.csv': ['expense_id', 'property_id', 'date', 'category', 'amount', 'description'],
    'maintenance.csv': ['request_id', 'property_id', 'date', 'category', 'priority', 'status', 'estimated_cost', 'actual_cost'],
}


def load_data(data_dir):
    data_dir = Path(data_dir)
    frames, warnings = [], []
    numeric = {'units', 'monthly_rent_per_unit', 'occupied_units', 'unit',
               'amount_due', 'amount_paid', 'amount', 'estimated_cost', 'actual_cost'}
    for name, columns in SCHEMAS.items():
        try:
            frame = pd.read_csv(data_dir / name, dtype={'zip_code': 'string'}).reindex(columns=columns)
        except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError):
            frame = pd.DataFrame(columns=columns)
            warnings.append(f'{name}: missing, empty, or unreadable; no records loaded.')
        exact_duplicates = frame.duplicated()
        if exact_duplicates.any():
            warnings.append(f'{name}: {int(exact_duplicates.sum())} exact duplicate records removed.')
            frame = frame.loc[~exact_duplicates].copy()
        id_column = columns[0]
        conflicts = frame[id_column].notna() & frame[id_column].duplicated(keep=False)
        if conflicts.any():
            warnings.append(f'{name}: {int(conflicts.sum())} conflicting records with duplicate IDs excluded; resolve source records.')
            frame = frame.loc[~conflicts].copy()
        for column in numeric.intersection(columns):
            values = pd.to_numeric(frame[column], errors='coerce').replace([float('inf'), -float('inf')], float('nan'))
            if values.isna().any():
                treatment = 'unavailable' if column in {'units', 'occupied_units'} else 'zero'
                warnings.append(f'{name}: missing or invalid {column} values treated as {treatment}.')
            frame[column] = values if column in {'units', 'occupied_units'} else values.fillna(0)
        for column in {'category', 'status', 'priority'}.intersection(columns):
            frame[column] = frame[column].fillna('Unknown').replace(r'^\s*$', 'Unknown', regex=True)
        frame['property_id'] = frame['property_id'].astype('string')
        if name == 'properties.csv':
            frame = frame.dropna(subset=['property_id']).drop_duplicates('property_id')
            frame['property_name'] = frame['property_name'].fillna(frame['property_id'])
            invalid = (frame.units <= 0) | (frame.occupied_units < 0) | (frame.occupied_units > frame.units)
            if invalid.any():
                warnings.append(f'{name}: invalid unit counts; occupancy unavailable for affected properties.')
                frame.loc[invalid, ['units', 'occupied_units']] = float('nan')
        else:
            date_column = 'due_date' if name == 'payments.csv' else 'date'
            dates = pd.to_datetime(frame[date_column], errors='coerce', format='%Y-%m-%d')
            if dates.isna().any():
                warnings.append(f'{name}: records with missing or invalid dates excluded from date-filtered analysis.')
            frame[date_column] = dates
            frame['month'] = dates.dt.strftime('%Y-%m')
        frames.append(frame)
    return (*frames, warnings)

def filter_records(frame, ids, start, end, date_column):
    if pd.Timestamp(start) > pd.Timestamp(end):
        raise ValueError("Start date must be on or before end date")
    return frame[frame.property_id.isin(ids) & frame[date_column].between(pd.Timestamp(start), pd.Timestamp(end))].copy()

def portfolio_totals(properties, payments, expenses):
    income = payments.amount_paid.sum()
    due = payments.amount_due.sum()
    spending = expenses.amount.sum()
    return dict(income=income, due=due, expenses=spending, cash=income-spending, occupancy=occupancy_rate(properties))

def occupancy_rate(properties):
    if properties.empty or properties[["units", "occupied_units"]].isna().any().any():
        return None
    if (properties.units <= 0).any() or (properties.occupied_units < 0).any() or (properties.occupied_units > properties.units).any():
        return None
    return properties.occupied_units.sum() / properties.units.sum()
