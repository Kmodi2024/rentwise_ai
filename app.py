from pathlib import Path
import importlib

import pandas as pd
import plotly.express as px
import streamlit as st
from insights import build_insights
import market

# A long-running Streamlit session can retain an older imported parser.
# Refresh this small, stateless module when the app script reruns.
importlib.reload(market)

st.set_page_config(page_title='RentWise AI', page_icon='🏠', layout='wide')
DATA = Path(__file__).parent / 'data'
COLORS = ['#2563eb', '#f59e0b', '#14b8a6', '#8b5cf6', '#64748b']
from analytics import SCHEMAS, load_data, filter_records, portfolio_totals

st.markdown('''
<style>
.stApp { background-color: #f5f7fb; color: #172554; }
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1500px; }
[data-testid="stSidebar"] { background-color: #fff; border-right: 1px solid #e2e8f0; }
[data-testid="stMetric"] { background: #fff; border: 1px solid #e2e8f0;
    border-radius: 12px; padding: 20px; height: 100%; }
[data-testid="stMetricLabel"] { color: #64748b; }
[data-testid="stMetricValue"] { color: #172554; font-weight: 650; }
h1, h2, h3 { letter-spacing: -0.025em; }
@media (max-width: 700px) {
    .block-container { padding: 1rem; }
    [data-testid="stMetric"] { padding: 14px; }
    [data-testid="stMetricValue"] { font-size: 1.65rem; }
}
</style>
''', unsafe_allow_html=True)


@st.cache_data
def load(data_version):
    """Cache CSV contents until a source file changes on disk."""
    return load_data(DATA)


@st.cache_data
def load_market(path, data_version):
    """Refresh local market data when its file changes."""
    return pd.read_csv(path, dtype={'RegionName': 'string'})


def chart(fig, currency=False):
    """Use the same responsive presentation for every chart."""
    fig.update_layout(
        template='plotly_white', height=350, autosize=True,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Arial, sans-serif', color='#475569', size=12),
        margin=dict(l=10, r=10, t=20, b=20),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0),
        colorway=COLORS,
    )
    fig.update_xaxes(showgrid=False, automargin=True)
    if fig.layout.xaxis.title.text == 'month':
        fig.update_xaxes(title='Month')
    fig.update_yaxes(gridcolor='#e2e8f0', automargin=True)
    if currency:
        fig.update_yaxes(title='Amount (USD)', tickprefix='$', tickformat=',.0f')
        fig.update_traces(hovertemplate='%{x}<br>$%{y:,.2f}<extra>%{fullData.name}</extra>')
    st.plotly_chart(fig, use_container_width=True,
                   config={'displayModeBar': False, 'responsive': True})


def table(frame):
    """Format display labels and currency without changing source values."""
    labels = {column: column.replace('_', ' ').title() for column in frame.columns}
    money = {'monthly_rent_per_unit', 'amount_due', 'amount_paid', 'amount',
             'estimated_cost', 'actual_cost', 'Rent collected', 'Rent due', 'Expenses', 'Net cash flow'}
    config = {
        labels[column]: st.column_config.NumberColumn(labels[column], format='$%.2f')
        for column in frame.columns if column in money
    }
    st.dataframe(frame.rename(columns=labels), column_config=config,
                 use_container_width=True, hide_index=True)


csv_files = list(SCHEMAS)
data_version = tuple(
    (name, (DATA / name).stat().st_mtime_ns, (DATA / name).stat().st_size) if (DATA / name).exists() else (name, None, None)
    for name in csv_files
)
p, pay, ex, m, data_warnings = load(data_version)
if data_warnings:
    with st.expander('Data quality notes', expanded=True):
        for message in data_warnings:
            st.warning(message)
record_dates = pd.concat([pd.to_datetime(pay['due_date']),
                          pd.to_datetime(ex['date']), pd.to_datetime(m['date'])])
if record_dates.dropna().empty or p.empty:
    st.title('RentWise AI')
    st.info('No dated records or properties available. Add valid CSV records to view portfolio analytics.')
    st.stop()
min_date = record_dates.min().date().replace(day=1)
max_date = (record_dates.max() + pd.offsets.MonthEnd(0)).date()
with st.sidebar:
    st.title('RentWise AI')
    st.caption('PROPERTY MANAGEMENT')
    page = st.radio('Navigation', ['Overview', 'Financial Analytics', 'Rent Tracking',
                                  'Maintenance', 'AI Insights'])
    st.divider()
    st.subheader('Portfolio filters')
    property_ids = p.property_id.tolist()
    property_labels = {row.property_id: f'{row.property_name} ({row.property_id})' for row in p.itertuples()}
    if 'selected_properties' not in st.session_state:
        st.session_state['selected_properties'] = property_ids
    else:
        st.session_state['selected_properties'] = [
            property_id for property_id in st.session_state['selected_properties'] if property_id in property_ids
        ]
    select_all, clear_all = st.columns(2)
    if select_all.button('Select all', key='select_all_properties'):
        st.session_state['selected_properties'] = property_ids
    if clear_all.button('Clear all', key='clear_all_properties'):
        st.session_state['selected_properties'] = []
    selected = st.multiselect('Properties', property_ids, format_func=property_labels.get,
                              key='selected_properties',
                              help='Select one or several properties. Remove a selection with its ? button.')
    st.caption(f'Available dates: {min_date:%b %d, %Y} – {max_date:%b %d, %Y}')
    if st.button('Use all available dates', use_container_width=True):
        st.session_state['filter_start'] = min_date
        st.session_state['filter_end'] = max_date
    # Keep saved selections valid if the CSV date range changes.
    for key, default in [('filter_start', min_date), ('filter_end', max_date)]:
        if key not in st.session_state:
            st.session_state[key] = default
        else:
            st.session_state[key] = max(min_date, min(max_date, st.session_state[key]))
    start = st.date_input('Start date', min_value=min_date, max_value=max_date,
                          key='filter_start')
    end = st.date_input('End date', min_value=min_date, max_value=max_date,
                        key='filter_end')
    st.caption('Dates are inclusive. Rent uses its due date; expenses and maintenance use their record date.')
    st.caption('Filters apply to every view. Occupancy reflects the current property snapshot.')
    st.divider()
    st.caption('Fictional demonstration data')

ids = selected
if start > end:
    st.error('Start date must be on or before end date.')
    st.stop()
pf = p[p.property_id.isin(ids)]
py = filter_records(pay, ids, start, end, 'due_date')
ef = filter_records(ex, ids, start, end, 'date')
mf = filter_records(m, ids, start, end, 'date')

descriptions = {
    'Overview': 'Your portfolio performance at a glance.',
    'Financial Analytics': 'Compare property cash flow and understand spending.',
    'Rent Tracking': 'Monitor collections and review payment records.',
    'Maintenance': 'Track requests, priorities, and service activity.',
    'AI Insights': 'Review explainable signals from your portfolio data.',
}
st.title(page)
st.caption(descriptions[page])
st.markdown(f'**{len(ids)} properties selected** · {start} → {end}')
if not ids or (py.empty and ef.empty and mf.empty):
    st.info('No data matches these filters. Select a property or adjust the date range.')
    st.stop()

totals = portfolio_totals(pf, py, ef)
income, due, expenses, cash, occupancy = (totals[key] for key in ['income', 'due', 'expenses', 'cash', 'occupancy'])
collection_rate = income / due if due > 0 else None
# All analytical summaries use the same filtered records, including partial months.
month_index = pd.Index(pd.period_range(start, end, freq='M').astype(str), name='month')
monthly = pd.DataFrame(index=month_index)
monthly['Rent collected'] = py.groupby('month').amount_paid.sum()
monthly['Rent due'] = py.groupby('month').amount_due.sum()
monthly['Expenses'] = ef.groupby('month').amount.sum()
monthly = monthly.fillna(0)
monthly['Net cash flow'] = monthly['Rent collected'] - monthly['Expenses']
monthly['Collection rate'] = monthly['Rent collected'].div(monthly['Rent due'].where(monthly['Rent due'] > 0))
monthly = monthly.reset_index()
byp = pf[['property_id', 'property_name']].copy().set_index('property_id')
byp['Rent collected'] = py.groupby('property_id').amount_paid.sum()
byp['Rent due'] = py.groupby('property_id').amount_due.sum()
byp['Expenses'] = ef.groupby('property_id').amount.sum()
byp = byp.fillna({'Rent collected': 0, 'Rent due': 0, 'Expenses': 0})
byp['Net cash flow'] = byp['Rent collected'] - byp['Expenses']
byp['Cash flow margin (%)'] = 100 * byp['Net cash flow'].div(byp['Rent collected'].where(byp['Rent collected'] > 0))
byp['Collection rate (%)'] = 100 * byp['Rent collected'].div(byp['Rent due'].where(byp['Rent due'] > 0))
byp = byp.reset_index()

a, b, c, d = st.columns(4)
a.metric('Rent collected', f'${income:,.0f}', help='Sum of rent payments in the selected period.')
b.metric('Tracked expenses', f'${expenses:,.0f}', help='Sum of expense records in the selected period.')
c.metric('Net cash flow', f'${cash:,.0f}', help='Rent collected minus tracked expenses.')
d.metric('Occupancy', f'{occupancy:.0%}' if occupancy is not None else 'N/A', help='Occupied units divided by total units; current snapshot.')
st.write('')

if page == 'Overview':
    with st.container(border=True):
        st.subheader('Monthly performance')
        st.caption('Rent collected and tracked expenses over the selected period')
        fig = px.line(monthly, x='month', y=['Rent collected', 'Expenses', 'Net cash flow'], markers=True,
                      color_discrete_sequence=COLORS)
        fig.update_layout(legend_title_text='')
        chart(fig, currency=True)
        st.caption('Months without recorded activity show zero. Boundary months reflect only the selected dates.')
    with st.container(border=True):
        st.subheader('Property portfolio')
        st.caption('Current property and occupancy records')
        table(pf)

elif page == 'Financial Analytics':
    with st.container(border=True):
        st.subheader('Compare rent with area market data')
        st.markdown('Compare with ZIP-level **Zillow Observed Rent Index (ZORI)** data. [Source: Zillow Research](https://www.zillow.com/research/data/).')
        st.caption('ZORI is a typical market-rent index, not a simple listing average or a bedroom-matched comparable. This compares your current per-unit rent with the mean of available ZORI months in the selected range. Partial months use the published monthly value. Property and date filters apply.')
        market_path = DATA / 'Zip_zori_uc_sfrcondomfr_sm_month.csv'
        with st.expander('Optional: use a different market data file'):
            upload = st.file_uploader('ZIP-level ZORI CSV', type=['csv'])
        if upload is not None or market_path.exists():
            try:
                if upload is not None:
                    market_data = pd.read_csv(upload, dtype={'RegionName': 'string'})
                    source_name = upload.name
                else:
                    market_data = load_market(str(market_path), (market_path.stat().st_mtime_ns, market_path.stat().st_size))
                    source_name = market_path.name
                comparison = market.compare_market(pf, market_data, start, end)
                matched = comparison.dropna(subset=['Area typical rent (USD/month)'])
                if not matched.empty:
                    plotted = matched.copy()
                    plotted['Property / ZIP'] = plotted['property_name'] + ' / ' + plotted['zip_code']
                    plotted = plotted.rename(columns={
                        'Your current rent (USD/month)': 'Your rent',
                        'Area typical rent (USD/month)': 'Area typical rent',
                    })
                    st.subheader('Your rent vs. area typical rent')
                    fig = px.bar(plotted, x='Property / ZIP', y=['Your rent', 'Area typical rent'],
                                 barmode='group', color_discrete_sequence=COLORS)
                    fig.update_layout(legend_title_text='')
                    fig.update_traces(texttemplate='$%{y:,.0f}', textposition='outside', cliponaxis=False)
                    chart(fig, currency=True)
                    st.subheader('Rent difference from area typical rent')
                    st.caption('Negative values mean your rent is below the area benchmark; positive values mean it is above.')
                    fig = px.bar(plotted, x='Property / ZIP', y='Difference (%)',
                                 color_discrete_sequence=[COLORS[2]],
                                 custom_data=['Difference (USD/month)'])
                    fig.update_yaxes(title='Difference from area rent (%)', ticksuffix='%')
                    fig.update_traces(texttemplate='%{y:.1f}%', textposition='outside', cliponaxis=False,
                                      hovertemplate='%{x}<br>Difference: %{y:.1f}%<br>$%{customdata[0]:,.2f}/month<extra></extra>')
                    fig.add_hline(y=0, line_color='#64748b')
                    chart(fig)
                else:
                    st.info('No area rent matches are available to graph for this selection.')
                with st.expander('View comparison values and market coverage'):
                    table(comparison)
                requested_months = len(pd.period_range(start, end, freq='M'))
                if comparison['Months available'].lt(requested_months).any():
                    st.info('Market coverage is incomplete for this selection. Averages use only available months; see the month counts and first/last market months in the table. Missing months are not estimated.')
                if comparison['Area typical rent (USD/month)'].isna().any():
                    st.info('Some properties have no ZIP match or usable rent values in this period; those comparisons remain blank.')
                st.caption(f'Data file: {source_name}. Sample property addresses are fictional; replace them before comparing an actual portfolio.')
            except (OSError, ValueError, pd.errors.EmptyDataError, pd.errors.ParserError) as error:
                st.warning(f'Unable to compare market rents: {error}')
        else:
            st.info('Upload a ZIP-level ZORI CSV to compare area rents.')
    with st.container(border=True):
        st.subheader('Monthly cash flow (USD)')
        fig = px.bar(monthly, x='month', y=['Rent collected', 'Expenses'], barmode='group', color_discrete_sequence=COLORS)
        fig.add_scatter(x=monthly['month'], y=monthly['Net cash flow'], name='Net cash flow', mode='lines+markers', line=dict(color=COLORS[2]))
        fig.update_layout(legend_title_text='')
        chart(fig, currency=True)
    with st.container(border=True):
        st.subheader('Property profitability comparison (USD)')
        st.caption('Profitability uses net cash flow: collected rent minus tracked expenses. Margin is cash flow divided by collected rent; undefined margins display as blank.')
        chart(px.bar(byp, x='property_name', y=['Rent collected', 'Expenses', 'Net cash flow'], barmode='group', labels={'property_name': 'Property'}, color_discrete_sequence=COLORS), currency=True)
    with st.container(border=True):
        st.subheader('Expense breakdown')
        cats = ef.groupby('category', as_index=False).amount.sum()
        if not cats.empty and cats.amount.ne(0).any():
            chart(px.bar(cats, x='category', y='amount', labels={'category': 'Expense category'}, color_discrete_sequence=COLORS), currency=True)
            if cats.amount.ge(0).all():
                fig = px.pie(cats, names='category', values='amount', hole=.6, color_discrete_sequence=COLORS)
                fig.update_traces(textinfo='percent+label', hovertemplate='%{label}<br>$%{value:,.2f}<br>%{percent}<extra></extra>')
                chart(fig)
            table(cats)
        else:
            st.info('No expenses recorded for this selection.')
    with st.container(border=True):
        st.subheader('Property financials')
        table(byp)

elif page == 'Rent Tracking':
    a, b, c = st.columns(3)
    a.metric('Rent due', f'${due:,.0f}')
    b.metric('Uncollected rent', f'${due - income:,.0f}', help='Rent due minus rent collected.')
    c.metric('Rent collection rate', f'{collection_rate:.1%}' if collection_rate is not None else 'N/A', help='Collected rent / rent due. N/A when no positive rent is due.')
    with st.container(border=True):
        st.subheader('Monthly rent collection rate')
        st.caption('Collected rent ÷ rent due. Months with no positive rent due have no rate.')
        if monthly['Collection rate'].notna().any():
            fig = px.line(monthly, x='month', y='Collection rate', markers=True, labels={'month': 'Month', 'Collection rate': 'Collection rate (%)'}, color_discrete_sequence=COLORS)
            fig.update_yaxes(tickformat='.0%')
            fig.update_traces(hovertemplate='%{x}<br>%{y:.1%}<extra></extra>')
            chart(fig)
        else:
            st.info('No positive rent due in this selection; collection rates are unavailable.')
        st.subheader('Collection rate by property')
        if byp['Collection rate (%)'].notna().any():
            fig = px.bar(byp.dropna(subset=['Collection rate (%)']), x='property_name', y='Collection rate (%)', labels={'property_name': 'Property'}, color_discrete_sequence=COLORS)
            fig.update_yaxes(ticksuffix='%')
            fig.update_traces(hovertemplate='%{x}<br>%{y:.1f}%<extra></extra>')
            chart(fig)
    with st.container(border=True):
        st.subheader('Payment status')
        status = py.groupby('status', as_index=False).size()
        if not status.empty:
            chart(px.bar(status, x='status', y='size', labels={'status': 'Payment status', 'size': 'Payment count'}, color_discrete_sequence=COLORS))
        else:
            st.info('No payment records for this selection.')
    with st.container(border=True):
        st.subheader('Payment records')
        table(py)

elif page == 'Maintenance':
    st.metric('Open / in progress', int(mf.status.isin(['Open', 'In Progress']).sum()))
    with st.container(border=True):
        st.subheader('Requests by category')
        if not mf.empty:
            counts = mf.groupby('category', as_index=False).size()
            chart(px.bar(counts, x='category', y='size', labels={'category': 'Maintenance category', 'size': 'Request count'}, color_discrete_sequence=COLORS))
        else:
            st.info('No maintenance requests for this selection.')
    with st.container(border=True):
        st.subheader('Maintenance records')
        table(mf)

else:
    with st.container(border=True):
        st.subheader('Explainable portfolio insights')
        st.caption('Transparent statistical and arithmetic rules. No language model is integrated; no records are sent to external services.')
        st.write('Rent and expense checks use the shared property and date filters. Occupancy checks use the selected properties’ current snapshot. All amounts are USD.')
    findings, coverage_notes = build_insights(pf, py, ef)
    if expenses > income:
        findings.append(dict(
            title='Expenses exceed collected rent',
            explanation=f'Tracked expenses of ${expenses:,.2f} exceed collected rent of ${income:,.2f}, producing net cash flow of ${cash:,.2f}.',
            rule='Flag when tracked expenses are greater than collected rent in the selected period.',
            evidence={'Rent collected (USD)': income, 'Expenses (USD)': expenses, 'Net cash flow (USD)': cash},
            action='Review spending and outstanding balances against source records.',
        ))
    st.caption(f'{len(findings)} review flags for this selection')
    if not findings:
        st.success('No review flags were triggered by the available records and these rules.')
    for finding in findings:
        with st.container(border=True):
            st.subheader(finding['title'])
            st.write(finding['explanation'])
            st.caption(f"Rule: {finding['rule']}")
            st.markdown('**Supporting values**')
            evidence = finding['evidence']
            if isinstance(evidence, dict):
                evidence = pd.DataFrame([evidence])
            table(evidence)
            st.markdown(f"**Suggested action:** {finding['action']}")
    with st.expander('Analysis coverage and limitations', expanded=bool(coverage_notes)):
        st.write('High-expense checks require at least 4 positive expense records per property and category. Credits and zero amounts are excluded from the baseline. Short date ranges can leave too few records for this check.')
        st.write('Missing or invalid numeric values are treated as zero by CSV loading. Check the data quality notes before relying on these flags. Invalid dates are excluded from period analysis.')
        for note in coverage_notes:
            st.caption(note)

st.caption('Cash flow = rent collected − tracked expenses. Occupancy is a current snapshot, not a historical trend.')
