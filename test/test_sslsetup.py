from unittest import TestCase
from unittest.mock import patch, MagicMock
import subprocess

from owrx.sslsetup import SslManager, HELPER


def completed(returncode=0, stdout="", stderr=""):
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


class ValidatorTest(TestCase):
    def testFqdnAccepts(self):
        for value in ["sdr.example.com", "a.pl", "my-sdr.sub.example.org", "SDR.Example.COM"]:
            self.assertTrue(SslManager.isValidFqdn(value), value)

    def testFqdnRejects(self):
        for value in [
            "",
            "nodots",
            "a.com; rm -rf /",
            "a.com\nb.com",
            "a.com b.com",
            "*.example.com",
            "-x.example.com",
            "example..com",
            "example.com/../x",
            "example.c",
            "$(id).example.com",
            "a.com\n",
        ]:
            self.assertFalse(SslManager.isValidFqdn(value), repr(value))

    def testHostAcceptsSingleLabelAndDots(self):
        self.assertTrue(SslManager.isValidHost("openwebrexplusnew"))
        self.assertTrue(SslManager.isValidHost("sdr.local"))

    def testHostRejects(self):
        for value in ["", "-evil", "host name", "a;b", "host\n", "a" * 300]:
            self.assertFalse(SslManager.isValidHost(value), repr(value))

    def testEmail(self):
        self.assertTrue(SslManager.isValidEmail("me@example.com"))
        self.assertTrue(SslManager.isValidEmail("a.b+c@sub.example.org"))
        for value in ["", "bad mail", "no-at.example.com", "a@b", "a@b.c", "a@b.com; x", "-x@b.com\n"]:
            self.assertFalse(SslManager.isValidEmail(value), repr(value))


class ApplyTest(TestCase):
    @patch("owrx.sslsetup.SslManager.localAddresses", return_value=["10.10.10.123"])
    @patch("owrx.sslsetup.subprocess.run")
    def testSelfSignedUsesDetectedHostAndAddresses(self, run, _addresses):
        run.return_value = completed()
        with patch("owrx.sslsetup.SslManager.detectFqdn", return_value="sdrhost"):
            SslManager.apply(True, False)
        run.assert_called_once()
        self.assertEqual(
            run.call_args[0][0], ["sudo", "-n", HELPER, "selfsigned", "sdrhost", "10.10.10.123"]
        )

    @patch("owrx.sslsetup.SslManager.localAddresses", return_value=[])
    @patch("owrx.sslsetup.subprocess.run")
    def testSelfSignedPrefersTypedName(self, run, _addresses):
        run.return_value = completed()
        SslManager.apply(True, False, fqdn="typed.example.com")
        self.assertEqual(run.call_args[0][0], ["sudo", "-n", HELPER, "selfsigned", "typed.example.com"])

    @patch("owrx.sslsetup.subprocess.run")
    def testLetsEncryptWithAndWithoutEmail(self, run):
        run.return_value = completed()
        SslManager.apply(True, True, fqdn="sdr.example.com", email="me@example.com")
        self.assertEqual(
            run.call_args[0][0], ["sudo", "-n", HELPER, "letsencrypt", "sdr.example.com", "me@example.com"]
        )
        SslManager.apply(True, True, fqdn="sdr.example.com")
        self.assertEqual(run.call_args[0][0], ["sudo", "-n", HELPER, "letsencrypt", "sdr.example.com"])

    @patch("owrx.sslsetup.subprocess.run")
    def testLetsEncryptRejectsBadInputWithoutRunningAnything(self, run):
        for fqdn, email in [("", ""), ("nodots", ""), ("a.com; rm", ""), ("sdr.example.com", "bad mail")]:
            with self.assertRaises(ValueError):
                SslManager.apply(True, True, fqdn=fqdn, email=email)
        run.assert_not_called()

    @patch("owrx.sslsetup.subprocess.run")
    def testDisable(self, run):
        run.return_value = completed()
        SslManager.apply(False, False)
        self.assertEqual(run.call_args[0][0], ["sudo", "-n", HELPER, "disable"])

    @patch("owrx.sslsetup.subprocess.run")
    def testHelperFailureBecomesValueErrorWithOutput(self, run):
        run.return_value = completed(returncode=7, stderr="ssl-helper: certbot failed (is port 80 free?)")
        with self.assertRaises(ValueError) as ctx:
            SslManager.apply(True, True, fqdn="sdr.example.com")
        self.assertIn("certbot failed", str(ctx.exception))

    @patch("owrx.sslsetup.subprocess.run", side_effect=subprocess.TimeoutExpired("sudo", 180))
    def testTimeout(self, _run):
        with self.assertRaises(ValueError):
            SslManager.apply(True, True, fqdn="sdr.example.com")
