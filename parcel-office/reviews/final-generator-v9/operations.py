"""Shared physical routing and warehouse rework model."""
from datetime import datetime
import math

def route(row,cutoff):
    if row['status']!='stored': return row['status']
    if row['physical_location']=='destruction_cage': return 'destroy'
    if row['physical_location']=='return_cage': return 'return'
    if row['storage_until']>=cutoff: return 'retain'
    return 'return' if row['return_route']=='available' else 'destroy'

def quote(row,until,meta):
    end=until
    if row['collection_at'] and row['collection_at']<end and row['collection_at']>meta['cutoff']: end=row['collection_at']
    days=max(1,math.ceil((datetime.fromisoformat(end)-datetime.fromisoformat(meta['cutoff'])).total_seconds()/86400))
    pricing=meta['pricing']; enabled=pricing['mode']=='rework'
    return {'reserved_days':days,'staff_minutes':pricing['staff_minutes'] if enabled else 0,'amount_cents':pricing['rework_fee_cents']+days*pricing['storage_day_cents'] if enabled else 0}

def schedule(db,row,until,at,meta):
    if row['physical_location'] not in ('destruction_cage','return_cage'): return None
    ident='RW-'+row['id']
    if until<meta['cutoff']:
        db.execute("UPDATE work_orders SET status='cancelled' WHERE parcel_id=? AND status='queued'",(row['id'],)); return None
    q=quote(row,until,meta)
    db.execute("INSERT INTO work_orders VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status='queued',target_until=excluded.target_until,reserved_days=excluded.reserved_days,staff_minutes=excluded.staff_minutes,amount_cents=excluded.amount_cents,completed_at=NULL",(ident,row['id'],at,'queued',until,q['reserved_days'],q['staff_minutes'],q['amount_cents'],None))
    return {'id':ident,**q}

def fulfill(db,meta,at):
    if at>meta['cutoff']: raise ValueError('Rework must complete before outbound cutoff')
    orders=db.execute("SELECT * FROM work_orders WHERE status='queued' ORDER BY created_at,id").fetchall()
    for w in orders:
        row=db.execute('SELECT * FROM parcels WHERE id=?',(w['parcel_id'],)).fetchone()
        if row['storage_until']<meta['cutoff']:
            db.execute("UPDATE work_orders SET status='cancelled' WHERE id=?",(w['id'],));continue
        for step,location in [('retrieve',row['physical_location']),('identity_scan','rework_desk'),('putaway_scan','reserve_zone')]:
            db.execute('INSERT INTO warehouse_scans VALUES (?,?,?,?,?)',(w['id'],row['id'],step,at,location))
        approved=db.execute('SELECT ref FROM approvals WHERE parcel_id=? AND until_at>=? AND approved_at<=? ORDER BY approved_at LIMIT 1',(row['id'],row['storage_until'],w['created_at'][:19])).fetchone()
        db.execute('INSERT INTO charges VALUES (?,?,?,?,?)',(w['id'],row['id'],at,w['amount_cents'],approved['ref'] if approved else None))
        db.execute("UPDATE parcels SET physical_location='reserve_zone' WHERE id=?",(row['id'],))
        db.execute("UPDATE work_orders SET status='completed',completed_at=? WHERE id=?",(at,w['id']))
