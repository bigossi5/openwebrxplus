function Scanner(bookmarkBar, msec) {
    this.modes     = ['lsb', 'usb', 'cw', 'am', 'sam', 'nfm'];
    this.bbar      = bookmarkBar;
    this.bookmarks = null;
    this.msec      = msec;
    this.current   = -1;
    this.threshold = -80;
    this.timer     = 0;
}

Scanner.prototype.update = function(data) {
    // Do not update if no timer or no bookmarks
    if (!this.timer || !this.bookmarks || !this.bookmarks.length) return;

    // Average level over time for each bookmark
    for(var j=0 ; j<this.bookmarks.length ; ++j) {
        var b = this.bookmarks[j];
        if (b.frequency > 0) {
            var l = data[Math.round(b.pos * data.length)];
            b.level += (l - b.level) / 3.0;
        }
    }
}

Scanner.prototype.scan = function() {
    // Do not scan if no timer or no bookmarks
    if (!this.timer || !this.bookmarks || !this.bookmarks.length) return;

    // Get current squelch threshold from the slider
    // (why do we need to subtract ~13dB here to make FFT match the S-meter?)
    var $slider = $('#openwebrx-panel-receiver .openwebrx-squelch-slider');
    this.threshold = $slider.val() - 13.0;

    // This is going to be our starting scan location
    var current = 0;

    // If there is currently selected bookmark...
    if (this.current>=0) {
        // Check if its current level still exceeds threshold
        var level = this.bookmarks[this.current].level;
        if (level>this.threshold) return;
        // If current bookmark no longer relevant, scan further
        current = this.current;
        this.current = -1;
    }

    // For every shown bookmark...
    for(var j=0 ; j<this.bookmarks.length ; ++j) {
        var b = this.bookmarks[current];

        //console.log("SCAN: " + b.name + " at " + b.frequency + ": " + b.level);

        // If level exceeds threshold, tune to the bookmark
        if (b.level>this.threshold && UI.tuneBookmark(b)) {
            this.current = current;
            return;
        }

        // Go to the next bookmark
        current = (current + 1) % this.bookmarks.length;
    }
};

Scanner.prototype.stop = function() {
    // If timer running...
    if (this.timer) {
        // Stop redraw timer
        clearInterval(this.timer);
        this.timer = 0;
        // Remove current bookmarks
        this.bookmarks = null;
    }

    // Done
    return !this.timer;
}

Scanner.prototype.start = function() {
    // If timer is not running...
    if (!this.timer) {
        // Nothing found yet
        this.current = -1;
        // Get all scannable bookmarks from the bookmark bar
        this.bookmarks = this.bbar.getAllBookmarks().filter(
          (b) => !!b.scannable && !!b.frequency && !!b.modulation
        );

        // If there are bookmarks to scan...
        if (this.bookmarks && this.bookmarks.length>0) {
            // Precompute FFT offsets, initialize levels
            for(var j=0 ; j<this.bookmarks.length ; ++j) {
                var f = this.bookmarks[j].frequency;
                this.bookmarks[j].level = -1000;
                this.bookmarks[j].pos = f>0? (f - center_freq) / bandwidth + 0.5 : 0;
            }

            // Start redraw timer
            var me = this;
            this.timer = setInterval(function() { me.scan(); }, this.msec);
        }
    }

    // Done
    return !!this.timer;
}

Scanner.prototype.isRunning = function() {
    // Return current state
    return !!this.timer;
};
