/**
 * band_alert — OpenWebRX+ plugin
 * Monitoruje aktywność sygnału na konfigurowalnych pasmach
 * i wyświetla powiadomienia w przeglądarce.
 */

Plugins.band_alert = {
    _version: 2,
    no_css: true,

    _rules: [],
    _checkInterval: null,
    _storageKey: 'owrx_band_alert_rules',

    init: function () {
        Plugins.band_alert._injectCSS();
        Plugins.band_alert._loadRules();
        Plugins.band_alert._injectToasts();
        Plugins.band_alert._startMonitor();
        Plugin.addButton('band_alert', '🔔 Alerts', Plugins.band_alert._toggleWindow);
        return true;
    },

    _toggleWindow: function () {
        Plugin.addWindow('band_alert', 'Band Activity Alerts', Plugins.band_alert._buildContent());
        Plugin.toggleWindow('band_alert');
        Plugins.band_alert._renderRules();
        Plugins.band_alert._updateNotifStatus();
    },

    _injectCSS: function () {
        var css = [
            '#band-alert-rules { width: 100%; border-collapse: collapse; margin-bottom: 8px; }',
            '#band-alert-rules th { color: #aaa; font-weight: normal; font-size: 11px;',
            '  text-align: left; padding: 2px 4px; }',
            '#band-alert-rules td { padding: 2px 4px; vertical-align: middle; }',
            '#band-alert-rules tr:hover td { background: rgba(255,255,255,0.05); }',
            '.ba-del { cursor: pointer; color: #e74c3c; font-weight: bold; padding: 0 4px; }',
            '.ba-del:hover { color: #ff6b6b; }',
            '#band-alert-add { background: rgba(0,0,0,0.2); border: 1px solid #555;',
            '  border-radius: 3px; padding: 6px 4px; width: 100%; margin-top: 4px; }',
            '#band-alert-add input {',
            '  background: #1a1a1a; border: 1px solid #555; color: #ddd;',
            '  border-radius: 2px; padding: 2px 4px; font-size: 11px; }',
            '#band-alert-add input[type=text] { width: 70px; }',
            '#band-alert-add input[type=number] { width: 60px; }',
            '.ba-btn { display: inline-block; cursor: pointer;',
            '  background: #3498db; color: #fff; border: none; border-radius: 3px;',
            '  padding: 3px 8px; font-size: 11px; margin-left: 4px; }',
            '.ba-btn:hover { background: #2980b9; }',
            '#band-alert-toasts { position: fixed; bottom: 20px; right: 20px;',
            '  z-index: 10000; display: flex; flex-direction: column; gap: 8px; }',
            '.ba-toast { background: #2c3e50; color: #fff;',
            '  border-left: 4px solid #e74c3c; border-radius: 4px;',
            '  padding: 10px 14px; font-size: 13px; min-width: 260px;',
            '  box-shadow: 0 3px 10px rgba(0,0,0,0.5); cursor: pointer;',
            '  animation: ba-slide-in 0.3s ease; }',
            '.ba-toast .ba-toast-title { font-weight: bold; margin-bottom: 2px; color: #e74c3c; }',
            '.ba-toast .ba-toast-body { font-size: 11px; color: #aaa; }',
            '@keyframes ba-slide-in {',
            '  from { opacity:0; transform:translateX(40px); }',
            '  to   { opacity:1; transform:translateX(0); } }',
        ].join('\n');
        var style = document.createElement('style');
        style.textContent = css;
        document.head.appendChild(style);
    },

    _injectToasts: function () {
        var toasts = document.createElement('div');
        toasts.id = 'band-alert-toasts';
        document.body.appendChild(toasts);
    },

    _buildContent: function () {
        return [
            '<table id="band-alert-rules">',
            '  <thead><tr>',
            '    <th>Name</th><th>From MHz</th><th>To MHz</th>',
            '    <th>Thr dB</th><th>Cool s</th><th></th>',
            '  </tr></thead>',
            '  <tbody id="ba-rules-body"></tbody>',
            '</table>',
            '<div id="band-alert-add">',
            '  <b>Add rule:</b><br><br>',
            '  Name: <input type="text" id="ba-new-name" placeholder="e.g. 2m" />',
            '  From: <input type="number" id="ba-new-low" step="0.001" placeholder="144.0" />',
            '  To: <input type="number" id="ba-new-high" step="0.001" placeholder="146.0" /><br><br>',
            '  Threshold dB: <input type="number" id="ba-new-thr" value="-90" />',
            '  Cooldown s: <input type="number" id="ba-new-cool" value="30" min="5" />',
            '  <span class="ba-btn" onclick="Plugins.band_alert._addRule()">Add</span>',
            '</div>',
            '<div style="margin-top:8px;display:flex;gap:6px;align-items:center;">',
            '  <span style="color:#aaa;font-size:11px;">Browser notifications:</span>',
            '  <span class="ba-btn" onclick="Plugins.band_alert._requestNotifPerm()">Enable</span>',
            '  <span id="ba-notif-status" style="font-size:11px;color:#aaa;"></span>',
            '</div>',
        ].join('');
    },

    _loadRules: function () {
        try {
            var raw = localStorage.getItem(Plugins.band_alert._storageKey);
            Plugins.band_alert._rules = raw ? JSON.parse(raw) : [];
            Plugins.band_alert._rules.forEach(function (r) { r._lastAlert = 0; });
        } catch (e) {
            Plugins.band_alert._rules = [];
        }
    },

    _saveRules: function () {
        var toSave = Plugins.band_alert._rules.map(function (r) {
            return { name: r.name, freqLow: r.freqLow, freqHigh: r.freqHigh,
                     threshold: r.threshold, cooldown: r.cooldown };
        });
        localStorage.setItem(Plugins.band_alert._storageKey, JSON.stringify(toSave));
    },

    _addRule: function () {
        var name = document.getElementById('ba-new-name').value.trim();
        var low  = parseFloat(document.getElementById('ba-new-low').value);
        var high = parseFloat(document.getElementById('ba-new-high').value);
        var thr  = parseFloat(document.getElementById('ba-new-thr').value);
        var cool = parseInt(document.getElementById('ba-new-cool').value, 10);
        if (!name || isNaN(low) || isNaN(high) || isNaN(thr) || isNaN(cool)) {
            alert('Please fill in all fields correctly.'); return;
        }
        if (low >= high) { alert('From must be less than To.'); return; }
        Plugins.band_alert._rules.push({
            name: name, freqLow: low * 1e6, freqHigh: high * 1e6,
            threshold: thr, cooldown: cool, _lastAlert: 0
        });
        Plugins.band_alert._saveRules();
        Plugins.band_alert._renderRules();
        ['ba-new-name','ba-new-low','ba-new-high'].forEach(function(id) {
            document.getElementById(id).value = '';
        });
    },

    _deleteRule: function (idx) {
        Plugins.band_alert._rules.splice(idx, 1);
        Plugins.band_alert._saveRules();
        Plugins.band_alert._renderRules();
    },

    _renderRules: function () {
        var tbody = document.getElementById('ba-rules-body');
        if (!tbody) return;
        var rules = Plugins.band_alert._rules;
        if (rules.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="color:#666;text-align:center;padding:6px">No rules defined.</td></tr>';
            return;
        }
        tbody.innerHTML = rules.map(function (r, i) {
            return '<tr>' +
                '<td>' + r.name + '</td>' +
                '<td>' + (r.freqLow/1e6).toFixed(3) + '</td>' +
                '<td>' + (r.freqHigh/1e6).toFixed(3) + '</td>' +
                '<td>' + r.threshold + '</td>' +
                '<td>' + r.cooldown + '</td>' +
                '<td><span class="ba-del" onclick="Plugins.band_alert._deleteRule(' + i + ')">&#x2715;</span></td>' +
            '</tr>';
        }).join('');
    },

    _startMonitor: function () {
        Plugins.band_alert._checkInterval = setInterval(function () {
            Plugins.band_alert._check();
        }, 2000);
    },

    _check: function () {
        if (typeof wf_data === 'undefined' || wf_data === null) return;
        if (typeof bandwidth === 'undefined' || !bandwidth) return;
        if (typeof center_freq === 'undefined' || !center_freq) return;
        var now = Date.now() / 1000;
        var rules = Plugins.band_alert._rules;
        for (var i = 0; i < rules.length; i++) {
            var r = rules[i];
            if (now - r._lastAlert < r.cooldown) continue;
            var freqStart = center_freq - bandwidth / 2;
            var freqEnd   = center_freq + bandwidth / 2;
            if (r.freqHigh < freqStart || r.freqLow > freqEnd) continue;
            var idxLow  = Math.max(0, Math.round((r.freqLow  - freqStart) / bandwidth * wf_data.length));
            var idxHigh = Math.min(wf_data.length - 1, Math.round((r.freqHigh - freqStart) / bandwidth * wf_data.length));
            if (idxLow >= idxHigh) continue;
            var maxLevel = -999;
            for (var j = idxLow; j <= idxHigh; j++) {
                if (wf_data[j] > maxLevel) maxLevel = wf_data[j];
            }
            if (maxLevel >= r.threshold) {
                r._lastAlert = now;
                Plugins.band_alert._alert(r, maxLevel);
            }
        }
    },

    _alert: function (rule, level) {
        var range = (rule.freqLow/1e6).toFixed(3) + ' – ' + (rule.freqHigh/1e6).toFixed(3) + ' MHz';
        var msg   = 'Level: ' + level.toFixed(1) + ' dB';
        Plugins.band_alert._showToast(rule.name, msg, range);
        if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
            new Notification('🔔 ' + rule.name + ' – Band Activity', {
                body: range + '\n' + msg,
                icon: 'static/favicon.ico',
                tag:  'band_alert_' + rule.name,
            });
        }
        Plugins.band_alert._beep();
    },

    _showToast: function (title, msg, sub) {
        var container = document.getElementById('band-alert-toasts');
        if (!container) return;
        var toast = document.createElement('div');
        toast.className = 'ba-toast';
        toast.innerHTML = '<div class="ba-toast-title">🔔 ' + title + '</div>' +
                          '<div class="ba-toast-body">' + msg + '<br>' + sub + '</div>';
        toast.onclick = function () { toast.remove(); };
        container.appendChild(toast);
        setTimeout(function () { if (toast.parentNode) toast.remove(); }, 8000);
    },

    _beep: function () {
        try {
            var ctx = new (window.AudioContext || window.webkitAudioContext)();
            var osc = ctx.createOscillator();
            var gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 880;
            gain.gain.setValueAtTime(0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.3);
        } catch (e) {}
    },

    _requestNotifPerm: function () {
        if (typeof Notification === 'undefined') {
            document.getElementById('ba-notif-status').textContent = 'Not supported';
            return;
        }
        Notification.requestPermission().then(function () {
            Plugins.band_alert._updateNotifStatus();
        });
    },

    _updateNotifStatus: function () {
        var el = document.getElementById('ba-notif-status');
        if (!el) return;
        if (typeof Notification === 'undefined') {
            el.textContent = 'not supported';
        } else if (Notification.permission === 'granted') {
            el.textContent = '✔ enabled'; el.style.color = '#2ecc71';
        } else if (Notification.permission === 'denied') {
            el.textContent = '✘ blocked'; el.style.color = '#e74c3c';
        } else {
            el.textContent = 'not yet granted';
        }
    },
};
