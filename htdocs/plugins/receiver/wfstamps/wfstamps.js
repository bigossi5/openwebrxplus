/**
 * wfstamps — OpenWebRX+ plugin
 * Burns a small UTC time label into the waterfall every N seconds.
 *
 * The labels are drawn into the waterfall canvas pixels, so they scroll with
 * the image. Zooming or resizing only rescales the picture: labels become
 * stretched/stale with it (they are not re-rendered), and they disappear when
 * the waterfall is cleared (e.g. profile change). The label time is the
 * arrival time of the row in the browser, not the sample time.
 *
 * The label is painted over the newest ~9 rows of the current waterfall
 * canvas, so it hides those rows' data. If a canvas is nearly full the label
 * waits for the next canvas. Rows/second is not needed: labels are driven by
 * wall-clock time, checked on every waterfall_add call.
 *
 * Configuration (optional, set before load):
 *   Plugins.wfstamps.interval = 30;   // seconds between labels
 */

Plugins.wfstamps = {
    _version: 1,
    no_css: true,

    interval: 30,
    enabled: false,

    _pending: false,
    _lastStamp: 0,
    _button: null,

    init: function () {
        var W = Plugins.wfstamps;
        W._button = Plugins.addButton('wfstamps', '🕒 WF stamps: off', W._toggle);
        if (typeof waterfall_add !== 'function') {
            console.error('wfstamps: waterfall_add not found');
            return false;
        }
        var orig = waterfall_add;
        window.waterfall_add = function (data) {
            var res = orig.apply(this, arguments);
            try { Plugins.wfstamps._afterRow(); } catch (e) { console.error('wfstamps', e); }
            return res;
        };
        return true;
    },

    _toggle: function () {
        var W = Plugins.wfstamps;
        W.enabled = !W.enabled;
        W._lastStamp = 0;
        W._pending = false;
        if (W._button) W._button.textContent = '🕒 WF stamps: ' + (W.enabled ? 'on' : 'off');
    },

    _label: function (d) {
        var p = function (n) { return (n < 10 ? '0' : '') + n; };
        return p(d.getUTCHours()) + ':' + p(d.getUTCMinutes()) + ':' + p(d.getUTCSeconds()) + 'Z';
    },

    _afterRow: function () {
        var W = Plugins.wfstamps;
        if (!W.enabled) return;
        if (typeof canvas_context === 'undefined' || !canvas_context) return;

        var nowMs = Date.now();
        if (!W._lastStamp) W._lastStamp = nowMs;
        if (nowMs - W._lastStamp >= W.interval * 1000) W._pending = true;
        if (!W._pending) return;

        // Newest row of the current canvas is at y = canvas_actual_line; older
        // rows are below it. The label covers rows y .. y+H-1.
        var H = 9;
        var y = canvas_actual_line;
        if (y + H > canvas_default_height) return;

        var ctx = canvas_context;
        var text = W._label(new Date(nowMs));
        ctx.save();
        ctx.font = '8px monospace';
        ctx.textBaseline = 'top';
        var w = Math.ceil(ctx.measureText(text).width) + 4;
        ctx.fillStyle = 'rgba(0,0,0,0.6)';
        ctx.fillRect(0, y, w, H);
        ctx.fillStyle = '#fff';
        ctx.fillText(text, 2, y);
        // line marking the exact row
        ctx.fillStyle = 'rgba(255,255,255,0.8)';
        ctx.fillRect(0, y, ctx.canvas.width, 1);
        ctx.restore();

        W._pending = false;
        W._lastStamp = nowMs;
    },
};
