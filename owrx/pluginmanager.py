from owrx.config import Config
from urllib import request
from urllib.error import HTTPError, URLError
import importlib.resources
import zipfile
import tempfile
import shutil
import json
import os
import re
import time
import threading

import logging

logger = logging.getLogger(__name__)


# plugins that are infrastructure, not user-toggleable local plugins
RESERVED_NAMES = {"utils"}

ALLOWED_EXTENSIONS = {".js", ".css", ".json", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".md", ".txt"}

NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# guards against zip bombs: this caps the *decompressed* size, independent of
# the (much smaller) max upload size enforced on the compressed request body
MAX_UNCOMPRESSED_SIZE = 20 * 1024 * 1024

# Fixed remote plugins that ship as part of the default init.js, unrelated to
# locally installed/managed plugins.
REMOTE_PLUGIN_BASE_URL = "https://0xaf.github.io/openwebrxplus-plugins/receiver"

# GitHub's content-listing API is used to enumerate the catalog since the
# plugin repo publishes no machine-readable manifest of its own
REMOTE_CATALOG_API = "https://api.github.com/repos/0xaf/openwebrxplus-plugins/contents/receiver"
REMOTE_CATALOG_CACHE_SECONDS = 600
REMOTE_FETCH_MAX_SIZE = 2 * 1024 * 1024
USER_AGENT = "OpenWebRXplus-PluginManager/1.0"


class PluginManager(object):
    sharedInstance = None
    creationLock = threading.Lock()

    @staticmethod
    def getSharedInstance():
        with PluginManager.creationLock:
            if PluginManager.sharedInstance is None:
                PluginManager.sharedInstance = PluginManager()
        return PluginManager.sharedInstance

    def __init__(self):
        # wireProperty() immediately fires once with the current value, which
        # already triggers the first regenerateInitJs() call
        Config.get().wireProperty("plugins_enabled", self._onEnabledChanged)
        self._catalogCache = None
        self._catalogCacheTime = 0

    def _onEnabledChanged(self, *args):
        self.regenerateInitJs()

    def _pluginsDir(self):
        return str(importlib.resources.files("htdocs").joinpath("plugins/receiver"))

    def _enabledSet(self):
        return set(Config.get()["plugins_enabled"])

    def listPlugins(self):
        base = self._pluginsDir()
        enabled = self._enabledSet()
        result = []
        if not os.path.isdir(base):
            return result
        for name in sorted(os.listdir(base)):
            if name in RESERVED_NAMES:
                continue
            full = os.path.join(base, name)
            if not os.path.isdir(full):
                continue
            jsFile = os.path.join(full, name + ".js")
            if not os.path.isfile(jsFile):
                continue
            manifest = {}
            manifestPath = os.path.join(full, "plugin.json")
            if os.path.isfile(manifestPath):
                try:
                    with open(manifestPath, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                except Exception:
                    logger.exception("Could not parse plugin.json for %s", name)
            result.append({
                "name": name,
                "title": manifest.get("title", name),
                "description": manifest.get("description", ""),
                "version": manifest.get("version", ""),
                "enabled": name in enabled,
            })
        return result

    def install(self, data: bytes) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            zipPath = os.path.join(tmp, "upload.zip")
            with open(zipPath, "wb") as f:
                f.write(data)

            try:
                zf = zipfile.ZipFile(zipPath)
            except zipfile.BadZipFile:
                raise ValueError("Not a valid zip file")

            # always close the ZipFile handle before this function returns,
            # otherwise its file descriptor keeps zipPath locked (breaks
            # TemporaryDirectory cleanup on Windows, and is a leak everywhere)
            with zf:
                entries = [i for i in zf.infolist() if i.filename and not i.filename.endswith("/")]
                if not entries:
                    raise ValueError("Zip file is empty")

                totalUncompressed = sum(e.file_size for e in entries)
                if totalUncompressed > MAX_UNCOMPRESSED_SIZE:
                    raise ValueError("Package too large when uncompressed")

                topLevels = set(e.filename.split("/")[0] for e in entries)
                if len(topLevels) != 1:
                    raise ValueError("Zip must contain exactly one top-level plugin folder")
                pluginName = next(iter(topLevels))

                if not NAME_PATTERN.match(pluginName):
                    raise ValueError("Invalid plugin folder name: " + pluginName)
                if pluginName in RESERVED_NAMES:
                    raise ValueError("'{}' is a reserved name".format(pluginName))

                extractRoot = os.path.join(tmp, "extract")
                os.makedirs(extractRoot)
                prefix = pluginName + "/"

                for entry in entries:
                    name = entry.filename
                    norm = os.path.normpath(name)
                    if norm.startswith("..") or os.path.isabs(norm) or not name.startswith(prefix):
                        raise ValueError("Unsafe path in zip: " + name)
                    ext = os.path.splitext(norm)[1].lower()
                    if ext not in ALLOWED_EXTENSIONS:
                        raise ValueError("Disallowed file type in package: " + name)
                    target = os.path.join(extractRoot, norm)
                    if not os.path.abspath(target).startswith(os.path.abspath(extractRoot) + os.sep):
                        raise ValueError("Unsafe path in zip: " + name)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with zf.open(entry) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)

            jsPath = os.path.join(extractRoot, pluginName, pluginName + ".js")
            if not os.path.isfile(jsPath):
                raise ValueError("Package is missing {0}/{0}.js".format(pluginName))

            dest = os.path.join(self._pluginsDir(), pluginName)
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            shutil.move(os.path.join(extractRoot, pluginName), dest)

            logger.info("Installed plugin '%s'", pluginName)
            return pluginName

    def uninstall(self, name: str):
        if name in RESERVED_NAMES:
            raise ValueError("'{}' is a reserved name".format(name))
        full = os.path.join(self._pluginsDir(), name)
        if not os.path.isdir(full):
            raise ValueError("Plugin not found: " + name)
        shutil.rmtree(full)
        self.setEnabled(name, False)
        logger.info("Uninstalled plugin '%s'", name)

    def _fetchUrl(self, url: str, maxSize: int = REMOTE_FETCH_MAX_SIZE) -> bytes:
        req = request.Request(url)
        # GitHub's API (and its Cloudflare edge) rejects requests with no
        # User-Agent header, same issue we hit with the Discord webhook
        req.add_header("User-Agent", USER_AGENT)
        with request.urlopen(req, timeout=15) as resp:
            data = resp.read(maxSize + 1)
            if len(data) > maxSize:
                raise ValueError("Remote file exceeds the maximum allowed size")
            return data

    def listRemotePlugins(self, forceRefresh: bool = False):
        now = time.time()
        if not forceRefresh and self._catalogCache is not None and now - self._catalogCacheTime < REMOTE_CATALOG_CACHE_SECONDS:
            return self._catalogCache
        try:
            data = self._fetchUrl(REMOTE_CATALOG_API)
            entries = json.loads(data.decode("utf-8"))
        except (HTTPError, URLError, ValueError, json.JSONDecodeError):
            logger.exception("Could not fetch the remote plugin catalog")
            raise ValueError("Could not reach the plugin catalog (check server internet access)")
        names = sorted(
            e["name"] for e in entries
            if e.get("type") == "dir" and e.get("name") not in RESERVED_NAMES
        )
        self._catalogCache = names
        self._catalogCacheTime = now
        return names

    def installFromRemote(self, name: str) -> str:
        if not NAME_PATTERN.match(name):
            raise ValueError("Invalid plugin name: " + name)
        if name in RESERVED_NAMES:
            raise ValueError("'{}' is a reserved name".format(name))

        jsUrl = "{base}/{name}/{name}.js".format(base=REMOTE_PLUGIN_BASE_URL, name=name)
        try:
            jsData = self._fetchUrl(jsUrl)
        except HTTPError as e:
            if e.code == 404:
                raise ValueError("Plugin not found in remote catalog: " + name)
            raise ValueError("Could not download plugin: HTTP {}".format(e.code))
        except URLError:
            raise ValueError("Could not reach the plugin catalog (check server internet access)")

        optionalFiles = {}
        for ext in (".css",):
            try:
                optionalFiles[name + ext] = self._fetchUrl(
                    "{base}/{name}/{name}{ext}".format(base=REMOTE_PLUGIN_BASE_URL, name=name, ext=ext)
                )
            except (HTTPError, URLError):
                pass
        try:
            optionalFiles["plugin.json"] = self._fetchUrl(
                "{base}/{name}/plugin.json".format(base=REMOTE_PLUGIN_BASE_URL, name=name)
            )
        except (HTTPError, URLError):
            pass

        with tempfile.TemporaryDirectory() as tmp:
            stagingDir = os.path.join(tmp, name)
            os.makedirs(stagingDir)
            with open(os.path.join(stagingDir, name + ".js"), "wb") as f:
                f.write(jsData)
            for fname, fdata in optionalFiles.items():
                with open(os.path.join(stagingDir, fname), "wb") as f:
                    f.write(fdata)

            dest = os.path.join(self._pluginsDir(), name)
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            shutil.move(stagingDir, dest)

        logger.info("Installed plugin '%s' from remote catalog", name)
        return name

    def setEnabled(self, name: str, enabled: bool):
        config = Config.get()
        current = set(config["plugins_enabled"])
        if enabled:
            current.add(name)
        else:
            current.discard(name)
        config["plugins_enabled"] = sorted(current)
        config.store()

    def regenerateInitJs(self):
        base = self._pluginsDir()
        if not os.path.isdir(base):
            return
        enabled = [p["name"] for p in self.listPlugins() if p["enabled"]]

        lines = [
            "// Receiver plugins initialization.",
            "// Auto-generated by the Plugin Manager (Settings -> Plugins).",
            "// Manual edits here will be overwritten the next time a plugin is",
            "// installed, uninstalled, enabled, or disabled.",
            "",
            "const rp_url = '{}';".format(REMOTE_PLUGIN_BASE_URL),
            "",
            "Plugins.load(rp_url + '/utils/utils.js').then(async function () {",
        ]
        for name in enabled:
            lines.append("    Plugins.load('{}');".format(name))
        lines += [
            "",
            "    await Plugins.load(rp_url + '/notify/notify.js');",
            "    Plugins.load(rp_url + '/colorful_spectrum/colorful_spectrum.js');",
            "    Plugins.load(rp_url + '/connect_notify/connect_notify.js');",
            "});",
            "",
        ]
        content = "\n".join(lines)

        target = os.path.join(base, "init.js")
        try:
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            logger.exception("Could not write init.js")
