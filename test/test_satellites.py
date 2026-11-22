from unittest import TestCase
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

from owrx.satellites import (
    parseTle,
    findTle,
    splitProfile,
    predictPasses,
    sgp4Available,
    listProfileOptions,
    PassScheduler,
)

ISS_NAME = "ISS (ZARYA)"
ISS_L1 = "1 25544U 98067A   26326.17166235  .00010101  00000+0  18757-3 0  9993"
ISS_L2 = "2 25544  51.6321 238.2738 0007393  52.3454 307.8204 15.49546258596247"
TLE_TEXT = "{0}             \n{1}\n{2}\nNOAA 15                 \n{3}\n{4}\n".format(
    ISS_NAME,
    ISS_L1,
    ISS_L2,
    "1 25338U 98030A   26326.28138103  .00000097  00000+0  57004-4 0  9991",
    "2 25338  98.4992 342.5914 0009261 240.7543 119.2713 14.27186131483840",
)

NOW = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc)


class ProfileOptionsTest(TestCase):
    SDRS = {
        "rtl1": {"name": "Green RTL-SDR |", "profiles": {"p1": {"name": "2m ISS"}, "p2": {"name": "70cm"}}},
        "rtl2": {"profiles": {"p3": {}}},
        "rtl3": {"name": "No profiles"},
    }

    def testPlainDicts(self):
        self.assertEqual(
            listProfileOptions(self.SDRS),
            [
                ("rtl1|p1", "Green RTL-SDR | - 2m ISS"),
                ("rtl1|p2", "Green RTL-SDR | - 70cm"),
                ("rtl2|p3", "rtl2 - p3"),
            ],
        )

    def testRealConfigObjects(self):
        # regression: settings.json is loaded into PropertyLayer objects, which
        # have no .get(); the settings page used to crash with AttributeError
        from owrx.config.dynamic import DynamicConfig

        sdrs = DynamicConfig._toLayer(self.SDRS)
        self.assertEqual(type(sdrs["rtl1"]).__name__, "PropertyLayer")
        self.assertEqual(listProfileOptions(sdrs), listProfileOptions(self.SDRS))

    def testEmpty(self):
        self.assertEqual(listProfileOptions(None), [])
        self.assertEqual(listProfileOptions({}), [])


class TleParsingTest(TestCase):
    def testParse(self):
        data = parseTle(TLE_TEXT)
        self.assertEqual(set(data.keys()), {ISS_NAME, "NOAA 15"})
        self.assertEqual(data[ISS_NAME], (ISS_L1, ISS_L2))

    def testFind(self):
        data = parseTle(TLE_TEXT)
        self.assertEqual(findTle(data, "iss (zarya)")[0], ISS_NAME)
        self.assertEqual(findTle(data, "noaa 15")[0], "NOAA 15")
        self.assertEqual(findTle(data, "ZARYA")[0], ISS_NAME)
        self.assertIsNone(findTle(data, "NOAA 99"))
        self.assertIsNone(findTle({}, "NOAA 15"))

    def testSplitProfile(self):
        self.assertEqual(splitProfile("sdr1|0"), ("sdr1", "0"))
        self.assertEqual(splitProfile("a|b|c"), ("a", "b|c"))
        self.assertEqual(splitProfile("nope"), (None, None))
        self.assertEqual(splitProfile(None), (None, None))


class PassPredictionTest(TestCase):
    def setUp(self):
        if not sgp4Available():
            self.skipTest("sgp4 is not installed")

    def testIssPasses(self):
        passes = predictPasses(ISS_L1, ISS_L2, 47.0, 19.0, 200, NOW, hours=48, minElevation=10)
        self.assertGreater(len(passes), 0)
        prevLos = NOW
        for p in passes:
            self.assertGreater(p["los"], p["aos"])
            self.assertGreaterEqual(p["aos"], prevLos)
            prevLos = p["los"]
            self.assertGreaterEqual(p["aos"], NOW)
            self.assertLessEqual(p["los"], NOW + timedelta(hours=48))
            minutes = (p["los"] - p["aos"]).total_seconds() / 60
            self.assertGreaterEqual(minutes, 2)
            self.assertLessEqual(minutes, 15)
            self.assertGreaterEqual(p["max_elevation"], 10)
            self.assertLessEqual(p["max_elevation"], 90)

    def testMinElevationFilters(self):
        low = predictPasses(ISS_L1, ISS_L2, 47.0, 19.0, 200, NOW, hours=48, minElevation=0)
        high = predictPasses(ISS_L1, ISS_L2, 47.0, 19.0, 200, NOW, hours=48, minElevation=40)
        self.assertGreaterEqual(len(low), len(high))
        for p in high:
            self.assertGreaterEqual(p["max_elevation"], 40)

    def testNaiveTimeAccepted(self):
        a = predictPasses(ISS_L1, ISS_L2, 47.0, 19.0, 200, NOW.replace(tzinfo=None), hours=12)
        b = predictPasses(ISS_L1, ISS_L2, 47.0, 19.0, 200, NOW, hours=12)
        self.assertEqual(a, b)


def _makeSource(profile="rx", users=False):
    source = MagicMock()
    source.getProfileId.return_value = profile
    source.hasClients.return_value = users

    def activate(pid):
        source.getProfileId.return_value = pid

    source.activateProfile.side_effect = activate
    return source


class SchedulerTest(TestCase):
    def setUp(self):
        patcher = patch("owrx.satellites._userClientClass", return_value="USER")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.source = _makeSource()
        self.sched = PassScheduler(getSource=lambda sdr: self.source if sdr == "sdr1" else None, now=lambda: NOW)
        # do not arm real timers
        self.sched._schedule = MagicMock()
        self.entry = {"name": ISS_NAME}
        self.pass_ = {"aos": NOW, "los": NOW + timedelta(minutes=10), "max_elevation": 30}

    def start(self):
        return self.sched.startPass(self.entry, ISS_NAME, self.pass_, "sdr1", "sat")

    def testSwitchAndRestore(self):
        self.assertTrue(self.start())
        self.source.activateProfile.assert_called_once_with("sat")
        self.sched._schedule.assert_called_once()
        self.assertTrue(self.sched.endPass("x", "sdr1"))
        self.assertEqual(self.source.activateProfile.call_args_list[-1][0][0], "rx")
        self.assertEqual(self.source.getProfileId(), "rx")

    def testSkipWhenUsersConnected(self):
        self.source.hasClients.return_value = True
        self.assertFalse(self.start())
        self.source.activateProfile.assert_not_called()
        self.assertEqual(self.sched.active, {})

    def testSkipUnknownSdr(self):
        self.assertFalse(self.sched.startPass(self.entry, ISS_NAME, self.pass_, "other", "sat"))

    def testNoRestoreWhenProfileChangedByUser(self):
        self.assertTrue(self.start())
        self.source.activateProfile("user-choice")
        self.source.activateProfile.reset_mock()
        self.assertFalse(self.sched.endPass("x", "sdr1"))
        self.source.activateProfile.assert_not_called()
        self.assertEqual(self.source.getProfileId(), "user-choice")

    def testOverlappingPassOnSameSdrSkipped(self):
        self.assertTrue(self.start())
        self.assertFalse(self.start())

    def testAlreadyOnPassProfile(self):
        self.source = _makeSource(profile="sat")
        self.assertTrue(self.start())
        self.source.activateProfile.assert_not_called()
        self.sched.endPass("x", "sdr1")
        self.source.activateProfile.assert_not_called()


class DiscordMultipartTest(TestCase):
    def _build(self, suffix, **kwargs):
        import os
        import tempfile
        from owrx.reporting.discord import _buildMultipart

        fd, path = tempfile.mkstemp(suffix=suffix)
        os.write(fd, b"DATA")
        os.close(fd)
        try:
            body, ctype = _buildMultipart({"content": "x"}, path, **kwargs)
            return body, ctype, os.path.basename(path)
        finally:
            os.unlink(path)

    def testPng(self):
        body, ctype, name = self._build(".png")
        self.assertIn(b"Content-Type: image/png", body)
        self.assertIn('filename="{0}"'.format(name).encode(), body)
        self.assertTrue(ctype.startswith("multipart/form-data; boundary="))

    def testMp3(self):
        body, _, _ = self._build(".mp3")
        self.assertIn(b"Content-Type: audio/mpeg", body)

    def testDefaultAndOverride(self):
        body, _, _ = self._build(".xyz")
        self.assertIn(b"Content-Type: application/octet-stream", body)
        body, _, _ = self._build(".png", contentType="text/plain")
        self.assertIn(b"Content-Type: text/plain", body)

    def testNoFile(self):
        from owrx.reporting.discord import _buildMultipart

        body, _ = _buildMultipart({"content": "x"})
        self.assertNotIn(b"filename", body)
