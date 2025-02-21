from owrx.config.core import CoreConfig

import urllib
import threading
import logging
import json
import os
import time
import re

logger = logging.getLogger(__name__)

class WebScraper(object):
    def __init__(self, dataName: str):
        self.refreshPeriod = 60*60*24
        self.lock = threading.Lock()
        self.dataName = dataName
        self.data = []

    # Get name of the cached database file
    def _getCachedDatabaseFile(self):
        return "{0}/{1}".format(CoreConfig().get_data_directory(), self.dataName)

    # Fake generic User-Agent, since at least KiwiSDR website likes that
    def _openUrl(self, url: str):
        hdrs = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0" }
        req  = urllib.request.Request(url, headers = hdrs)
        return urllib.request.urlopen(req)

    # Return the current data
    def getAll(self):
        return self.data

    # Get last downloaded timestamp or 0 for none
    def lastDownloaded(self):
        try:
            file = self._getCachedDatabaseFile()
            if os.path.isfile(file) and os.path.getsize(file) > 0:
                return os.path.getmtime(file)
            else:
                return 0
        except Exception as e:
            return 0

    # Load cached database or refresh it from the web.
    def refresh(self):
        # This file contains cached receivers database
        file = self._getCachedDatabaseFile()
        # If cached database is stale...
        if time.time() - self.lastDownloaded() >= self.refreshPeriod:
            logger.info("Updating {0} database from web...".format(self.dataName))
            # Load receivers list from the web
            data = self._loadFromWeb()
            if data:
                # Save parsed data into a file
                self.saveData(file, data)
                # Update current database
                with self.lock:
                    self.data = data
                return True

        # If no current database, load it from cached file
        if not self.data:
            data = self.loadData(file)
            with self.lock:
                self.data = data
            return True

        # No refresh done
        return False

    # Save database to a given JSON file.
    def saveData(self, file: str, data):
        logger.info("Saving {0} items to '{1}'...".format(len(data), file))
        try:
            with open(file, "w") as f:
                json.dump(data, f, indent=2)
                f.close()
        except Exception as e:
            logger.error("saveData() exception: {0}".format(e))

    # Load database from a given JSON file.
    def loadData(self, file: str):
        logger.info("Loading items from '{0}'...".format(file))
        if not os.path.isfile(file):
            result = []
        else:
            try:
                with open(file, "r") as f:
                    result = json.load(f)
                    f.close()
            except Exception as e:
                logger.error("loadData() exception: {0}".format(e))
                result = []
        # Done
        logger.info("Loaded {0} items from '{1}'...".format(len(result), file))
        return result

    # Scrape web site(s) for data
    def _loadFromWeb(self):
        # Fill in your own method
        return []
