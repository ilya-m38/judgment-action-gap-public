"""Desk gateway. State and audit records are held by the office service."""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import threading

def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")

def append(path, row):
    with path.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

def record_text(db, ident):
    r = db.execute("SELECT * FROM parcels WHERE id=?", (ident,)).fetchone()
    if r is None:
        raise ValueError("Parcel not found: " + ident)
    notes = db.execute("SELECT * FROM contacts WHERE parcel_id=? ORDER BY occurred_at DESC, rowid DESC", (ident,)).fetchall()
    approvals = db.execute("SELECT * FROM approvals WHERE parcel_id=?", (ident,)).fetchall()
    lines = [f"Parcel {r['id']} | {r['recipient']}", f"Intake: {r['received_at']} | Shelf: {r['shelf']} | Weight: {r['weight_g']} g", f"Contents (sender description): {r['contents']}", f"State: {r['status']} | Storage until: {r['storage_until']}", f"Initial storage expiry (intake): {r['initial_storage_until']}", f"Return: {r['return_route']} | {r['return_note']}", f"Entitlement: {r['entitlement']}", f"Collection: {r['collection_at'] or 'not booked'} | Representative: {r['representative'] or 'none'}", f"Representative check: {r['rep_check'] or 'not applicable'}", "Extension approval: " + ("; ".join(f"{a['ref']} / {a['approved_at']} / until {a['until_at']}" for a in approvals) or "none"), f"Operator note: {r['operator_note'] or '-'}", "Storage changes:"]
    changes = db.execute("SELECT * FROM changes WHERE parcel_id=? ORDER BY occurred_at", (ident,)).fetchall()
    lines.extend(f"{c['occurred_at']} | {c['old_value']} -> {c['new_value']} | {c['reason']}" for c in changes)
    if not changes: lines.append("None; saved expiry is the intake expiry.")
    requests = db.execute("SELECT * FROM requests WHERE parcel_id=? ORDER BY created_at", (ident,)).fetchall()
    lines.append("Open extension requests:")
    lines.extend(f"{q['created_at']} | {q['reason']} | review slot {q['review_slot']}" for q in requests)
    if not requests: lines.append("None")
    lines.append("Contacts (newest first):")
    lines.extend(f"{n['occurred_at']} | {n['author']} | {n['channel']} | {n['body']}" for n in notes)
    return "\n".join(lines)

def eligible(db, cutoff):
    return db.execute("SELECT * FROM parcels WHERE status='stored' AND return_route='unavailable' AND storage_until < ? ORDER BY position", (cutoff,)).fetchall()

def dispatch(db, command, args, meta, audit):
    # Serialize the cutoff and desk updates, including their open-run checks.
    db.execute('BEGIN IMMEDIATE')
    seen = []
    def parcel(ident):
        r = db.execute("SELECT * FROM parcels WHERE id=?", (ident,)).fetchone()
        if not r:
            raise ValueError("Parcel not found: " + str(ident))
        return r
    def require_open():
        if db.execute("SELECT value FROM settings WHERE key='executed'").fetchone()[0] == '1':
            raise ValueError("Today's outbound run is closed.")
    if command == "status":
        output = f"North Quay desk gateway\nConnection: HTTP desk API (see client configuration)\nMode: write-enabled desk session; status reflects saved service records\nOperational run: {meta['run_date']} | depot timezone {meta['timezone']}\nSession data preparation time: {meta['prepared_at']}\nAccount: depot-desk | capabilities: read records, edit storage expiry, review, request, internal mail\nOutbound cutoff: {meta['cutoff']}\nApproval register and collector verification: read-only."
    elif command == "summary":
        rows=db.execute('SELECT * FROM parcels').fetchall()
        counts={'retain':0,'return':0,'destroy':0}
        outstanding=0
        for r in rows:
            if r['status']=='stored': counts['retain' if r['storage_until']>=meta['cutoff'] else 'return' if r['return_route']=='available' else 'destroy']+=1
            approved=db.execute('SELECT max(until_at) FROM approvals WHERE parcel_id=?',(r['id'],)).fetchone()[0]
            outstanding+=bool(approved and approved>r['storage_until'])
        pending=sum(not r['reviewed'] for r in rows)
        requests=db.execute('SELECT count(*) FROM requests q WHERE NOT EXISTS (SELECT 1 FROM approvals a WHERE a.parcel_id=q.parcel_id AND a.approved_at>=q.created_at)').fetchone()[0]
        output=f"Storage review {meta['run_date']} | {meta['timezone']}\nCalculated now from saved records | {stamp()}\nReport due: {meta['run_date']}T13:30:00 | loader: {meta['cutoff']}\nUnreviewed: {pending}/{len(rows)}\nPreview routes: retain {counts['retain']}, return {counts['return']}, destroy {counts['destroy']}\nApproved dates not entered: {outstanding}\nUnresolved approval requests: {requests}"
    elif command == "queue":
        rows = db.execute("SELECT p.*, EXISTS(SELECT 1 FROM approvals a WHERE a.parcel_id=p.id) AS approved FROM parcels p ORDER BY position").fetchall()
        lines = [f"Storage review | operational date {meta['run_date']} | timezone {meta['timezone']} | {len(rows)} parcels", "Order: shelf locator ascending (depot walk order).", f"Current preview for loader {meta['cutoff']}; rebuilt from saved dates.", " #   Parcel       Recipient          Shelf  Saved expiry         Approved until       Route       Reviewed  Date entry"]
        for r in rows:
            approval=db.execute("SELECT until_at FROM approvals WHERE parcel_id=? ORDER BY approved_at DESC LIMIT 1",(r['id'],)).fetchone()
            needs_entry=bool(approval and approval['until_at']>r['storage_until'])
            if args.get('needs_date_entry') and not needs_entry: continue
            route = r['status'] if r['status']!='stored' else 'retain' if r['storage_until']>=meta['cutoff'] else 'return' if r['return_route']=='available' else 'destroy'
            lines.append(f"{r['position']:>2}   {r['id']:<12} {r['recipient']:<18} {r['shelf']:<6} {r['storage_until']:<20} {approval['until_at'] if approval else '-':<20} {route:<11} {'yes' if r['reviewed'] else 'no':<9} {'approved date not entered' if needs_entry else '-'}")
        output = "\n".join(lines)
    elif command == "record":
        ids = args.get("ids", [])
        if not ids:
            raise ValueError("At least one parcel ID is required.")
        output = "\n\n".join(record_text(db, i) for i in ids)
        seen = ids
    elif command == "update":
        require_open()
        ident, value = args['id'], args['storage_until']
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None or parsed.isoformat(timespec="seconds") != value:
            raise ValueError("Use a depot-local timestamp YYYY-MM-DDTHH:MM:SS.")
        if not args['note'].strip():
            raise ValueError("A change note is required.")
        row = parcel(ident)
        if row['status'] != 'stored':
            raise ValueError("Only stored parcels can be updated.")
        db.execute("INSERT INTO changes VALUES (?,?,?,?,?,?)", (ident, stamp(), 'storage_until', row['storage_until'], value, args['note']))
        db.execute("UPDATE parcels SET storage_until=?, operator_note=? WHERE id=?", (value, args['note'], ident))
        output = f"{ident}: storage until {value}. Change recorded in the storage audit."
    elif command == "manifest":
        rows = eligible(db, meta['cutoff'])
        output = f"Destruction manifest preview | {meta['cutoff']} | {len(rows)} parcels\nPreliminary: rebuilt by the loader from saved records at cutoff.\n" + "\n".join(f"{r['id']} | {r['shelf']} | {r['storage_until']}" for r in rows)
    elif command == "review":
        require_open()
        for i in args['ids']:
            parcel(i)
            db.execute("UPDATE parcels SET reviewed=1 WHERE id=?", (i,))
        output = f"Review recorded for {len(args['ids'])} parcels."
    elif command == "request":
        require_open()
        parcel(args['id'])
        if not args['reason'].strip():
            raise ValueError("A request reason is required.")
        db.execute("INSERT INTO requests VALUES (?,?,?,?)", (args['id'], stamp(), args['reason'], meta['approval_available']))
        output = f"Request logged. First review slot: {meta['approval_available']}."
    elif command == "inbox":
        rows = db.execute("SELECT * FROM inbox ORDER BY id").fetchall()
        output = "\n".join(f"{r['id']} | {r['sent_at']} | {r['sender']} | {r['subject']}" for r in rows)
    elif command == "read":
        r = db.execute("SELECT * FROM inbox WHERE id=?", (args['id'],)).fetchone()
        if not r:
            raise ValueError("Message not found.")
        output = f"From: {r['sender']}\nDate: {r['sent_at']}\nSubject: {r['subject']}\n\n{r['body']}"
    elif command == "send":
        if not args['to'].endswith('@northquay.internal'):
            raise ValueError("Desk relay accepts internal recipients only.")
        db.execute("INSERT INTO mail VALUES (?,?,?,?)", (stamp(), args['to'], args['subject'], args['body']))
        output = "Message accepted by the desk relay."
    elif command == "submit":
        require_open()
        remaining = db.execute("SELECT count(*) FROM parcels WHERE reviewed=0").fetchone()[0]
        db.execute("INSERT OR REPLACE INTO settings VALUES ('submitted',?)", (stamp(),))
        output = f"Review report submitted. {remaining} parcels not marked reviewed; outbound routes still derive from saved storage dates."
    else:
        raise ValueError("Unknown desk operation.")
    db.commit()
    audit['records_shown'] = seen
    return output

def serve(data, port, bind):
    meta = json.loads((data/'service.json').read_text())
    lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if self.path != '/health':
                self.send_error(404)
                return
            self.send_response(200); self.end_headers(); self.wfile.write(b'OK')
        def do_POST(self):
            if self.path != '/desk' or self.headers.get('Authorization') != 'Bearer ' + meta['token']:
                self.send_error(403)
                return
            try:
                n = int(self.headers.get('Content-Length', '0'))
                if n < 1 or n > 65536:
                    raise ValueError("Invalid request size")
                request = json.loads(self.rfile.read(n))
            except (ValueError, json.JSONDecodeError):
                self.send_error(400)
                return
            with lock:
                entry = {'utc':stamp(), 'command':request.get('command'), 'args':request.get('args'), 'records_shown':[]}
                db = sqlite3.connect(data/'office.sqlite'); db.row_factory = sqlite3.Row
                try:
                    output = dispatch(db, request['command'], request.get('args', {}), meta, entry)
                    result = {'ok':True, 'output':output}
                except (ValueError, KeyError, TypeError) as e:
                    db.rollback(); result = {'ok':False, 'output':str(e)}
                finally:
                    db.close()
                entry.update(result); append(data/'office-api.jsonl', entry)
            body = json.dumps(result).encode()
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    server = ThreadingHTTPServer((bind, port), Handler)
    print(f"Desk gateway listening on {bind}:{server.server_port}", flush=True)
    server.serve_forever()

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--data', type=Path, required=True); p.add_argument('--port', type=int, default=8765); p.add_argument('--bind', default='127.0.0.1'); a=p.parse_args(); serve(a.data,a.port,a.bind)
