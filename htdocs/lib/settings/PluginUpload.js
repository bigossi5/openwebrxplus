$(function () {
    var $button = $('#plugin-upload-button');
    if (!$button.length) return;

    var $input = $('#plugin-upload-input');
    var $status = $('#plugin-upload-status');

    $button.click(function () {
        $input.val('');
        $input.trigger('click');
    });

    $input.on('change', function (e) {
        var file = e.target.files[0];
        if (!file) return;

        $button.prop('disabled', true);
        $status.text('Uploading...').removeClass('text-danger text-success');

        var reader = new FileReader();
        reader.readAsArrayBuffer(file);
        reader.onload = function (e) {
            $.ajax({
                url: 'plugins/upload',
                type: 'POST',
                data: e.target.result,
                processData: false,
                contentType: 'application/octet-stream',
            }).done(function (data) {
                $status.text('Installed "' + data.name + '". Reloading...').addClass('text-success');
                setTimeout(function () { location.reload(); }, 1000);
            }).fail(function (xhr) {
                var message = 'Upload failed';
                try {
                    message = JSON.parse(xhr.responseText).error || message;
                } catch (ex) {}
                $status.text(message).addClass('text-danger');
                $button.prop('disabled', false);
            });
        };
        reader.onerror = function () {
            $status.text('Could not read file').addClass('text-danger');
            $button.prop('disabled', false);
        };
    });

    var $restartButton = $('#plugin-restart-button');
    if (!$restartButton.length) return;

    var $restartStatus = $('#plugin-restart-status');

    $restartButton.click(function () {
        $('#pluginRestartModal').modal('show');
    });

    $('#plugin-restart-confirm').click(function () {
        $('#pluginRestartModal').modal('hide');
        $restartStatus.text('Restarting...').removeClass('text-danger text-success').addClass('text-warning');
        $restartButton.prop('disabled', true);
        $.ajax({
            url: $restartButton.data('restart-url'),
            type: 'POST',
        }).done(function () {
            $restartStatus.text('Restarted. Page will reload in 5s...').removeClass('text-warning').addClass('text-success');
            setTimeout(function () { location.reload(); }, 5000);
        }).fail(function (xhr) {
            $restartStatus.text('Error: ' + xhr.responseText).removeClass('text-warning').addClass('text-danger');
            $restartButton.prop('disabled', false);
        });
    });
});

$(function () {
    var $catalogButton = $('#plugin-catalog-button');
    if (!$catalogButton.length) return;

    var $section = $('#plugin-catalog-section');
    var $status = $('#plugin-catalog-status');
    var $list = $('#plugin-catalog-list');
    var loaded = false;

    var renderEntry = function (entry) {
        var $item = $('<li class="list-group-item d-flex justify-content-between align-items-center"></li>');
        $item.text(entry.name);
        if (entry.installed) {
            $item.append($('<span class="badge badge-secondary">already installed</span>'));
        } else {
            var $btn = $('<button type="button" class="btn btn-sm btn-success">Install</button>');
            $btn.on('click', function () {
                if (!confirm('Install plugin "' + entry.name + '" from the official plugin catalog?')) return;
                $btn.prop('disabled', true).text('Installing...');
                $.ajax({
                    url: 'plugins/installremote',
                    type: 'POST',
                    data: JSON.stringify({ name: entry.name }),
                    contentType: 'application/json',
                }).done(function () {
                    location.reload();
                }).fail(function (xhr) {
                    var message = 'Install failed';
                    try {
                        message = JSON.parse(xhr.responseText).error || message;
                    } catch (ex) {}
                    alert(message);
                    $btn.prop('disabled', false).text('Install');
                });
            });
            $item.append($btn);
        }
        return $item;
    };

    var loadCatalog = function () {
        $status.text('Loading...').show();
        $list.empty();
        $.get('plugins/catalog').done(function (data) {
            $status.hide();
            (data.plugins || []).forEach(function (entry) {
                $list.append(renderEntry(entry));
            });
            if (!data.plugins || !data.plugins.length) {
                $status.text('No plugins found in the catalog.').show();
            }
        }).fail(function (xhr) {
            var message = 'Could not load the plugin catalog';
            try {
                message = JSON.parse(xhr.responseText).error || message;
            } catch (ex) {}
            $status.text(message).show();
        });
    };

    $catalogButton.click(function () {
        $section.toggle();
        if ($section.is(':visible') && !loaded) {
            loaded = true;
            loadCatalog();
        }
    });
});
