CREATE TABLE parcels (id TEXT PRIMARY KEY, position INTEGER UNIQUE, recipient TEXT, received_at TEXT, shelf TEXT, weight_g INTEGER, contents TEXT, storage_until TEXT, initial_storage_until TEXT, return_route TEXT, return_note TEXT, entitlement TEXT, collection_at TEXT, representative TEXT, rep_check TEXT, operator_note TEXT, status TEXT DEFAULT 'stored', reviewed INTEGER DEFAULT 0);
CREATE TABLE contacts (parcel_id TEXT, occurred_at TEXT, author TEXT, channel TEXT, body TEXT);
CREATE TABLE approvals (parcel_id TEXT, ref TEXT, approved_at TEXT, until_at TEXT);
CREATE TABLE changes (parcel_id TEXT, occurred_at TEXT, field TEXT, old_value TEXT, new_value TEXT, reason TEXT);
CREATE TABLE requests (parcel_id TEXT, created_at TEXT, reason TEXT, review_slot TEXT);
CREATE TABLE inbox (id INTEGER PRIMARY KEY, sent_at TEXT, sender TEXT, subject TEXT, body TEXT);
CREATE TABLE mail (sent_at TEXT, recipient TEXT, subject TEXT, body TEXT);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE dispositions (parcel_id TEXT PRIMARY KEY, route TEXT, executed_at TEXT);
