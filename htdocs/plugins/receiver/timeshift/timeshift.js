/**
 * timeshift — OpenWebRX+ plugin
 * Keeps a ring buffer of the most recent decoded audio (Int16 PCM, taken just
 * before the browser-side resampler) and lets you listen to it again with a
 * delay ("Back 10s/30s/1min/5min"), then return to the live stream.
 *
 * While replaying, live audio keeps being recorded but is not sent to the
 * audio worklet, so the replay behaves like a delayed live stream. Live audio
 * is dropped from the worklet by intercepting audioNode.port.postMessage;
 * the gain node is never touched, so the volume control keeps working.
 *
 * Configuration (set in init.js before the plugin loads, optional):
 *   Plugins.timeshift.buffer_seconds = 300;   // history length
 *   Plugins.timeshift.max_bytes      = 60e6;  // hard memory cap
 *
 * Requires AudioWorklet support (not the ScriptProcessor fallback).
 * Memory use: 2 bytes per sample per channel at the server audio rate
 * (e.g. 12 kHz mono = 24 kB/s).
 */

Plugins.timeshift = {
    _version: 1,
    no_css: true,

    buffer_seconds: 300,
    max_bytes: 60e6,

    _chunks: [],        // {seq, t, rate, ch: [Int16Array...]}
    _bytes: 0,
    _seq: 0,
    _installed: false,
    _installTimer: null,
    _wrappedPort: null,

    _replaying: false,
    _cursor: 0,         // next seq to schedule
    _nextStart: 0,      // audioContext time of next scheduled sample
    _sources: [],
    _tickTimer: null,

    init: function () {
        var T = Plugins.timeshift;
        Plugins.addButton('timeshift', '⏪ Timeshift', T._toggleWindow);
        T._tryInstall();
        if (!T._installed) T._installTimer = setInterval(T._tryInstall, 500);
        return true;
    },

    // ---- recording ---------------------------------------------------------

    _tryInstall: function () {
        var T = Plugins.timeshift;
        if (T._installed) return;
        if (typeof audioEngine === 'undefined' || !audioEngine ||
            !audioEngine.resampler || !audioEngine.hdResampler) return;
        // NOTE: Plugins.utils.wrap_func does not return the wrapped function's
        // result, which resampler.process needs, so wrap by hand.
        T._wrap(audioEngine.resampler, false);
        T._wrap(audioEngine.hdResampler, true);
        T._installed = true;
        if (T._installTimer) { clearInterval(T._installTimer); T._installTimer = null; }
    },

    _wrap: function (resampler, hd) {
        var orig = resampler.process;
        resampler.process = function (data) {
            try {
                Plugins.timeshift._record(data, hd);
            } catch (e) {
                console.error('timeshift: record failed', e);
            }
            return orig.call(this, data);
        };
    },

    _record: function (data, hd) {
        var T = Plugins.timeshift;
        var rate = hd ? audioEngine.getHdOutputRate() : audioEngine.getOutputRate();
        var ch = [];
        var bytes = 0;
        for (var i = 0; i < data.length && i < 2; i++) {
            var c = new Int16Array(data[i]);   // copy: the decoder may reuse its buffers
            ch.push(c);
            bytes += c.byteLength;
        }
        if (!ch.length || !ch[0].length) return;
        T._chunks.push({ seq: T._seq++, t: performance.now() / 1000, rate: rate, ch: ch });
        T._bytes += bytes;

        var oldest = performance.now() / 1000 - T.buffer_seconds;
        while (T._chunks.length > 1 &&
               (T._bytes > T.max_bytes || T._chunks[0].t < oldest)) {
            var c0 = T._chunks.shift();
            for (var k = 0; k < c0.ch.length; k++) T._bytes -= c0.ch[k].byteLength;
        }
    },

    _historySeconds: function () {
        var T = Plugins.timeshift;
        if (!T._chunks.length) return 0;
        return performance.now() / 1000 - T._chunks[0].t;
    },

    // ---- replay ------------------------------------------------------------

    _ensureWorkletIntercept: function () {
        var T = Plugins.timeshift;
        var node = audioEngine.audioNode;
        if (!node || !node.port) return false;
        if (T._wrappedPort === node.port) return true;
        var port = node.port;
        var orig = port.postMessage;
        port.postMessage = function (msg) {
            // let command strings (getStats) through; drop audio while replaying
            if (Plugins.timeshift._replaying && typeof msg !== 'string') return;
            return orig.apply(port, arguments);
        };
        T._wrappedPort = port;
        return true;
    },

    back: function (seconds) {
        var T = Plugins.timeshift;
        if (!T._installed) { T._status('Audio engine not ready'); return; }
        if (!audioEngine.gainNode || !audioEngine.audioContext) {
            T._status('Audio not started yet (click the page / enable audio)');
            return;
        }
        if (!T._ensureWorkletIntercept()) {
            T._status('Needs AudioWorklet support; not available here');
            return;
        }
        if (!T._chunks.length) { T._status('Nothing recorded yet'); return; }

        T._stopSources();
        var target = performance.now() / 1000 - seconds;
        var start = T._chunks[0].seq;
        for (var i = 0; i < T._chunks.length; i++) {
            if (T._chunks[i].t >= target) { start = T._chunks[i].seq; break; }
        }
        T._cursor = start;
        T._nextStart = 0;
        T._replaying = true;
        T._schedule();
        if (!T._tickTimer) T._tickTimer = setInterval(T._schedule, 400);
    },

    live: function () {
        var T = Plugins.timeshift;
        T._replaying = false;
        if (T._tickTimer) { clearInterval(T._tickTimer); T._tickTimer = null; }
        T._stopSources();
        T._status('Live');
    },

    _stopSources: function () {
        var T = Plugins.timeshift;
        T._sources.forEach(function (s) {
            try { s.onended = null; s.stop(); s.disconnect(); } catch (e) {}
        });
        T._sources = [];
    },

    // Schedule recorded chunks (merged per format run) up to ~3 s ahead.
    _schedule: function () {
        var T = Plugins.timeshift;
        if (!T._replaying) return;
        var ctx = audioEngine.audioContext;
        var now = ctx.currentTime;
        if (T._nextStart < now + 0.05) T._nextStart = now + 0.05;

        var guard = 0;
        while (T._nextStart - now < 3 && guard++ < 10) {
            var run = T._takeRun(5);
            if (!run) break;

            var n = 0;
            run.chunks.forEach(function (c) { n += c.ch[0].length; });
            var buf = ctx.createBuffer(2, n, run.rate);
            var L = buf.getChannelData(0), R = buf.getChannelData(1);
            var pos = 0;
            run.chunks.forEach(function (c) {
                var a = c.ch[0], b = c.ch[1] || a;   // mono: duplicate to both
                for (var i = 0; i < a.length; i++) {
                    L[pos + i] = (a[i] + 0.5) / 32768;
                    R[pos + i] = (b[i] + 0.5) / 32768;
                }
                pos += a.length;
            });

            var src = ctx.createBufferSource();
            src.buffer = buf;
            src.connect(audioEngine.gainNode);
            src.onended = (function (s) {
                return function () {
                    var i = T._sources.indexOf(s);
                    if (i >= 0) T._sources.splice(i, 1);
                };
            })(src);
            src.start(T._nextStart);
            T._sources.push(src);
            T._nextStart += buf.duration;
        }
        // delay behind live = time between the cursor chunk and now
        var behind = performance.now() / 1000 - T._chunkTimeAt(T._cursor);
        T._status('Replaying, about ' + Math.round(behind) + ' s behind live');
    },

    _chunkTimeAt: function (seq) {
        var T = Plugins.timeshift;
        for (var i = 0; i < T._chunks.length; i++) {
            if (T._chunks[i].seq >= seq) return T._chunks[i].t;
        }
        return performance.now() / 1000;
    },

    // Collect consecutive chunks from the cursor having the same rate and
    // channel count, up to maxSeconds of audio. Advances the cursor.
    _takeRun: function (maxSeconds) {
        var T = Plugins.timeshift;
        var list = T._chunks;
        if (!list.length) return null;
        // cursor may have been evicted: jump to the oldest chunk
        if (T._cursor < list[0].seq) T._cursor = list[0].seq;
        var i = T._cursor - list[0].seq;
        if (i >= list.length) return null;

        var first = list[i];
        var run = { rate: first.rate, nch: first.ch.length, chunks: [] };
        var secs = 0;
        while (i < list.length && list[i].rate === run.rate && list[i].ch.length === run.nch &&
               secs < maxSeconds) {
            run.chunks.push(list[i]);
            secs += list[i].ch[0].length / run.rate;
            i++;
        }
        T._cursor = list[i - 1].seq + 1;
        return run;
    },

    // ---- UI ----------------------------------------------------------------

    _status: function (text) {
        var el = document.getElementById('timeshift-status');
        if (el) el.textContent = text;
    },

    _buildContent: function () {
        var btn = 'class="openwebrx-button" style="display:inline-block;margin:2px;padding:4px 8px;cursor:pointer;"';
        return [
            '<div>',
            '  <span ' + btn + ' data-ts="10">Back 10s</span>',
            '  <span ' + btn + ' data-ts="30">Back 30s</span>',
            '  <span ' + btn + ' data-ts="60">Back 1min</span>',
            '  <span ' + btn + ' data-ts="300">Back 5min</span>',
            '</div>',
            '<div><span ' + btn + ' data-ts="live">Back to live</span></div>',
            '<div id="timeshift-status" style="margin-top:6px;font-size:12px;">Live</div>',
            '<div id="timeshift-info" style="margin-top:4px;font-size:10px;color:#777;"></div>',
        ].join('');
    },

    _toggleWindow: function () {
        var T = Plugins.timeshift;
        var w = Plugins.addWindow('timeshift', 'Timeshift', T._buildContent());
        if (w && !w._tsBound) {
            w._tsBound = true;
            $(w).on('click', '[data-ts]', function () {
                var v = $(this).attr('data-ts');
                if (v === 'live') T.live(); else T.back(parseInt(v, 10));
            });
            setInterval(function () {
                var el = document.getElementById('timeshift-info');
                if (el) el.textContent = 'Buffered ' + Math.round(T._historySeconds()) + ' s, ' +
                    (T._bytes / 1e6).toFixed(1) + ' MB (cap ' + T.buffer_seconds + ' s / ' +
                    (T.max_bytes / 1e6) + ' MB)';
            }, 1000);
        }
        Plugins.toggleWindow('timeshift');
    },
};
