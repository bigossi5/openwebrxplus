$(function () {
    var $log = $('.log-messages');
    if (!$log.length) return;

    var el = $log.get(0);
    var $select = $('#log-refresh-interval');
    var $status = $('#log-refresh-status');
    var storageKey = 'owrx_logs_refresh_interval';
    var timer = null;

    var isAtBottom = function () {
        return el.scrollHeight - el.scrollTop - el.clientHeight < 20;
    };

    var refresh = function () {
        var stick = isAtBottom();
        $.get('logs/data').done(function (text) {
            if ($log.text() !== text) {
                $log.text(text);
                if (stick) el.scrollTop = el.scrollHeight;
            }
            $status.text('Updated ' + new Date().toLocaleTimeString());
        }).fail(function () {
            $status.text('Refresh failed');
        });
    };

    var applyInterval = function (ms) {
        if (timer) {
            clearInterval(timer);
            timer = null;
        }
        if (ms > 0) {
            timer = setInterval(refresh, ms);
        }
    };

    var savedInterval = parseInt(localStorage.getItem(storageKey), 10);
    if (isNaN(savedInterval)) savedInterval = 5000;
    if ($select.length) {
        $select.val(String(savedInterval));
        // saved value might not match any option (e.g. after changing the
        // available choices) - fall back to the select's own default then
        savedInterval = parseInt($select.val(), 10) || 0;
    }
    applyInterval(savedInterval);

    $select.on('change', function () {
        var ms = parseInt($(this).val(), 10) || 0;
        localStorage.setItem(storageKey, ms);
        applyInterval(ms);
    });

    $('#log-refresh-now').on('click', function () {
        refresh();
    });
});
