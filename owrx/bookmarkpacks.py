"""
Bookmark packs: curated sets of bookmarks shipped as JSON files in the
"bookmark-packs" directory, plus import / export of the editable bookmarks.

Only logic here, no web code. Dependency-light on purpose (no pycsdr).
"""
import json
import logging
import os
import re

from owrx.bookmarks import Bookmark, Bookmarks

logger = logging.getLogger(__name__)

SYSTEM_DIR = "/usr/share/openwebrx/bookmark-packs"
PACK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
MAX_PACK_BOOKMARKS = 1000
MAX_IMPORT_BOOKMARKS = 5000
MAX_NAME_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 300

# used when the mode registry cannot be loaded (for example in unit tests)
FALLBACK_MODULATIONS = ("nfm", "wfm", "am", "sam", "lsb", "usb", "cw")


def packDirectory():
    """System directory when installed, repo-relative directory otherwise."""
    if os.path.isdir(SYSTEM_DIR):
        return SYSTEM_DIR
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bookmark-packs")


def _findMode(modulation):
    """Returns (known, mode-or-None). Falls back to a static list without the mode registry."""
    try:
        from owrx.modes import Modes

        mode = Modes.findByModulation(modulation)
        return mode is not None, mode
    except Exception:
        return modulation in FALLBACK_MODULATIONS, None


def sanitizeBookmark(data):
    """
    Validates and normalizes a bookmark dict in place, same rules as the bookmark editor.
    Returns None when ok, otherwise an error message.
    """
    try:
        if not isinstance(data, dict):
            return "Bookmark is not an object"
        if "name" not in data or "frequency" not in data or "modulation" not in data:
            return "Bookmark missing required fields"
        if not isinstance(data["name"], str):
            return "Invalid bookmark name"
        data["name"] = data["name"].strip()[:MAX_NAME_LENGTH]
        if len(data["name"]) == 0:
            return "Empty bookmark name"
        if isinstance(data["frequency"], bool) or isinstance(data["frequency"], float) and not data["frequency"].is_integer():
            return "Frequency must be an integer"
        data["frequency"] = int(data["frequency"])
        if data["frequency"] <= 0:
            return "Frequency must be positive"
        if not isinstance(data["modulation"], str):
            return "Invalid modulation"
        known, mode1 = _findMode(data["modulation"])
        if not known:
            return "Invalid modulation"
        underlying = data.get("underlying") or ""
        if not isinstance(underlying, str):
            return "Incorrect underlying modulation"
        if underlying:
            known2, mode2 = _findMode(underlying)
            if not known2:
                data["underlying"] = ""
            elif mode1 is None or not hasattr(mode1, "underlying") or underlying not in mode1.underlying:
                return "Incorrect underlying modulation"
        else:
            data["underlying"] = ""
        description = data.get("description", "")
        if not isinstance(description, str):
            description = str(description)
        data["description"] = description[:MAX_DESCRIPTION_LENGTH]
        if "scannable" in data and not isinstance(data["scannable"], bool):
            return "Invalid scannable flag"
    except Exception as e:
        return str(e)
    return None


def _validPackId(packId):
    return isinstance(packId, str) and PACK_ID_PATTERN.match(packId) is not None


def validatePack(pack):
    """Returns None if the pack structure is valid, otherwise an error message."""
    if not isinstance(pack, dict):
        return "Pack is not an object"
    if not _validPackId(pack.get("id")):
        return "Invalid pack id"
    if not isinstance(pack.get("name"), str) or not pack["name"].strip():
        return "Missing pack name"
    bookmarks = pack.get("bookmarks")
    if not isinstance(bookmarks, list) or len(bookmarks) == 0:
        return "Pack has no bookmarks"
    if len(bookmarks) > MAX_PACK_BOOKMARKS:
        return "Too many bookmarks in pack"
    for b in bookmarks:
        error = sanitizeBookmark(dict(b) if isinstance(b, dict) else b)
        if error is not None:
            return "{0}: {1}".format(b.get("name", "?") if isinstance(b, dict) else "?", error)
    return None


def loadPack(packId, directory=None):
    """Loads one pack by id, returns the dict or None if missing / invalid."""
    if not _validPackId(packId):
        return None
    directory = directory or packDirectory()
    path = os.path.join(directory, packId + ".json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            pack = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(pack, dict) or pack.get("id") != packId:
        return None
    error = validatePack(pack)
    if error is not None:
        logger.warning("bookmark pack %s is invalid: %s", packId, error)
        return None
    return pack


def installedCount(packId, store=None):
    store = store or Bookmarks.getSharedInstance()
    return sum(1 for b in store.getEditableBookmarks() if getattr(b, "pack", "") == packId)


def listPacks(directory=None, store=None):
    """List of dicts: id, name, description, source, count, installed (number of bookmarks in use)."""
    directory = directory or packDirectory()
    result = []
    try:
        files = sorted(f for f in os.listdir(directory) if f.endswith(".json"))
    except OSError:
        return result
    store = store or Bookmarks.getSharedInstance()
    editable = store.getEditableBookmarks()
    for f in files:
        pack = loadPack(f[: -len(".json")], directory)
        if pack is None:
            continue
        installed = sum(1 for b in editable if getattr(b, "pack", "") == pack["id"])
        result.append(
            {
                "id": pack["id"],
                "name": pack["name"],
                "description": pack.get("description", ""),
                "source": pack.get("source", ""),
                "count": len(pack["bookmarks"]),
                "installed": installed,
            }
        )
    return result


def _addBookmarks(items, store, packId=""):
    """Adds sanitized bookmarks, skipping existing frequencies. Returns (added, skipped, invalid)."""
    existing = {b.getFrequency() for b in store.getEditableBookmarks()}
    added = skipped = invalid = 0
    for item in items:
        data = {}
        if isinstance(item, dict):
            for key in ["name", "frequency", "modulation", "underlying", "description", "scannable"]:
                if key in item:
                    data[key] = item[key]
        if sanitizeBookmark(data) is not None:
            invalid += 1
            continue
        if data["frequency"] in existing:
            skipped += 1
            continue
        if packId:
            data["pack"] = packId
        bookmark = Bookmark(data)
        store.addBookmark(bookmark)
        existing.add(bookmark.getFrequency())
        added += 1
    if added:
        store.store()
    return added, skipped, invalid


def installPack(packId, directory=None, store=None):
    """Installs a pack. Returns {"added": n, "skipped": n}. Raises ValueError for unknown packs."""
    pack = loadPack(packId, directory)
    if pack is None:
        raise ValueError("Unknown or invalid bookmark pack")
    store = store or Bookmarks.getSharedInstance()
    added, skipped, invalid = _addBookmarks(pack["bookmarks"], store, packId)
    return {"added": added, "skipped": skipped}


def removePack(packId, store=None):
    """Removes all editable bookmarks tagged with the pack id. Returns the number removed."""
    if not _validPackId(packId):
        raise ValueError("Invalid pack id")
    store = store or Bookmarks.getSharedInstance()
    victims = [b for b in store.getEditableBookmarks() if getattr(b, "pack", "") == packId]
    for b in victims:
        store.removeBookmark(b)
    if victims:
        store.store()
    return len(victims)


def exportBookmarks(store=None):
    """JSON text with all editable bookmarks."""
    store = store or Bookmarks.getSharedInstance()
    return json.dumps([b.__dict__() for b in store.getEditableBookmarks()], indent=4)


def importBookmarks(text, store=None):
    """
    Imports a JSON list of bookmarks (the export format). Existing frequencies are skipped, the
    pack tag is dropped. Raises ValueError on malformed input.
    """
    if isinstance(text, (bytes, bytearray)):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Not valid UTF-8")
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError("Not valid JSON")
    if isinstance(data, dict) and isinstance(data.get("bookmarks"), list):
        data = data["bookmarks"]
    if not isinstance(data, list):
        raise ValueError("Expected a list of bookmarks")
    if len(data) > MAX_IMPORT_BOOKMARKS:
        raise ValueError("Too many bookmarks")
    store = store or Bookmarks.getSharedInstance()
    added, skipped, invalid = _addBookmarks(data, store)
    return {"added": added, "skipped": skipped, "invalid": invalid}
