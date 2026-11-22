import os
import tempfile
import unittest
from unittest.mock import MagicMock

from owrx.activity import ActivityStore, bandFromFrequency, adifField, adifRecord, adifRecords, adifDocument

NOW = 1_700_000_000  # 2023-11-14 22:13:20 UTC


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ActivityStore(os.path.join(self.tmp.name, "activity.db"), retentionDays=90)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_roundtrip(self):
        self.assertTrue(self.store.addSpot(NOW, "FT8", "DL1ABC", "JO62", 14074000, -12, "CQ DL1ABC JO62", now=NOW))
        self.assertTrue(self.store.addEvent(NOW, "20m", 14200000, "signal_alert", 3.5, now=NOW))
        spots = self.store.spots(NOW - 10)
        self.assertEqual(len(spots), 1)
        self.assertEqual(spots[0]["callsign"], "DL1ABC")
        self.assertEqual(spots[0]["db"], -12)
        self.assertEqual(self.store.countSpots(0), 1)
        self.assertEqual(self.store.countEvents(0), 1)
        self.assertEqual(self.store.spots(NOW + 1), [])
        self.assertEqual(len(self.store.spots(0, NOW, limit=1)), 1)

    def test_pruning(self):
        old = NOW - 100 * 86400
        self.store.addEvent(old, "20m", 1, now=old)
        self.store.addSpot(old, "FT8", "OLD", None, 1, now=old)
        self.store.lastPrune = 0
        self.store.addEvent(NOW, "20m", 1, now=NOW)
        self.assertEqual(self.store.countEvents(0), 1)
        self.assertEqual(self.store.countSpots(0), 0)

    def test_prune_at_most_hourly(self):
        self.store.addEvent(NOW, "20m", 1, now=NOW)
        old = NOW - 100 * 86400
        self.store.addEvent(old, "20m", 1, now=NOW + 60)
        self.assertEqual(self.store.countEvents(0), 2)

    def test_heatmap_and_timezone(self):
        # 22:13 UTC
        self.store.addEvent(NOW, "20m", 1, now=NOW)
        self.store.addEvent(NOW + 60, "20m", 1, now=NOW)
        self.store.addEvent(NOW, "40m", 1, now=NOW)
        h = self.store.heatmap(1, now=NOW + 100)
        self.assertEqual(h["total"], 3)
        self.assertEqual(h["max"], 2)
        self.assertEqual(h["bands"]["20m"][22], 2)
        self.assertEqual(h["bands"]["40m"][22], 1)
        shifted = self.store.heatmap(1, tz_offset_minutes=120, now=NOW + 100)
        self.assertEqual(shifted["bands"]["20m"][0], 2)
        self.assertEqual(self.store.heatmap(1, now=NOW + 3 * 86400)["total"], 0)

    def test_write_never_raises(self):
        store = ActivityStore(os.path.join(self.tmp.name, "nonexistent", "x.db"))
        self.assertFalse(store.addEvent(NOW, "20m", 1))
        self.assertFalse(store.addSpot(NOW, "FT8", "A", None, 1))


class BandTest(unittest.TestCase):
    def test_bands(self):
        cases = {
            1840000: "160m", 3573000: "80m", 5357000: "60m", 7074000: "40m", 10136000: "30m",
            14074000: "20m", 18100000: "17m", 21074000: "15m", 24915000: "12m", 28074000: "10m",
            50313000: "6m", 70100000: "4m", 144174000: "2m", 432000000: "70cm", 100000000: "other",
            None: "other",
        }
        for f, b in cases.items():
            self.assertEqual(bandFromFrequency(f), b, f)


class AdifTest(unittest.TestCase):
    def test_field_byte_length(self):
        self.assertEqual(adifField("CALL", "DL1ABC"), "<CALL:6>DL1ABC")
        self.assertEqual(adifField("COMMENT", "café"), "<COMMENT:5>café")

    def test_record(self):
        spot = {"ts": NOW, "mode": "FT8", "callsign": "DL1ABC", "locator": "JO62", "freq": 14074000, "db": -12}
        r = adifRecord(spot, "JO70ab")
        self.assertIn("<CALL:6>DL1ABC", r)
        self.assertIn("<QSO_DATE:8>20231114", r)
        self.assertIn("<TIME_ON:6>221320", r)
        self.assertIn("<BAND:3>20m", r)
        self.assertIn("<FREQ:9>14.074000", r)
        self.assertIn("<MODE:3>FT8", r)
        self.assertIn("<GRIDSQUARE:4>JO62", r)
        self.assertIn("<MY_GRIDSQUARE:6>JO70ab", r)
        self.assertIn("<RST_RCVD:3>-12", r)
        self.assertIn("Heard by OpenWebRX+ (receive only, SNR -12 dB)", r)
        self.assertTrue(r.endswith("<EOR>\n"))

    def test_js8_and_optional(self):
        spot = {"ts": NOW, "mode": "JS8", "callsign": "K1ABC", "locator": None, "freq": 7078000, "db": None}
        r = adifRecord(spot, None)
        self.assertIn("<MODE:4>MFSK", r)
        self.assertIn("<SUBMODE:3>JS8", r)
        self.assertNotIn("GRIDSQUARE", r)
        self.assertNotIn("RST_RCVD", r)

    def test_lengths_parse_back(self):
        import re

        spot = {"ts": NOW, "mode": "WSPR", "callsign": "G0XYZ", "locator": "IO91", "freq": 14095600, "db": -20.5}
        for m in re.finditer(r"<([A-Z_]+):(\d+)>", adifRecords([spot], "AA00aa")):
            pass
        rec = adifRecords([spot], "AA00aa")
        pos = 0
        for m in re.finditer(r"<([A-Z_]+):(\d+)>", rec):
            n = int(m.group(2))
            value = rec[m.end():m.end() + n]
            nxt = rec[m.end() + n:m.end() + n + 1]
            self.assertEqual(nxt, "<", m.group(1))
            self.assertEqual(len(value), n)

    def test_document(self):
        doc = adifDocument([], None)
        self.assertIn("<ADIF_VER:5>3.1.4", doc)
        self.assertIn("<PROGRAMID:10>OpenWebRX+", doc)
        self.assertIn("<EOH>", doc)


class ReporterTest(unittest.TestCase):
    def setUp(self):
        try:
            from owrx.reporting.activitylog import ActivityReporter
        except ImportError as e:
            self.skipTest("owrx.reporting not importable here: {}".format(e))
        self.cls = ActivityReporter

    def test_routing(self):
        store = MagicMock()
        r = self.cls(store)
        self.assertIn("signal_alert", r.getSupportedModes())
        r.spot({"mode": "signal_alert", "name": "20m", "freq": 14200000, "timestamp": 1700000000000, "duration": 2})
        store.addEvent.assert_called_once_with(1700000000, "20m", 14200000, "signal_alert", 2)
        r.spot({"mode": "FT8", "callsign": "DL1ABC", "locator": "JO62", "freq": 14074000, "db": -5, "msg": "m",
                "timestamp": 1700000000000})
        store.addSpot.assert_called_once_with(1700000000, "FT8", "DL1ABC", "JO62", 14074000, -5, "m")
        r.spot({"mode": "FT8", "timestamp": 1700000000000})
        self.assertEqual(store.addSpot.call_count, 1)

    def test_store_error_swallowed(self):
        store = MagicMock()
        store.addEvent.side_effect = RuntimeError("boom")
        self.cls(store).spot({"mode": "signal_alert", "freq": 1, "timestamp": 1000})


if __name__ == "__main__":
    unittest.main()
