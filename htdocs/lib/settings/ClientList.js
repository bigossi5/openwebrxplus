$.fn.clientList = function() {
    this.each(function() {
        var $container = $(this);

        var refresh = function() {
            var currentSelection = $container.find('#ban-minutes').val();
            $.get('/clients').done(function(html) {
                var $fresh = $('<div>').html(html).find('.client-list').html();
                if ($fresh === undefined) return;
                $container.html($fresh);
                if (currentSelection !== undefined) {
                    $container.find('#ban-minutes').val(currentSelection);
                }
            });
        };

        $container.on('click', '.client-ban', function(e) {
            var ip = this.value;
            if (!confirm('Ban IP ' + ip + ' for the selected duration?')) return false;
            var mins = $container.find('#ban-minutes').val();
            $.ajax("/ban", {
                data: JSON.stringify({ ip: ip, mins: mins }),
                contentType: 'application/json',
                method: 'POST'
            }).done(function() {
                refresh();
            });
            return false;
        });

        $container.on('click', '.client-unban', function(e) {
            var ip = this.value;
            if (!confirm('Unban IP ' + ip + '?')) return false;
            $.ajax("/unban", {
                data: JSON.stringify({ ip: ip }),
                contentType: 'application/json',
                method: 'POST'
            }).done(function() {
                refresh();
            });
            return false;
        });

        // keep the client list current without requiring a manual page reload
        setInterval(refresh, 20000);
    });

    $('#broadcast-send').on('click', function(e) {
        var $button = $(this);
        var $status = $('#broadcast-status');
        var text = $('#broadcast-text').val();
        if (text.length > 0) {
            $button.prop('disabled', true);
            $status.removeClass('text-danger text-success').text('Sending...');
            $.ajax("/broadcast", {
                data: JSON.stringify({ text: text }),
                contentType: 'application/json',
                method: 'POST'
            }).done(function() {
                $('#broadcast-text').val('');
                $status.addClass('text-success').text('Sent.');
                $button.prop('disabled', false);
                setTimeout(function() { $status.text(''); }, 3000);
            }).fail(function() {
                $status.addClass('text-danger').text('Failed to send broadcast.');
                $button.prop('disabled', false);
            });
        }
        return false;
    });
}
