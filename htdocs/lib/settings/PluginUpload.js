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
