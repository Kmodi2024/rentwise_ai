"""Compare current property rents with an uploaded ZIP-level Zillow ZORI CSV."""
import re
import pandas as pd


def compare_market(properties, market, start, end):
    if 'RegionName' not in market:
        raise ValueError('Upload ZIP-level ZORI data with a RegionName column.')
    # CSVs saved by spreadsheet software often change ISO headers to M/D/YYYY.
    dates = {}
    for column in market.columns:
        header = str(column)
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', header):
            date = pd.to_datetime(header, format='%Y-%m-%d', errors='coerce')
        elif re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}', header):
            date = pd.to_datetime(header, format='%m/%d/%Y', errors='coerce')
        else:
            continue
        if pd.notna(date) and str(start)[:7] <= date.strftime('%Y-%m') <= str(end)[:7]:
            dates[column] = date
    months = sorted(dates, key=dates.get)
    if not months:
        raise ValueError('The market file has no monthly data in the selected date range.')
    if len({dates[c].strftime('%Y-%m') for c in months}) != len(months):
        raise ValueError('The market file has duplicate month columns; use one value per month.')
    market = market.copy()
    market['zip_code'] = market.RegionName.astype('string').str.strip().str.replace(r'\.0$', '', regex=True).str.zfill(5)
    if not market.zip_code.str.fullmatch(r'\d{5}').fillna(False).all():
        raise ValueError('RegionName must contain five-digit ZIP codes; city or metro files are unsupported.')
    if market.zip_code.duplicated().any():
        raise ValueError('The upload has multiple rows per ZIP. Use one ZIP-level ZORI series.')
    selected_zips = properties.zip_code.astype('string').str.strip().str.zfill(5)
    market = market.loc[market.zip_code.isin(selected_zips)].copy()
    values = market[months].apply(pd.to_numeric, errors='coerce')
    values = values.where(values.gt(0) & values.lt(float('inf')))
    market['Area typical rent (USD/month)'] = values.mean(axis=1)
    market['Months available'] = values.notna().sum(axis=1)
    market['First market month'] = [next((dates[c].strftime('%Y-%m') for c in months if pd.notna(row[c])), None) for _, row in values.iterrows()]
    market['Last market month'] = [next((dates[c].strftime('%Y-%m') for c in reversed(months) if pd.notna(row[c])), None) for _, row in values.iterrows()]
    result = properties[['property_id', 'property_name', 'zip_code', 'monthly_rent_per_unit']].copy()
    result['zip_code'] = result.zip_code.astype('string').str.strip().str.zfill(5)
    result = result.merge(market[['zip_code', 'Area typical rent (USD/month)', 'Months available', 'First market month', 'Last market month']], on='zip_code', how='left')
    result = result.rename(columns={'monthly_rent_per_unit': 'Your current rent (USD/month)'})
    result['Difference (USD/month)'] = result['Your current rent (USD/month)'] - result['Area typical rent (USD/month)']
    result['Difference (%)'] = 100 * result['Difference (USD/month)'] / result['Area typical rent (USD/month)']
    result['Months available'] = result['Months available'].fillna(0).astype(int)
    return result
