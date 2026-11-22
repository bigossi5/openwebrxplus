/**
 * ncdxf — OpenWebRX+ plugin
 * NCDXF/IARU beacon monitor: shows which beacon should be on air on each of
 * the five beacon frequencies right now and, if the current tuning covers
 * the frequency, whether a signal is visible in the waterfall.
 */

Plugins.ncdxf = {
    _version: 1,
    no_css: true,

    // The 18 beacons in rotation order.
    beacons: ['4U1UN', 'VE8AT', 'W6WX', 'KH6RS', 'ZL6B', 'VK6RBP', 'JA2IGY', 'RR9O', 'VR2B',
              '4S7B', 'ZS6DN', '5Z4B', '4X6TU', 'OH2B', 'CS3B', 'LU4AA', 'OA4B', 'YV5B'],
    // Beacon frequencies in kHz, index f = 0..4.
    freqs: [14100, 18110, 21150, 24930, 28200],

    _interval: null,
    _heardDb: 10,      // max - median level (dB) needed to call a frequency "heard"
    _halfWidthHz: 1000,

    init: function () {
        Plugins.ncdxf._injectCSS();
        Plugins.addButton('ncdxf', '📡 Beacons', Plugins.ncdxf._toggleWindow);
        return true;
    },

    // ---- pure helpers (no DOM, no globals) --------------------------------

    // Slot 0..17 of the 3-minute cycle. The cycle starts at minute 0, 3, 6, ...
    // of every hour (UTC); each slot is 10 seconds long.
    slotAt: function (date) {
        var secInCycle = (date.getUTCMinutes() % 3) * 60 + date.getUTCSeconds();
        return Math.floor(secInCycle / 10);
    },

    // Beacon schedule: every beacon transmits on 14.100 in its own slot, then
    // on 18.110 in the next slot, then 21.150, 24.930 and 28.200 in the
    // following consecutive slots. So on frequency index f (0..4) during slot
    // s the beacon is beacons[(s - f) mod 18]. Example: in slot 1, 4U1UN is
    // on 18.110 (f=1) and VE8AT is on 14.100 (f=0).
    beaconAt: function (slot, f) {
        var n = Plugins.ncdxf.beacons.length;
        return Plugins.ncdxf.beacons[(((slot - f) % n) + n) % n];
    },

    // Seconds left in the current 10 second slot.
    secondsLeftInSlot: function (date) {
        return 10 - (date.getUTCSeconds() % 10);
    },

    // Waterfall bin range [lo, hi] for a frequency +-halfWidthHz, or null when
    // the frequency is not inside the tuned span (centerHz +- bandwidthHz/2).
    binRange: function (freqHz, centerHz, bandwidthHz, nBins, halfWidthHz) {
        var start = centerHz - bandwidthHz / 2;
        var end = centerHz + bandwidthHz / 2;
        if (freqHz < start || freqHz > end || nBins < 2) return null;
        var lo = Math.max(0, Math.floor((freqHz - halfWidthHz - start) / bandwidthHz * nBins));
        var hi = Math.min(nBins - 1, Math.ceil((freqHz + halfWidthHz - start) / bandwidthHz * nBins));
        if (hi < lo) hi = lo;
        return [lo, hi];
    },

    median: function (arr) {
        var a = Array.prototype.slice.call(arr).sort(function (x, y) { return x - y; });
        var m = a.length >> 1;
        return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
    },

    // Returns {state: 'heard'|'quiet'|'nocover', delta: dB or null}.
    assess: function (freqHz, centerHz, bandwidthHz, data, thresholdDb, halfWidthHz) {
        var r = Plugins.ncdxf.binRange(freqHz, centerHz, bandwidthHz, data.length, halfWidthHz);
        if (!r) return { state: 'nocover', delta: null };
        var max = -Infinity;
        for (var i = r[0]; i <= r[1]; i++) if (data[i] > max) max = data[i];
        var delta = max - Plugins.ncdxf.median(data);
        return { state: delta >= thresholdDb ? 'heard' : 'quiet', delta: delta };
    },

    // ---- UI ----------------------------------------------------------------

    _injectCSS: function () {
        var css = [
            '#plugin-button-ncdxf { white-space: nowrap; height: auto; line-height: 16px; }',
            '#ncdxf-table { width: 100%; border-collapse: collapse; margin-top: 6px; }',
            '#ncdxf-table th { color: #aaa; font-weight: normal; font-size: 11px; text-align: left; padding: 2px 6px; }',
            '#ncdxf-table td { padding: 2px 6px; font-size: 12px; }',
            '.ncdxf-heard { color: #2ecc71; font-weight: bold; }',
            '.ncdxf-quiet { color: #aaa; }',
            '.ncdxf-nocover { color: #666; }',
        ].join('\n');
        var style = document.createElement('style');
        style.textContent = css;
        document.head.appendChild(style);
    },

    _buildContent: function () {
        return [
            '<div id="ncdxf-clock" style="font-size:13px;"></div>',
            '<table id="ncdxf-table">',
            '  <thead><tr><th>kHz</th><th>On air now</th><th>Next</th><th>Signal</th></tr></thead>',
            '  <tbody id="ncdxf-body"></tbody>',
            '</table>',
            '<div style="margin-top:6px;font-size:10px;color:#777;">',
            '  Signal = waterfall peak within &plusmn;1 kHz at least 10 dB above the median of the tuned span.',
            '</div>',
        ].join('');
    },

    _toggleWindow: function () {
        var w = Plugins.addWindow('ncdxf', 'NCDXF/IARU Beacons', Plugins.ncdxf._buildContent());
        Plugins.toggleWindow('ncdxf');
        var visible = w && w.style.display !== 'none' && $(w).is(':visible');
        if (visible) Plugins.ncdxf._start(); else Plugins.ncdxf._stop();
    },

    _start: function () {
        Plugins.ncdxf._update();
        if (!Plugins.ncdxf._interval) {
            Plugins.ncdxf._interval = setInterval(Plugins.ncdxf._update, 1000);
        }
    },

    _stop: function () {
        if (Plugins.ncdxf._interval) {
            clearInterval(Plugins.ncdxf._interval);
            Plugins.ncdxf._interval = null;
        }
    },

    _update: function () {
        var self = Plugins.ncdxf;
        var win = document.getElementById('plugin-window-ncdxf');
        var body = document.getElementById('ncdxf-body');
        if (!win || !body) { self._stop(); return; }
        // window closed with its X button: stop polling
        if (!$(win).is(':visible')) { self._stop(); return; }

        var now = new Date();
        var slot = self.slotAt(now);
        var pad = function (n) { return (n < 10 ? '0' : '') + n; };
        document.getElementById('ncdxf-clock').textContent =
            'UTC ' + pad(now.getUTCHours()) + ':' + pad(now.getUTCMinutes()) + ':' + pad(now.getUTCSeconds()) +
            ' — slot ' + (slot + 1) + '/18, next in ' + self.secondsLeftInSlot(now) + ' s';

        var haveSpectrum = typeof wf_data !== 'undefined' && wf_data && wf_data.length &&
            typeof bandwidth !== 'undefined' && bandwidth &&
            typeof center_freq !== 'undefined' && center_freq;

        var rows = [];
        for (var f = 0; f < self.freqs.length; f++) {
            var res = haveSpectrum
                ? self.assess(self.freqs[f] * 1000, center_freq, bandwidth, wf_data, self._heardDb, self._halfWidthHz)
                : { state: 'nocover', delta: null };
            var label = res.state === 'heard' ? 'heard (+' + res.delta.toFixed(0) + ' dB)'
                : res.state === 'quiet' ? 'quiet'
                : 'not covered by current tuning';
            rows.push('<tr><td>' + (self.freqs[f] / 1000).toFixed(3) + '</td>' +
                '<td><b>' + self.beaconAt(slot, f) + '</b></td>' +
                '<td>' + self.beaconAt(slot + 1, f) + '</td>' +
                '<td class="ncdxf-' + res.state + '">' + label + '</td></tr>');
        }
        body.innerHTML = rows.join('');
    },
};
