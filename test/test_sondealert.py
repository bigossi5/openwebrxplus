from unittest import TestCase
from owrx.alertcooldown import AlertCooldown
from owrx.reporting.sondealert import SondeAlertLogic
from owrx import geo

T0 = 1700000000.0
RX = {"lat": 52.0, "lon": 21.0}


def spot(**kw):
    s = {
        "mode": "SONDE",
        "source": "N1234567",
        "lat": 52.1,
        "lon": 21.0,
        "altitude": 12000,
        "vspeed": 5.0,
        "speed": 36.0,
        "course": 0,
        "device": "RS41",
        "timestamp": 1000,
    }
    s.update(kw)
    return s


class SondeAlertTest(TestCase):
    def setUp(self):
        AlertCooldown._lastAlert = {}
        self.logic = SondeAlertLogic()

    def run_(self, s, now=T0, radius=50, cooldown=1800, ground=0):
        return self.logic.process(s, RX, radius, cooldown, ground, now)

    def testNearAlert(self):
        out = self.run_(spot())
        self.assertEqual([a["kind"] for a in out], ["near"])
        a = out[0]
        self.assertEqual(a["mode"], "sonde_alert")
        self.assertEqual(a["serial"], "N1234567")
        self.assertIsNone(a["landing"])
        self.assertAlmostEqual(a["distance_km"], 11.1, delta=0.2)

    def testTooFar(self):
        self.assertEqual(self.run_(spot(lat=55.0)), [])

    def testCooldownSuppresses(self):
        self.assertEqual(len(self.run_(spot(), now=T0)), 1)
        self.assertEqual(self.run_(spot(), now=T0 + 100), [])
        self.assertEqual(len(self.run_(spot(), now=T0 + 1801)), 1)

    def testCooldownPerSerial(self):
        self.assertEqual(len(self.run_(spot())), 1)
        self.assertEqual(len(self.run_(spot(source="OTHER123"))), 1)

    def testMissingPositionIgnored(self):
        s = spot()
        del s["lat"]
        self.assertEqual(self.run_(s), [])
        s = spot()
        del s["lon"]
        self.assertEqual(self.run_(s), [])
        self.assertEqual(self.logic.tracks, {})

    def testJunkSerialIgnored(self):
        self.assertEqual(self.run_(spot(source="xxxxxxxx")), [])
        self.assertEqual(self.run_(spot(source=None)), [])

    def testDescentClassification(self):
        d = SondeAlertLogic.isDescending
        self.assertTrue(d(-5.1, 1000, 200))
        self.assertFalse(d(-4.9, 1000, 200))
        self.assertFalse(d(5.0, 1000, 200))
        self.assertFalse(d(-10, 100, 200))
        self.assertFalse(d(None, 1000, 200))

    def testLandingAlertFarSondeLandsNearby(self):
        # 80 km north, descending 10 m/s from 8000 m, moving south at 100 km/h
        # fall time 800 s -> drift 22.2 km south => landing ~58 km away: too far
        s = spot(lat=52.72, vspeed=-10.0, altitude=8000, speed=100.0, course=180)
        out = self.run_(s)
        self.assertEqual(out, [])
        # heavier drift brings the landing point inside the radius
        AlertCooldown._lastAlert = {}
        s = spot(lat=52.72, vspeed=-10.0, altitude=8000, speed=200.0, course=180)
        out = self.run_(s)
        self.assertEqual([a["kind"] for a in out], ["landing"])
        landing = out[0]["landing"]
        self.assertAlmostEqual(landing["distance_km"], geo.haversineKm(52.0, 21.0, landing["lat"], landing["lon"]))
        self.assertLessEqual(landing["distance_km"], 50)

    def testNearAndLandingBoth(self):
        s = spot(vspeed=-8.0, altitude=4000, speed=0.0)
        out = self.run_(s)
        self.assertEqual(sorted(a["kind"] for a in out), ["landing", "near"])
        self.assertIsNotNone(out[0]["landing"])

    def testLandingUsesGround(self):
        # at ground level the sonde is not considered descending
        self.assertEqual([a["kind"] for a in self.run_(spot(vspeed=-8.0, altitude=150), ground=200)], ["near"])

    def testTrackerBoundedAndTtl(self):
        for i in range(600):
            self.run_(spot(source="S%05d" % i, lat=80.0), now=T0 + i)
        self.assertLessEqual(len(self.logic.tracks), 500)
        self.run_(spot(source="LATE0001", lat=80.0), now=T0 + 600 + 4000)
        self.assertEqual(list(self.logic.tracks), ["LATE0001"])
