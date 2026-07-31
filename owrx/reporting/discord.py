from owrx.reporting.reporter import FilteredReporter
from owrx.config import Config
from owrx.metrics import Metrics, CounterMetric
from queue import Queue, Full
from urllib import request
from datetime import datetime, timezone
import threading
import json
import os
import uuid
import logging

logger = logging.getLogger(__name__)


PoisonPill = object()


def _buildMultipart(payload: dict, filePath: str = None):
    boundary = uuid.uuid4().hex
    body = (
        "--{boundary}\r\n"
        'Content-Disposition: form-data; name="payload_json"\r\n'
        "Content-Type: application/json\r\n\r\n"
        "{payload}\r\n"
    ).format(boundary=boundary, payload=json.dumps(payload)).encode("utf-8")
    if filePath:
        with open(filePath, "rb") as f:
            fileData = f.read()
        header = (
            "--{boundary}\r\n"
            'Content-Disposition: form-data; name="files[0]"; filename="{name}"\r\n'
            "Content-Type: audio/mpeg\r\n\r\n"
        ).format(boundary=boundary, name=os.path.basename(filePath))
        body += header.encode("utf-8") + fileData + b"\r\n"
    body += "--{boundary}--\r\n".format(boundary=boundary).encode("utf-8")
    return body, "multipart/form-data; boundary={0}".format(boundary)


class Worker(threading.Thread):
    def __init__(self, queue: Queue):
        self.queue = queue
        self.doRun = True
        super().__init__(daemon=True)

    def run(self):
        while self.doRun:
            try:
                spot = self.queue.get()
                if spot is PoisonPill:
                    self.doRun = False
                else:
                    self.uploadSpot(spot)
                    self.queue.task_done()
            except Exception:
                logger.exception("Exception while sending Discord alert")

    def uploadSpot(self, spot):
        config = Config.get()
        url = config["discord_webhook_url"]
        if not url:
            return
        ts = datetime.fromtimestamp(spot["timestamp"] / 1000, tz=timezone.utc)
        content = "\U0001F514 **{name}** — {freq:.4f} MHz\nDuration: {duration:.1f}s\n{time} UTC".format(
            name=spot.get("name", "Signal Alert"),
            freq=spot["freq"] / 1e6,
            duration=spot.get("duration", 0),
            time=ts.strftime("%Y-%m-%d %H:%M:%S"),
        )
        body, contentType = _buildMultipart({"content": content}, spot.get("file"))
        req = request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", contentType)
        request.urlopen(req, timeout=30)


class DiscordReporter(FilteredReporter):
    def __init__(self):
        # max 100 entries
        self.queue = Queue(100)
        # single worker
        Worker(self.queue).start()

        # metrics
        metrics = Metrics.getSharedInstance()
        self.spotCounter = CounterMetric()
        metrics.addMetric("discord.spots", self.spotCounter)

    def stop(self):
        while not self.queue.empty():
            self.queue.get(timeout=1)
            self.queue.task_done()
        self.queue.put(PoisonPill)

    def spot(self, spot):
        try:
            self.queue.put(spot, block=False)
            self.spotCounter.inc()
        except Full:
            logger.warning("Discord Queue overflow, one spot lost")

    def getSupportedModes(self):
        return ["signal_alert"]
