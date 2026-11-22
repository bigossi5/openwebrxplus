"""
Anonymous listener statistics for the public /stats page.

A sampler thread records, once a minute, how many clients are connected and which frequency and
modulation each one is tuned to. Only counts, frequencies and modulations are stored: no IP
addresses, names or other client identifying data ever pass through this module.

Dependency-light on purpose (no pycsdr), heavy imports are done lazily.
"""
import threading
import time
import logging

logger = logging.getLogger(__name__)

SAMPLE_INTERVAL = 60
DEFAULT_BUCKET = 1000
TOP_COUNT = 10
PERIODS = (("24h", 86400), ("7d", 7 * 86400))


def bucketFrequency(freq, bucket=DEFAULT_BUCKET):
    """Rounds a frequency in Hz to the nearest multiple of `bucket` Hz."""
    bucket = max(1, int(bucket))
    return int(round(float(freq) / bucket)) * bucket


def aggregate(rows, bucket=DEFAULT_BUCKET, top=TOP_COUNT):
    """
    rows: iterable of (ts, count, freq, mod) as stored by ActivityStore.addListenerSample.
    Returns {"peak", "average", "samples", "top": [{"freq", "mod", "minutes"}]}.
    "minutes" is the number of listener samples at that frequency (one sample per minute).
    """
    perSample = {}
    buckets = {}
    for ts, count, freq, mod in rows:
        perSample[ts] = max(perSample.get(ts, 0), count or 0)
        if freq is None:
            continue
        key = bucketFrequency(freq, bucket)
        entry = buckets.setdefault(key, {"minutes": 0, "mods": {}})
        entry["minutes"] += 1
        if mod:
            entry["mods"][mod] = entry["mods"].get(mod, 0) + 1
    peak = max(perSample.values(), default=0)
    average = (sum(perSample.values()) / len(perSample)) if perSample else 0.0
    ranked = sorted(buckets.items(), key=lambda kv: (-kv[1]["minutes"], kv[0]))[:top]
    return {
        "peak": peak,
        "average": round(average, 2),
        "samples": len(perSample),
        "top": [
            {
                "freq": freq,
                "mod": max(e["mods"], key=lambda m: (e["mods"][m], m)) if e["mods"] else "",
                "minutes": e["minutes"],
            }
            for freq, e in ranked
        ],
    }


def buildStats(store, current, startedAt, now=None, bucket=DEFAULT_BUCKET):
    """Everything the stats page shows, as plain data."""
    now = time.time() if now is None else now
    result = {"current": int(current), "uptime": max(0, int(now - startedAt)), "periods": {}}
    for label, seconds in PERIODS:
        rows = store.listenerRows(now - seconds)
        result["periods"][label] = aggregate(rows, bucket)
    return result


def collectSamples(clients):
    """
    From the connected clients returns (count, [(freq, mod), ...]). Clients without a running
    demodulator are counted but have no frequency. Looks only at the demodulator properties.
    """
    tuned = []
    count = 0
    for c in list(clients):
        count += 1
        try:
            # do not use getDsp(): it would create a demodulator for idle clients
            dsp = getattr(c, "dsp", None)
            if dsp is None:
                continue
            props = dsp.props
            freq = int(props["center_freq"]) + int(props["offset_freq"])
            try:
                mod = props["mod"]
            except Exception:
                mod = None
            tuned.append((freq, str(mod) if mod else ""))
        except Exception:
            continue
    return count, tuned


class ListenerSampler(object):
    sharedInstance = None
    lock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with ListenerSampler.lock:
            if ListenerSampler.sharedInstance is None:
                ListenerSampler.sharedInstance = ListenerSampler()
            return ListenerSampler.sharedInstance

    @staticmethod
    def isEnabled():
        try:
            from owrx.config import Config

            return bool(Config.get()["stats_page_enabled"])
        except Exception:
            return False

    @staticmethod
    def start():
        sampler = ListenerSampler.getSharedInstance()
        try:
            from owrx.config import Config

            Config.get().wireProperty("stats_page_enabled", lambda enabled: sampler.apply(bool(enabled)))
        except Exception:
            logger.exception("Could not watch stats_page_enabled")
        sampler.apply(ListenerSampler.isEnabled())

    @staticmethod
    def stop():
        ListenerSampler.getSharedInstance().apply(False)

    def __init__(self, interval=SAMPLE_INTERVAL):
        self.interval = interval
        self.thread = None
        self.stopEvent = None
        self.threadLock = threading.Lock()

    def apply(self, enabled):
        with self.threadLock:
            running = self.thread is not None and self.thread.is_alive()
            if enabled and not running:
                self.stopEvent = threading.Event()
                self.thread = threading.Thread(
                    target=self._run, args=(self.stopEvent,), name="ListenerSampler", daemon=True
                )
                self.thread.start()
            elif not enabled and running:
                self.stopEvent.set()
                self.thread = None

    def sampleOnce(self, store=None, clients=None, now=None):
        if store is None:
            from owrx.activity import ActivityStore

            store = ActivityStore.getSharedInstance()
        if clients is None:
            from owrx.client import ClientRegistry

            clients = ClientRegistry.getSharedInstance().clients
        count, tuned = collectSamples(clients)
        return store.addListenerSample(time.time() if now is None else now, count, tuned)

    def _run(self, stopEvent):
        while not stopEvent.is_set():
            try:
                self.sampleOnce()
            except Exception:
                logger.exception("Listener sampling failed")
            stopEvent.wait(self.interval)
