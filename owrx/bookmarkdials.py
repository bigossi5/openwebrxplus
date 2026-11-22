import logging

logger = logging.getLogger(__name__)

SCANNABLE_MODES = ["lsb", "usb", "cw", "am", "sam", "nfm"]


def selectBookmarkDials(bookmarks, existingDials, centerFrequency, maxCount, mode="signal_alert"):
    """
    Pick bookmarks to be monitored by signal_alert services.

    Only scannable bookmarks with a scannable modulation are used. Bookmarks at a
    frequency that is already used by one of the existing dials (any mode) are
    skipped, as are duplicates among the bookmarks. If there are more candidates than
    maxCount, those nearest to the centre frequency are kept.
    """
    taken = set(d["frequency"] for d in existingDials)
    candidates = []
    for bm in bookmarks:
        if not bm.isScannable() or bm.modulation not in SCANNABLE_MODES:
            continue
        if bm.frequency in taken:
            continue
        taken.add(bm.frequency)
        candidates.append(bm)

    candidates.sort(key=lambda b: abs(b.frequency - centerFrequency))
    if maxCount is not None and len(candidates) > maxCount:
        logger.warning(
            "%d scannable bookmarks in range, monitoring only the %d nearest to the center frequency",
            len(candidates),
            maxCount,
        )
        candidates = candidates[: max(maxCount, 0)]

    return [{"mode": mode, "frequency": bm.frequency, "underlying": bm.modulation} for bm in candidates]
