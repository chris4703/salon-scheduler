import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import server

class SalonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DB = Path(self.temp.name) / 'test.sqlite3'
        server.initialize()
        self.start = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=2)
    def tearDown(self):
        self.temp.cleanup()
    def booking(self, **changes):
        data = dict(client='Taylor', service='Haircut', stylist_id=1, chair_id=1, start=self.start.isoformat(), duration=60, email='taylor@example.com', reminder=True)
        data.update(changes)
        return data
    def test_persistence_and_edit(self):
        ident = server.save_appointment(self.booking())
        server.save_appointment(self.booking(client='Updated client'), ident)
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT client FROM appointments').fetchone()[0], 'Updated client')
    def test_stylist_and_chair_conflicts(self):
        server.save_appointment(self.booking())
        for changes in ({'chair_id':2}, {'stylist_id':2}):
            with self.assertRaisesRegex(ValueError, 'already booked'):
                server.save_appointment(self.booking(**changes))
        server.save_appointment(self.booking(stylist_id=2, chair_id=2))
    def test_adjacent_booking_and_cancellation(self):
        ident = server.save_appointment(self.booking())
        server.save_appointment(self.booking(start=(self.start+timedelta(hours=1)).isoformat()))
        server.save_appointment(self.booking(status='cancelled'), ident)
        server.save_appointment(self.booking())
    def test_invalid_duration_and_timezone(self):
        for changes in ({'duration':0},{'start':'2026-10-13T09:00'},{'stylist_id':999},{'email':'invalid'}):
            with self.assertRaises(ValueError):
                server.save_appointment(self.booking(**changes))
    @patch.dict(os.environ, {'SMTP_HOST':'smtp.example.com','SMTP_FROM':'salon@example.com'}, clear=True)
    @patch('server.smtplib.SMTP')
    def test_reminders_once_and_skip_cancelled_or_past(self, smtp):
        server.save_appointment(self.booking())
        server.save_appointment(self.booking(status='cancelled', stylist_id=2,chair_id=2))
        server.save_appointment(self.booking(start=(self.start-timedelta(days=4)).isoformat()))
        server.send_reminders()
        server.send_reminders()
        self.assertEqual(smtp.return_value.__enter__.return_value.send_message.call_count,1)
    @patch.dict(os.environ, {}, clear=True)
    @patch('server.smtplib.SMTP')
    def test_no_email_configuration_means_no_send(self, smtp):
        server.save_appointment(self.booking())
        server.send_reminders()
        smtp.assert_not_called()

if __name__ == '__main__':
    unittest.main()
