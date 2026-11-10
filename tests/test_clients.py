import unittest
from datetime import timedelta
import test_server as fixtures
import server


class ClientTests(unittest.TestCase):
    setUp = fixtures.SalonTests.setUp
    tearDown = fixtures.SalonTests.tearDown
    booking = fixtures.SalonTests.booking
    def test_booking_creates_client_and_reuses_record(self):
        first = server.save_appointment(self.booking())
        second = server.save_appointment(self.booking(start=(self.start + timedelta(hours=1)).isoformat()))
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM clients').fetchone()[0], 1)
            ids = [r['client_id'] for r in db.execute('SELECT * FROM appointments')]
            self.assertEqual(ids[0], ids[1])
        server.initialize()
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM clients').fetchone()[0], 1)

    def test_inactive_status_survives_future_booking(self):
        client = server.save_client(dict(name='Taylor',email='taylor@example.com',active=False))
        server.save_appointment(self.booking(client_id=client))
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT active FROM clients WHERE id=?', (client,)).fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT client_id FROM appointments').fetchone()[0], client)

    def test_profile_rename_preserves_service_snapshots_and_identity(self):
        appointment = server.save_appointment(self.booking(notes='Color formula: 7N'))
        with server.connect() as db:
            client = db.execute('SELECT client_id FROM appointments').fetchone()[0]
        server.save_client(dict(name='Taylor Newname',email='new@example.com',active=True), client)
        server.save_appointment(self.booking(client_id=client,status='completed',notes='Color formula: 7N'), appointment)
        with server.connect() as db:
            row = db.execute('SELECT * FROM appointments').fetchone()
            self.assertEqual(row['client_id'], client)
            self.assertEqual(row['notes'], 'Color formula: 7N')
            self.assertEqual(db.execute('SELECT count(*) FROM clients').fetchone()[0], 1)

    def test_same_name_different_contact_stays_separate(self):
        server.save_appointment(self.booking())
        server.save_appointment(self.booking(email='other@example.com',start=(self.start+timedelta(hours=1)).isoformat()))
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM clients').fetchone()[0], 2)

    def test_invalid_client_does_not_create_appointment(self):
        with self.assertRaisesRegex(ValueError, 'existing client'):
            server.save_appointment(self.booking(client_id=99999))
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM appointments').fetchone()[0], 0)
        with self.assertRaises(ValueError):
            server.save_client(dict(name='Taylor',active='false'))

    def test_legacy_database_backfills_without_changing_history(self):
        server.save_appointment(self.booking(status='completed',notes='Original notes'))
        with server.connect() as db:
            db.execute('UPDATE appointments SET client_id=NULL')
            db.execute('DELETE FROM clients')
            db.execute('DROP INDEX appointments_client_idx')
            db.execute('ALTER TABLE appointments DROP COLUMN client_id')
        server.initialize()
        server.initialize()
        with server.connect() as db:
            row = db.execute('SELECT * FROM appointments').fetchone()
            self.assertTrue(row['client_id'])
            self.assertEqual(row['status'], 'completed')
            self.assertEqual(row['notes'], 'Original notes')
            self.assertEqual(db.execute('SELECT count(*) FROM clients').fetchone()[0], 1)
