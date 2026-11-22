import ipaddress
import os
import re
import socket
import subprocess

import logging

logger = logging.getLogger(__name__)

CERT_FILE = "/etc/openwebrx/cert.pem"
KEY_FILE = "/etc/openwebrx/key.pem"
HELPER = "/usr/lib/openwebrx/ssl-helper"

# Keep these in sync with debian/ssl-helper (which re-validates everything).
HOST_RE = re.compile(r"[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")
FQDN_RE = re.compile(r"([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,63}")

# certbot may have to wait for the ACME server, so allow a generous timeout
HELPER_TIMEOUT = 180


class SslManager(object):
    @staticmethod
    def isValidHost(value: str) -> bool:
        return bool(value) and HOST_RE.fullmatch(value) is not None

    @staticmethod
    def isValidFqdn(value: str) -> bool:
        return bool(value) and FQDN_RE.fullmatch(value) is not None

    @staticmethod
    def isValidEmail(value: str) -> bool:
        return bool(value) and EMAIL_RE.fullmatch(value) is not None

    @staticmethod
    def isInstalled() -> bool:
        return os.path.isfile(CERT_FILE) and os.path.isfile(KEY_FILE)

    @staticmethod
    def detectFqdn() -> str:
        try:
            name = socket.getfqdn()
            if name and name != "localhost" and SslManager.isValidHost(name):
                return name
            name = socket.gethostname()
            if name and SslManager.isValidHost(name):
                return name
        except Exception:
            logger.exception("Could not detect the host name")
        return ""

    @staticmethod
    def localAddresses() -> list:
        found = []
        try:
            # connecting a UDP socket sends nothing, it only selects the
            # outgoing interface and therefore the primary LAN address
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("192.0.2.1", 9))
                found.append(s.getsockname()[0])
        except Exception:
            pass
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                found.append(info[4][0])
        except Exception:
            pass
        result = []
        for address in found:
            try:
                parsed = ipaddress.ip_address(address)
            except ValueError:
                continue
            if parsed.is_loopback or address in result:
                continue
            result.append(address)
        return result[:4]

    @staticmethod
    def describe() -> str:
        if not SslManager.isInstalled():
            return "HTTPS is currently off (the receiver is served over plain http)."
        try:
            out = subprocess.run(
                ["openssl", "x509", "-noout", "-subject", "-issuer", "-enddate", "-in", CERT_FILE],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout
        except Exception:
            return "HTTPS is on (certificate details are unavailable)."
        fields = {}
        for line in out.splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                fields[key.strip()] = value.strip()
        subject = fields.get("subject", "")
        issuer = fields.get("issuer", "")
        kind = "self-signed" if subject and subject == issuer else "issued by " + (issuer or "unknown CA")
        expires = fields.get("notAfter", "unknown")
        return "HTTPS is on: {kind} certificate, valid until {expires}.".format(kind=kind, expires=expires)

    @staticmethod
    def _run(args: list) -> None:
        argv = ["sudo", "-n", HELPER] + args
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=HELPER_TIMEOUT)
        except subprocess.TimeoutExpired:
            raise ValueError("The HTTPS helper timed out")
        except FileNotFoundError:
            raise ValueError("sudo is not available on this system")
        if result.returncode != 0:
            output = (result.stderr or result.stdout or "").strip()
            logger.error("ssl-helper %s failed (%d): %s", args[0], result.returncode, output)
            raise ValueError("HTTPS setup failed: " + (output[-500:] or "unknown error (exit {})".format(result.returncode)))

    @staticmethod
    def apply(enabled: bool, letsencrypt: bool, fqdn: str = "", email: str = "") -> None:
        fqdn = (fqdn or "").strip()
        email = (email or "").strip()

        if not enabled:
            SslManager._run(["disable"])
            return

        if letsencrypt:
            if not SslManager.isValidFqdn(fqdn):
                raise ValueError(
                    "Enter a valid public domain name (e.g. sdr.example.com) to get a Let's Encrypt certificate."
                )
            if email and not SslManager.isValidEmail(email):
                raise ValueError("The e-mail address for Let's Encrypt is not valid.")
            SslManager._run(["letsencrypt", fqdn] + ([email] if email else []))
            return

        cn = fqdn or SslManager.detectFqdn()
        if not SslManager.isValidHost(cn):
            raise ValueError("Could not determine a valid host name for the certificate; enter one in the domain field.")
        SslManager._run(["selfsigned", cn] + SslManager.localAddresses())
