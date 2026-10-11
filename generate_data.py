import csv, random
import argparse
from pathlib import Path
from datetime import date, timedelta
random.seed(42)
parser = argparse.ArgumentParser(description='Generate 36 completed months of fictional property records.')
parser.add_argument('--as-of', type=date.fromisoformat, default=date(2026, 10, 11),
                    help='Reference date in YYYY-MM-DD format (default: 2026-10-11).')
as_of = parser.parse_args().as_of
# Exclude the incomplete reference month, then generate the preceding 36 months.
end_month = as_of.year * 12 + as_of.month - 1
D=Path(__file__).parent/'data'; D.mkdir(exist_ok=True)
def save(name, fields, rows):
 with (D/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
properties=[dict(property_id=f'P{i:02}',property_name=n,units=u,monthly_rent_per_unit=r,occupied_units=o) for i,(n,u,r,o) in enumerate([('Oak Street',4,1450,4),('Maple Court',3,1700,2),('Pine Apartments',5,1200,5),('River House',2,1950,2),('Cedar Lane',4,1350,3)],1)]
# Fictional street addresses; real ZIP areas for demonstrating market-data matching.
addresses = [('101 Sample Oak Street', 'Boston', 'MA', '02108'), ('202 Sample Maple Court', 'Boston', 'MA', '02116'), ('303 Sample Pine Avenue', 'Boston', 'MA', '02118'), ('404 Sample River Road', 'Boston', 'MA', '02127'), ('505 Sample Cedar Lane', 'Boston', 'MA', '02130')]
for property_record, (street, city, state, zipcode) in zip(properties, addresses):
 property_record.update(street_address=street, city=city, state=state, zip_code=zipcode, country='US',
                        full_address=f'{street}, {city}, {state} {zipcode}, USA')
save('properties.csv',list(properties[0]),properties)
payments=[]; expenses=[]; maintenance=[]; pid=1;eid=1;mid=1
for month_index in range(end_month - 36, end_month):
 year, zero_based_month = divmod(month_index, 12)
 month = zero_based_month + 1
 for p in properties:
  for unit in range(1,p['occupied_units']+1):
   due=date(year,month,5); status=random.choices(['Paid','Late','Unpaid'],[.82,.12,.06])[0]; amt=p['monthly_rent_per_unit']; paid=amt if status!='Unpaid' else 0
   payment_date=(due+timedelta(days=(random.randint(1,10) if status=='Late' else -random.randint(0,4)))).isoformat() if paid else ''
   payments.append(dict(payment_id=f'PAY{pid:04}',property_id=p['property_id'],unit=unit,month=f'{year}-{month:02}',due_date=due.isoformat(),amount_due=amt,amount_paid=paid,payment_date=payment_date,status=status));pid+=1
  for cat in ['Utilities','Insurance','Maintenance','Taxes']:
   base={'Utilities':230,'Insurance':170,'Maintenance':160,'Taxes':320}[cat]
   amount=round(base*random.uniform(.6,1.5),2)
   if p['property_id']=='P02' and year==2026 and month==8 and cat=='Maintenance': amount=2600
   expenses.append(dict(expense_id=f'EXP{eid:04}',property_id=p['property_id'],date=f'{year}-{month:02}-15',category=cat,amount=amount,description=f'{cat} expense'));eid+=1
  if random.random()<.55:
   cat=random.choice(['Plumbing','HVAC','Electrical','Appliance']); status=random.choice(['Open','In Progress','Closed']); estimate=random.randint(100,700)
   maintenance.append(dict(request_id=f'MNT{mid:04}',property_id=p['property_id'],date=f'{year}-{month:02}-12',category=cat,priority=random.choice(['Low','Medium','High']),status=status,estimated_cost=estimate,actual_cost=estimate+random.randint(-60,120) if status=='Closed' else 0));mid+=1
save('payments.csv',list(payments[0]),payments);save('expenses.csv',list(expenses[0]),expenses);save('maintenance.csv',list(maintenance[0]),maintenance)
print('Generated fictional datasets:',len(payments),'payments',len(expenses),'expenses',len(maintenance),'maintenance')
