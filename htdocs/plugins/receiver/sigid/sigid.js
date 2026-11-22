/**
 * sigid — OpenWebRX+ plugin
 * Signal identification helper. Looks at the current tuning (frequency, mode,
 * demodulator passband, bandplan entry, rough occupied bandwidth measured in
 * the waterfall) and lists candidate signal types from a small, deliberately
 * conservative table with the reasons for each match.
 *
 * This is a hint, not a decoder: band allocations differ between regions and
 * the table only contains widely documented facts. Anything not listed is
 * simply not suggested.
 */

Plugins.sigid = {
    _version: 1,
    no_css: true,

    // Table fields:
    //   name     display name
    //   freqs    [[lo, hi], ...] in Hz where it is typically found
    //   modes    modulations a user would normally use to listen to it (informational)
    //   bw       [min, max] typical signal bandwidth in Hz (informational + compared to the measurement)
    //   note     short description
    //   dial     true when freqs are USB dial frequencies; the signal sits ~0-3 kHz above
    // Ranges for dial frequencies are given as [dial, dial + 3000].
    table: [
        { name: 'FT8', dial: true, modes: ['usb', 'ft8'], bw: [40, 60],
          freqs: [[1840000, 1843000], [3573000, 3576000], [5357000, 5360000], [7074000, 7077000],
                  [10136000, 10139000], [14074000, 14077000], [18100000, 18103000],
                  [21074000, 21077000], [24915000, 24918000], [28074000, 28077000],
                  [50313000, 50316000], [144174000, 144177000]],
          note: 'Weak-signal digital mode, 15 s slots, ~50 Hz wide tones inside a ~2.5 kHz USB passband.' },
        { name: 'FT4', dial: true, modes: ['usb', 'ft4'], bw: [70, 100],
          freqs: [[7047500, 7050500], [14080000, 14083000], [21140000, 21143000]],
          note: 'Faster weak-signal digital mode, 7.5 s slots, ~90 Hz wide.' },
        { name: 'WSPR', dial: true, modes: ['usb', 'wspr'], bw: [3, 10],
          freqs: [[1836600, 1836600 + 3000], [3568600, 3568600 + 3000], [7038600, 7038600 + 3000],
                  [10138700, 10138700 + 3000], [14095600, 14095600 + 3000], [18104600, 18104600 + 3000],
                  [21094600, 21094600 + 3000], [24924600, 24924600 + 3000], [28124600, 28124600 + 3000]],
          note: 'Beacon mode, ~6 Hz wide signals inside a 200 Hz window, 2 minute transmissions.' },
        { name: 'NCDXF/IARU beacon', modes: ['cw', 'usb'], bw: [50, 300],
          freqs: [[14099000, 14101000], [18109000, 18111000], [21149000, 21151000],
                  [24929000, 24931000], [28199000, 28201000]],
          note: 'Beacon network on 14.100, 18.110, 21.150, 24.930 and 28.200 MHz; 10 s slots in a 3 minute cycle (see the ncdxf plugin).' },
        { name: 'Time signal (WWV/WWVH)', modes: ['am'], bw: [3000, 10000],
          freqs: [[2499000, 2501000], [4999000, 5001000], [9999000, 10001000],
                  [14999000, 15001000], [19999000, 20001000]],
          note: 'US standard time and frequency stations on 2.5, 5, 10, 15 and 20 MHz, AM with ticks and voice announcements.' },
        { name: 'Time signal (DCF77)', modes: ['am', 'usb', 'lsb'], bw: [50, 500],
          freqs: [[77400, 77600]],
          note: 'German longwave time signal at 77.5 kHz.' },
        { name: 'Time signal (MSF/WWVB)', modes: ['am', 'usb', 'lsb'], bw: [50, 500],
          freqs: [[59900, 60100]],
          note: 'Longwave time signals at 60 kHz (MSF in the UK, WWVB in the USA).' },
        { name: 'Broadcast FM (WFM)', modes: ['wfm'], bw: [150000, 200000],
          freqs: [[87500000, 108000000]],
          note: 'FM broadcast band (87.5-108 MHz in most regions), 200 kHz channel raster with ~150-200 kHz occupied bandwidth.' },
        { name: 'AM broadcast (MW/SW)', modes: ['am', 'sam'], bw: [8000, 10000],
          freqs: [[531000, 1710000], [2300000, 26100000]],
          note: 'Medium wave and shortwave broadcast, AM with 9 or 10 kHz channel spacing (shortwave band edges vary; check the bandplan).' },
        { name: 'Airband voice', modes: ['am'], bw: [6000, 25000],
          freqs: [[118000000, 137000000]],
          note: 'Aeronautical voice, AM, on a 25 kHz or 8.33 kHz channel raster.' },
        { name: 'Maritime VHF voice', modes: ['nfm'], bw: [12500, 25000],
          freqs: [[156000000, 162025000]],
          note: 'Marine VHF channels, narrow FM on a 25 kHz raster; channel 16 (distress/calling) is 156.800 MHz.' },
        { name: 'AIS', modes: ['nfm', 'ais'], bw: [12500, 25000],
          freqs: [[161950000, 162000000], [162000000, 162050000]],
          note: 'Ship position reports, 161.975 and 162.025 MHz, 25 kHz channels, 9600 baud GMSK.' },
        { name: 'NOAA Weather Radio', modes: ['nfm'], bw: [10000, 25000],
          freqs: [[162399000, 162551000]],
          note: 'US/Canada continuous weather broadcast on 162.400-162.550 MHz (seven channels), narrow FM.' },
        { name: 'CB radio', modes: ['am', 'nfm', 'usb', 'lsb'], bw: [2400, 10000],
          freqs: [[26960000, 27410000]],
          note: '11 m citizens band, 40 channels at 10 kHz spacing; AM/FM/SSB depending on country.' },
        { name: 'PMR446', modes: ['nfm'], bw: [6250, 12500],
          freqs: [[446000000, 446200000]],
          note: 'European licence-free handheld radios, 446.0-446.2 MHz, narrow FM.' },
        { name: 'Radiosonde (meteorological aids)', modes: ['nfm', 'sonde'], bw: [3000, 20000],
          freqs: [[400150000, 406000000]],
          note: 'Weather balloon telemetry in the 400.15-406 MHz meteorological aids band.' },
        { name: 'TETRA', modes: ['tetra'], bw: [25000, 25000],
          freqs: [[380000000, 400000000], [410000000, 430000000], [450000000, 470000000]],
          note: 'Digital trunked radio with 25 kHz carriers; typically in 380-400, 410-430 and 450-470 MHz (varies by country).' },
        { name: 'DMR (12.5 kHz TDMA)', modes: ['dmr'], bw: [7000, 12500],
          freqs: [[136000000, 174000000], [400000000, 470000000]],
          note: 'Two-slot TDMA digital voice in 12.5 kHz channels, used on VHF/UHF amateur and land mobile bands.' },
        { name: 'Narrow FM voice (12.5/25 kHz)', modes: ['nfm'], bw: [8000, 25000],
          freqs: [[29000000, 29700000], [50000000, 54000000], [136000000, 174000000],
                  [420000000, 470000000]],
          note: 'Land mobile and amateur FM voice, channel spacing 12.5 or 25 kHz (6.25 kHz in some systems).' },
        { name: 'Amateur CW', modes: ['cw'], bw: [50, 500],
          freqs: [[1810000, 2000000], [3500000, 3800000], [7000000, 7200000], [10100000, 10150000],
                  [14000000, 14350000], [18068000, 18168000], [21000000, 21450000],
                  [24890000, 24990000], [28000000, 29700000]],
          note: 'Morse telegraphy on the HF amateur bands, typically 50-500 Hz wide (band edges vary by region).' },
        { name: 'Amateur SSB voice', modes: ['lsb', 'usb'], bw: [2400, 3000],
          freqs: [[1810000, 2000000], [3500000, 3800000], [7000000, 7200000], [10100000, 10150000],
                  [14000000, 14350000], [18068000, 18168000], [21000000, 21450000],
                  [24890000, 24990000], [28000000, 29700000]],
          note: 'Single sideband voice; by convention LSB below 10 MHz and USB above.' },
    ],

    _interval: null,

    init: function () {
        Plugins.addButton('sigid', '🔎 ID', Plugins.sigid._toggleWindow);
        return true;
    },

    // ---- pure helpers ------------------------------------------------------

    inRanges: function (f, ranges) {
        for (var i = 0; i < ranges.length; i++) {
            if (f >= ranges[i][0] && f <= ranges[i][1]) return true;
        }
        return false;
    },

    // Returns [{entry, score, reasons[]}] sorted by score, best first.
    identify: function (freq, mode, passbandWidth, measuredBw) {
        var out = [];
        Plugins.sigid.table.forEach(function (e) {
            if (!Plugins.sigid.inRanges(freq, e.freqs)) return;
            var score = 3;
            var reasons = [e.dial ? 'frequency matches a usual dial/signal frequency'
                                  : 'frequency is inside its usual range'];
            if (mode) {
                if (e.modes.indexOf(mode) >= 0) {
                    score += 2; reasons.push('mode ' + mode.toUpperCase() + ' is the usual one');
                } else {
                    reasons.push('usual mode: ' + e.modes.join('/').toUpperCase() + ' (current: ' + mode.toUpperCase() + ')');
                }
            }
            if (passbandWidth > 0) {
                if (passbandWidth >= e.bw[0] && passbandWidth <= e.bw[1] * 1.6) {
                    score += 1; reasons.push('passband ' + Math.round(passbandWidth) + ' Hz fits');
                }
            }
            if (measuredBw > 0) {
                if (measuredBw >= e.bw[0] * 0.5 && measuredBw <= e.bw[1] * 1.5) {
                    score += 1; reasons.push('measured width ~' + Math.round(measuredBw) + ' Hz is plausible');
                } else {
                    reasons.push('measured width ~' + Math.round(measuredBw) + ' Hz is outside ' +
                                 e.bw[0] + '-' + e.bw[1] + ' Hz');
                }
            }
            out.push({ entry: e, score: score, reasons: reasons });
        });
        out.sort(function (a, b) { return b.score - a.score; });
        return out;
    },

    // Rough occupied bandwidth around freq (Hz) from one waterfall line.
    // Returns {bw: Hz|null, peakDb, floorDb, note}.
    measure: function (data, centerHz, spanHz, freq, searchHz) {
        var n = data.length;
        if (!n || !spanHz) return { bw: null, note: 'no waterfall data' };
        var range = (typeof Waterfall !== 'undefined' && Waterfall.getRange) ? Waterfall.getRange() : null;
        if (range && isFinite(range.max - range.min) && range.max - range.min < 10) {
            return { bw: null, note: 'waterfall level range is too small to measure' };
        }
        var start = centerHz - spanHz / 2;
        var binHz = spanHz / n;
        var ci = Math.round((freq - start) / binHz);
        if (ci < 0 || ci >= n) return { bw: null, note: 'tuned frequency is outside the waterfall' };

        var sorted = Array.prototype.slice.call(data).sort(function (a, b) { return a - b; });
        var floor = sorted[sorted.length >> 1];
        var r = Math.max(2, Math.round(searchHz / binHz));
        var lo = Math.max(0, ci - r), hi = Math.min(n - 1, ci + r), pk = ci;
        for (var i = lo; i <= hi; i++) if (data[i] > data[pk]) pk = i;
        var peak = data[pk];
        if (peak - floor < 10) return { bw: null, peakDb: peak, floorDb: floor, note: 'no clear signal (<10 dB above median)' };

        var thr = floor + Math.min(10, (peak - floor) / 2);
        var gap = Math.max(1, Math.round(100 / binHz));   // tolerate ~100 Hz holes
        var a = pk, b = pk, miss = 0;
        for (var i = pk; i >= 0; i--) { if (data[i] >= thr) { a = i; miss = 0; } else if (++miss > gap) break; }
        miss = 0;
        for (var j = pk; j < n; j++) { if (data[j] >= thr) { b = j; miss = 0; } else if (++miss > gap) break; }
        return { bw: (b - a + 1) * binHz, peakDb: peak, floorDb: floor, note: 'rough, from a single waterfall line' };
    },

    // ---- UI ----------------------------------------------------------------

    _toggleWindow: function () {
        var S = Plugins.sigid;
        var w = Plugins.addWindow('sigid', 'Signal identification',
            '<div id="sigid-head" style="font-size:12px;"></div><div id="sigid-list"></div>' +
            '<div style="margin-top:6px;font-size:10px;color:#777;">Hints from a static table; allocations vary by region. Not a decoder.</div>');
        Plugins.toggleWindow('sigid');
        var visible = w && $(w).is(':visible');
        if (visible) S._start(); else S._stop();
    },

    _start: function () {
        var S = Plugins.sigid;
        S._update();
        if (!S._interval) S._interval = setInterval(S._update, 1000);
    },

    _stop: function () {
        var S = Plugins.sigid;
        if (S._interval) { clearInterval(S._interval); S._interval = null; }
    },

    _bandplanFor: function (freq) {
        var names = [];
        if (typeof bandplan !== 'undefined' && bandplan && bandplan.bands) {
            bandplan.bands.forEach(function (b) {
                if (freq >= b.low_bound && freq <= b.high_bound) {
                    names.push(b.name + (b.tags && b.tags.length ? ' [' + b.tags.join(', ') + ']' : ''));
                }
            });
        }
        return names;
    },

    _update: function () {
        var S = Plugins.sigid;
        var win = document.getElementById('plugin-window-sigid');
        var head = document.getElementById('sigid-head');
        var list = document.getElementById('sigid-list');
        if (!win || !head || !list) { S._stop(); return; }
        if (!$(win).is(':visible')) { S._stop(); return; }

        var freq = UI.getFrequency();
        var mode = UI.getModulation();
        var demod = UI.getDemodulator();
        var bp = demod ? demod.getBandpass() : null;
        var pbw = bp ? Math.abs(bp.high_cut - bp.low_cut) : 0;

        var m = { bw: null, note: 'no waterfall data' };
        if (typeof wf_data !== 'undefined' && wf_data && wf_data.length &&
            typeof bandwidth !== 'undefined' && typeof center_freq !== 'undefined') {
            m = S.measure(wf_data, center_freq, bandwidth, freq, Math.max(pbw, 3000));
        }

        var esc = Utils.htmlEscape;
        head.innerHTML = (freq / 1e6).toFixed(5) + ' MHz, ' + esc((mode || '?').toUpperCase()) +
            ', passband ' + Math.round(pbw) + ' Hz' +
            (m.bw ? ', measured ~' + Math.round(m.bw) + ' Hz' : ' (' + esc(m.note || '') + ')') +
            '<br>Bandplan: ' + (S._bandplanFor(freq).map(esc).join('; ') || 'none');

        var res = S.identify(freq, mode, pbw, m.bw);
        if (!res.length) {
            list.innerHTML = '<div style="margin-top:6px;color:#aaa;">No candidates in the table for this frequency.</div>';
            return;
        }
        list.innerHTML = res.slice(0, 6).map(function (r) {
            return '<div style="margin-top:6px;"><b>' + esc(r.entry.name) + '</b> <span style="color:#888;">(score ' + r.score + ')</span>' +
                '<div style="font-size:11px;color:#aaa;">' + esc(r.entry.note) + '</div>' +
                '<div style="font-size:11px;">' + r.reasons.map(esc).join('; ') + '</div></div>';
        }).join('');
    },
};
