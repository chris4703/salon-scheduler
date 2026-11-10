"""Shared salon calendar. Run with python3 server.py (no dependencies)."""
import json
import os
import sqlite3
import ssl
import smtplib
import threading
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
DB = Path(os.getenv('SALON_DB', str(ROOT / 'data' / 'salon.sqlite3')))
LOCK = threading.RLock()


def connect():
    db = sqlite3.connect(str(DB), timeout=15)
    db.row_factory = sqlite3.Row
    return db


def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS stylists (id INTEGER PRIMARY KEY, name TEXT NOT NULL, color TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chairs (id INTEGER PRIMARY KEY, name TEXT NOT NULL, stylist_id INTEGER REFERENCES stylists(id));
        CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY, client TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', service TEXT NOT NULL, stylist_id INTEGER NOT NULL REFERENCES stylists(id), chair_id INTEGER NOT NULL REFERENCES chairs(id), start TEXT NOT NULL, duration INTEGER NOT NULL, notes TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'confirmed', reminder INTEGER NOT NULL DEFAULT 0, reminder_sent TEXT);
        ''')
        db.execute("CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1)")
        if 'client_id' not in {row['name'] for row in db.execute('PRAGMA table_info(appointments)')}:
            db.execute('ALTER TABLE appointments ADD COLUMN client_id INTEGER REFERENCES clients(id)')
        # Backfill existing bookings once, keeping their original service and contact snapshots.
        for row in db.execute('SELECT * FROM appointments WHERE client_id IS NULL').fetchall():
            ident = resolve_client(db, row['client'], row['email'], row['phone'])
            db.execute('UPDATE appointments SET client_id=? WHERE id=?', (ident, row['id']))
        db.execute('CREATE INDEX IF NOT EXISTS appointments_client_idx ON appointments(client_id)')
        # Fictional starter profiles only; clients and appointments start empty.
        if not db.execute('SELECT 1 FROM stylists').fetchone():
            db.executemany('INSERT INTO stylists(name,color) VALUES (?,?)', [('Alex Morgan', '#a75c43'), ('Jamie Lee', '#687c64'), ('Sam Rivera', '#85719b')])
            db.executemany('INSERT INTO chairs(name,stylist_id) VALUES (?,?)', [('Chair 01', 1), ('Chair 02', 2), ('Chair 03', 3), ('Chair 04', None)])


def contact_key(name, email, phone):
    return (name.strip().casefold(), email.strip().casefold(), ''.join(c for c in phone if c.isdigit()))


def resolve_client(db, name, email, phone):
    key = contact_key(name, email, phone)
    matches = [row for row in db.execute('SELECT * FROM clients')
               if contact_key(row['name'], row['email'], row['phone']) == key]
    if len(matches) == 1:
        return matches[0]['id']
    # Never guess between duplicate records; the appointment picker can select an exact client.
    return db.execute('INSERT INTO clients(name,email,phone) VALUES (?,?,?)', (name, email, phone)).lastrowid


def save_client(data, ident=None):
    name = str(data.get('name', '')).strip()
    email = str(data.get('email', '')).strip()
    phone = str(data.get('phone', '')).strip()
    notes = str(data.get('notes', ''))
    active = data.get('active', True)
    if not name or len(name) > 120:
        raise ValueError('Enter a client name (up to 120 characters).')
    if email and ('@' not in email or '.' not in email.split('@')[-1] or '\n' in email or '\r' in email):
        raise ValueError('Enter a valid email address.')
    if len(email) > 254 or len(phone) > 80 or len(notes) > 4000:
        raise ValueError('Client contact details or notes are too long.')
    if not isinstance(active, bool):
        raise ValueError('Active must be checked or unchecked.')
    with LOCK, connect() as db:
        values = (name, email, phone, notes, int(active))
        if ident:
            if not db.execute('UPDATE clients SET name=?,email=?,phone=?,notes=?,active=? WHERE id=?', values + (ident,)).rowcount:
                raise ValueError('Client not found.')
        else:
            ident = db.execute('INSERT INTO clients(name,email,phone,notes,active) VALUES (?,?,?,?,?)', values).lastrowid
        return ident


def parse_start(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Appointment time must include a timezone.')
    return dt.astimezone(timezone.utc)


def save_appointment(data, ident=None):
    client = str(data.get('client', '')).strip()
    service = str(data.get('service', '')).strip()
    if not client or not service or len(client) > 120 or len(service) > 120:
        raise ValueError('Enter a client name and service (up to 120 characters).')
    start = parse_start(str(data.get('start', '')))
    duration = int(data.get('duration', 60))
    if duration < 15 or duration > 480:
        raise ValueError('Appointments must be between 15 minutes and 8 hours.')
    stylist, chair = int(data['stylist_id']), int(data['chair_id'])
    status = data.get('status', 'confirmed')
    if status not in ('confirmed', 'completed', 'cancelled'):
        raise ValueError('Choose a valid appointment status.')
    email = str(data.get('email', '')).strip()
    if email and ('@' not in email or '.' not in email.split('@')[-1] or '\n' in email or '\r' in email):
        raise ValueError('Enter a valid email address.')
    with LOCK, connect() as db:
        if not db.execute('SELECT 1 FROM stylists WHERE id=?', (stylist,)).fetchone() or not db.execute('SELECT 1 FROM chairs WHERE id=?', (chair,)).fetchone():
            raise ValueError('Choose an existing stylist and chair.')
        old = db.execute('SELECT * FROM appointments WHERE id=?', (ident,)).fetchone() if ident else None
        if ident and not old:
            raise ValueError('This appointment no longer exists. Refresh the calendar.')
        if status != 'cancelled':
            for row in db.execute("SELECT * FROM appointments WHERE status != 'cancelled' AND (stylist_id=? OR chair_id=?)", (stylist, chair)):
                other = parse_start(row['start'])
                if row['id'] != ident and start < other + timedelta(minutes=row['duration']) and start + timedelta(minutes=duration) > other:
                    raise ValueError('That stylist or chair is already booked during this time.')
        sent = old['reminder_sent'] if old and old['start'] == start.isoformat() and old['email'] == email and old['status'] != 'cancelled' else None
        phone = str(data.get('phone', ''))[:80]
        client_id = data.get('client_id')
        if client_id:
            client_id = int(client_id)
            if not db.execute('SELECT 1 FROM clients WHERE id=?', (client_id,)).fetchone():
                raise ValueError('Choose an existing client.')
        elif old and contact_key(client, email, phone) == contact_key(old['client'], old['email'], old['phone']):
            client_id = old['client_id']
        else:
            client_id = resolve_client(db, client, email, phone)
        values = (client, email, phone, service, stylist, chair, start.isoformat(), duration, str(data.get('notes', ''))[:4000], status, int(bool(data.get('reminder'))), sent, client_id)
        fields = 'client,email,phone,service,stylist_id,chair_id,start,duration,notes,status,reminder,reminder_sent,client_id'
        if ident:
            db.execute('UPDATE appointments SET ' + ','.join(f + '=?' for f in fields.split(',')) + ' WHERE id=?', values + (ident,))
        else:
            ident = db.execute('INSERT INTO appointments (' + fields + ') VALUES (' + ','.join('?' for _ in values) + ')', values).lastrowid
        return ident


def send_reminders():
    """Send due reminders; past/cancelled bookings are never mailed."""
    host, sender = os.getenv('SMTP_HOST'), os.getenv('SMTP_FROM')
    if not host or not sender:
        return
    now = datetime.now(timezone.utc)
    with LOCK, connect() as db:
        rows = db.execute("SELECT a.*,s.name AS stylist FROM appointments a JOIN stylists s ON s.id=a.stylist_id WHERE reminder=1 AND reminder_sent IS NULL AND email!='' AND status='confirmed'").fetchall()
        for row in rows:
            start = parse_start(row['start'])
            if not now < start <= now + timedelta(days=3):
                continue
            message = EmailMessage()
            message['From'], message['To'] = sender, row['email']
            message['Subject'] = 'Your upcoming salon appointment'
            # Explicit offset avoids relying on the server's local timezone.
            from zoneinfo import ZoneInfo
            local = start.astimezone(ZoneInfo(os.getenv('SALON_TIMEZONE', 'Etc/UTC')))
            message.set_content('Hi ' + row['client'] + ',\n\nA reminder of your ' + row['service'] + ' appointment with ' + row['stylist'] + ' on ' + local.strftime('%A, %B %d at %I:%M %p %Z') + '.\n\nPlease contact the salon if you need to make a change. We look forward to seeing you!')
            with smtplib.SMTP(host, int(os.getenv('SMTP_PORT', '587')), timeout=20) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if os.getenv('SMTP_USER'):
                    smtp.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
                smtp.send_message(message)
            db.execute('UPDATE appointments SET reminder_sent=? WHERE id=?', (now.isoformat(), row['id']))
            db.commit()


def reminder_loop():
    while True:
        try:
            send_reminders()
        except Exception as exc:
            print('Reminder delivery failed (' + type(exc).__name__ + '); retrying in 60 seconds.', flush=True)
        time.sleep(60)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'public'), **kwargs)

    def respond(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path == '/api/state':
            with connect() as db:
                self.respond({table: [dict(r) for r in db.execute('SELECT * FROM ' + table)] for table in ('stylists', 'chairs', 'appointments', 'clients')} | {'revision': os.getenv('APP_REVISION', 'development'), 'email_configured': bool(os.getenv('SMTP_HOST') and os.getenv('SMTP_FROM'))})
        elif self.path.startswith('/api/'):
            self.respond({'error': 'Not found'}, 404)
        else:
            super().do_GET()

    def do_POST(self):
        self.mutate()

    def do_PUT(self):
        self.mutate()

    def mutate(self):
        # Browser writes must originate from this app; no cross-origin API access.
        origin = self.headers.get('Origin')
        if origin and urlparse(origin).netloc != self.headers.get('Host'):
            return self.respond({'error': 'Origin not allowed'}, 403)
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 16384:
                raise ValueError('Invalid request size.')
            data = json.loads(self.rfile.read(length))
            path = urlparse(self.path).path
            if path == '/api/appointments' and self.command == 'POST':
                ident = save_appointment(data)
            elif path.startswith('/api/appointments/') and self.command == 'PUT':
                ident = save_appointment(data, int(path.rsplit('/', 1)[1]))
            elif path == '/api/clients' and self.command == 'POST':
                ident = save_client(data)
            elif path.startswith('/api/clients/') and self.command == 'PUT':
                ident = save_client(data, int(path.rsplit('/', 1)[1]))
            elif (path == '/api/team' and self.command == 'POST') or (path.startswith('/api/team/') and self.command == 'PUT'):
                name = str(data.get('name', '')).strip()
                if not name or len(name) > 80:
                    raise ValueError('Enter a stylist name (up to 80 characters).')
                with LOCK, connect() as db:
                    if self.command == 'PUT':
                        ident = int(path.rsplit('/', 1)[1])
                        if not db.execute('UPDATE stylists SET name=? WHERE id=?', (name, ident)).rowcount:
                            raise ValueError('Stylist not found.')
                    else:
                        ident = db.execute('INSERT INTO stylists(name,color) VALUES (?,?)', (name, '#687c64')).lastrowid
            elif path.startswith('/api/chairs/') and self.command == 'PUT':
                stylist = data.get('stylist_id') or None
                with LOCK, connect() as db:
                    if stylist and not db.execute('SELECT 1 FROM stylists WHERE id=?', (int(stylist),)).fetchone():
                        raise ValueError('Choose an existing stylist.')
                    ident = int(path.rsplit('/', 1)[1])
                    if not db.execute('UPDATE chairs SET stylist_id=? WHERE id=?', (stylist, ident)).rowcount:
                        raise ValueError('Chair not found.')
            else:
                return self.respond({'error': 'Not found'}, 404)
            self.respond({'id': ident})
        except (ValueError, KeyError, TypeError) as exc:
            self.respond({'error': str(exc) or 'Invalid request.'}, 400)


if __name__ == '__main__':
    initialize()
    threading.Thread(target=reminder_loop, daemon=True).start()
    host, port = os.getenv('HOST', '127.0.0.1'), int(os.getenv('PORT', '8000'))
    print('Salon dashboard: http://' + host + ':' + str(port), flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
