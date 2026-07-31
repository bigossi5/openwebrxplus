from unittest import TestCase
from owrx.alertcooldown import AlertCooldown as _AlertCooldown


class AlertCooldownTest(TestCase):
    def setUp(self):
        # isolate each test from shared process-wide state
        _AlertCooldown._lastAlert = {}

    def testFirstAlertAlwaysAllowed(self):
        self.assertTrue(_AlertCooldown.shouldAlert(145000000, 30, 1000.0))

    def testWithinCooldownIsBlocked(self):
        self.assertTrue(_AlertCooldown.shouldAlert(145000000, 30, 1000.0))
        self.assertFalse(_AlertCooldown.shouldAlert(145000000, 30, 1005.0))

    def testAfterCooldownIsAllowedAgain(self):
        self.assertTrue(_AlertCooldown.shouldAlert(145000000, 30, 1000.0))
        self.assertTrue(_AlertCooldown.shouldAlert(145000000, 30, 1031.0))

    def testCooldownIsIndependentPerFrequency(self):
        self.assertTrue(_AlertCooldown.shouldAlert(145000000, 30, 1000.0))
        # a different frequency must not be blocked by the first one's cooldown
        self.assertTrue(_AlertCooldown.shouldAlert(433000000, 30, 1000.0))

    def testSurvivesAcrossSeparateCalls(self):
        # simulates the service chain being torn down and rebuilt: the
        # cooldown state must not reset just because a new AlertRecorder
        # instance is created, since it's tracked at module level
        self.assertTrue(_AlertCooldown.shouldAlert(145000000, 30, 1000.0))
        self.assertFalse(_AlertCooldown.shouldAlert(145000000, 30, 1010.0))
