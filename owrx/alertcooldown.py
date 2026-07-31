import threading


class AlertCooldown(object):
    """
    Tracks last-alert timestamps per frequency, shared process-wide so it
    survives individual recorder/service instances being torn down and
    rebuilt (e.g. by the background service scheduler).
    """

    _lock = threading.Lock()
    _lastAlert = {}

    @classmethod
    def shouldAlert(cls, frequency, cooldown, now):
        with cls._lock:
            last = cls._lastAlert.get(frequency, 0)
            if now - last < cooldown:
                return False
            cls._lastAlert[frequency] = now
            return True
