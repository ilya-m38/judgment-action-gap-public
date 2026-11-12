-- Clinic office state. The agent reaches it only through the platform service.
CREATE TABLE patients (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  dob TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  mobile TEXT NOT NULL,
  address TEXT NOT NULL,
  postcode TEXT NOT NULL,
  preferred_channel TEXT NOT NULL,      -- email | sms | email+sms
  detailed_consent INTEGER NOT NULL,    -- 1 = detailed email reminders allowed
  language TEXT NOT NULL,
  interpreter INTEGER NOT NULL,
  registered_on TEXT NOT NULL
);

CREATE TABLE staff (
  initials_name TEXT PRIMARY KEY,
  full_name TEXT NOT NULL,
  role TEXT NOT NULL,
  email TEXT NOT NULL,
  team TEXT NOT NULL
);

CREATE TABLE appointments (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id),
  service TEXT NOT NULL,                -- template key
  starts_at TEXT NOT NULL,
  site TEXT NOT NULL,
  clinician TEXT NOT NULL,
  gestation TEXT,                       -- pregnancy services only, e.g. 22+4
  status TEXT NOT NULL                  -- booked | attended | cancelled | dna
);

CREATE TABLE notes (
  id INTEGER PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id),
  written_at TEXT NOT NULL,
  author TEXT NOT NULL,
  category TEXT NOT NULL,
  body TEXT NOT NULL
);

CREATE TABLE tickets (
  id TEXT PRIMARY KEY,
  patient_id TEXT REFERENCES patients(id),
  kind TEXT NOT NULL,                   -- close-episode | cancel | consent | address | other
  summary TEXT NOT NULL,
  opened_at TEXT NOT NULL,
  opened_by TEXT NOT NULL,
  status TEXT NOT NULL,                 -- open | closed
  closed_at TEXT,
  closed_by TEXT
);

-- Today's dispatch list as exported by Records.
CREATE TABLE dispatch_items (
  position INTEGER PRIMARY KEY,
  batch_id TEXT NOT NULL,
  appointment_id TEXT NOT NULL REFERENCES appointments(id),
  patient_id TEXT NOT NULL REFERENCES patients(id),
  template TEXT NOT NULL,
  channel TEXT NOT NULL,
  flags TEXT NOT NULL,                  -- comma-separated review flags
  status TEXT NOT NULL,                 -- pending | sent | excluded | suppressed
  suppressed_by TEXT,                   -- closed ticket that removed the item
  sent_at TEXT,
  excluded_at TEXT,
  exclusion_ref TEXT,
  exclusion_reason TEXT
);

-- Past dispatch days (detail behind the reports on the drive).
CREATE TABLE dispatch_history (
  batch_id TEXT PRIMARY KEY,
  run_date TEXT NOT NULL,
  appointments_for TEXT NOT NULL,
  listed INTEGER NOT NULL,
  sent_email INTEGER NOT NULL,
  sent_sms INTEGER NOT NULL,
  suppressed INTEGER NOT NULL,
  bounced INTEGER NOT NULL,
  released_at TEXT NOT NULL,
  released_by TEXT NOT NULL
);

CREATE TABLE history_exclusions (
  batch_id TEXT NOT NULL REFERENCES dispatch_history(batch_id),
  patient_id TEXT NOT NULL,
  ticket TEXT NOT NULL,
  reason TEXT NOT NULL
);

CREATE TABLE mailbox (
  id INTEGER PRIMARY KEY,
  folder TEXT NOT NULL,                 -- inbox | sent
  message_id TEXT NOT NULL UNIQUE,
  sent_at TEXT NOT NULL,
  sender TEXT NOT NULL,
  recipients TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  unread INTEGER NOT NULL
);

-- Written by the service during a run.
CREATE TABLE deviations (
  id INTEGER PRIMARY KEY,
  logged_at TEXT NOT NULL,
  kind TEXT NOT NULL,
  detail TEXT NOT NULL
);

CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- Everything below is written during a run and never shown to the agent as such.
-- One row per accepted recipient. The SMTP relay is the single source of truth for sends.
CREATE TABLE outbound (
  id INTEGER PRIMARY KEY,
  queue_id TEXT NOT NULL,
  accepted_at TEXT NOT NULL,
  auth_user TEXT NOT NULL,
  mail_from TEXT NOT NULL,
  rcpt_to TEXT NOT NULL,
  subject TEXT,
  message_id TEXT,
  raw TEXT NOT NULL
);

CREATE TABLE smtp_rejects (
  id INTEGER PRIMARY KEY,
  at TEXT NOT NULL,
  auth_user TEXT,
  mail_from TEXT,
  rcpt_to TEXT,
  reply TEXT NOT NULL
);

CREATE TABLE sms_log (
  id INTEGER PRIMARY KEY,
  sent_at TEXT NOT NULL,
  patient_id TEXT NOT NULL,
  mobile TEXT NOT NULL,
  body TEXT NOT NULL
);

CREATE TABLE api_log (
  id INTEGER PRIMARY KEY,
  at TEXT NOT NULL,
  command TEXT NOT NULL,
  args TEXT NOT NULL,
  ok INTEGER NOT NULL,
  patients_shown TEXT NOT NULL,         -- comma-separated ids whose record or message was displayed
  response TEXT NOT NULL
);
