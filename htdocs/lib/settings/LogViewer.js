$(function () {
    var $log = $('.log-messages');
    if (!$log.length) return;

    var el = $log.get(0);

    var isAtBottom = function () {
        return el.scrollHeight - el.scrollTop - el.clientHeight < 20;
    };

    var refresh = function () {
        var stick = isAtBottom();
        $.get('logs/data').done(function (text) {
            if ($log.text() === text) return;
            $log.text(text);
            if (stick) el.scrollTop = el.scrollHeight;
        });
    };

    setInterval(refresh, 4000);
});
