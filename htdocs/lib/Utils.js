//
// Utility functions
//

function Utils() {}

Utils.fm_url = 'https://www.google.com/search?q={}+FM';
Utils.callsign_url = null;
Utils.vessel_url = null;
Utils.flight_url = null;
Utils.icao_url = null;
Utils.receiver_pos = null;

// Set receiver position
Utils.setReceiverPos = function(pos) {
    if (pos.lat && pos.lon) this.receiver_pos = pos;
};

// Get receiver position
Utils.getReceiverPos = function() {
    return this.receiver_pos;
};

// Set URL for linkifying callsigns
Utils.setCallsignUrl = function(url) {
    this.callsign_url = url;
};

// Set URL for linkifying AIS vessel IDs
Utils.setVesselUrl = function(url) {
    this.vessel_url = url;
};

// Set URL for linkifying flight and aircraft IDs
Utils.setFlightUrl = function(url) {
    this.flight_url = url;
};

// Set URL for linkifying ICAO aircraft IDs
Utils.setIcaoUrl = function(url) {
    this.icao_url = url;
};

// Escape HTML code
Utils.htmlEscape = function(input) {
    return $('<div/>').text(input).html();
};

// Print frequency (in Hz) in a nice way
Utils.printFreq = function(freq) {
    if (isNaN(parseInt(freq))) {
        return freq;
    } else if (freq >= 30000000) {
        return '' + (freq / 1000000.0) + 'MHz';
    } else if (freq >= 10000) {
        return '' + (freq / 1000.0) + 'kHz';
    } else {
        return '' + freq + 'Hz';
    }
}

// Change frequency as required by given modulation
Utils.offsetFreq = function(freq, mod) {
    switch(mod) {
        case 'cw':
            return freq - 800;
        case 'fax':
            return freq - 1900;
        case 'cwdecoder':
        case 'rtty450':
        case 'rtty170':
        case 'rtty85':
        case 'bpsk31':
        case 'bpsk63':
        case 'sitorb':
        case 'navtex':
        case 'dsc':
            return freq - 1000;
    }

    return freq;
}

// Wrap given callsign or other ID into a clickable link.
Utils.linkify = function(id, url = null, content = null, tip = null) {
    // If no specific content, use the ID itself
    if (content == null) content = id;

    // Compose tooltip
    var tipText = tip? ' title="' + tip + '"'  : '';

    // Must have valid ID and lookup URL
    if ((id == '') || (url == null) || (url == '')) {
        return tipText? '<div' + tipText + '>' + content + '</div>'  : content;
    } else {
        return '<a target="callsign_info"' + tipText + ' href="' +
            url.replaceAll('{}', id) + '">' + content + '</a>';
    }
};

// Create link to an FM station
Utils.linkifyFM = function(name) {
    return this.linkify(name, this.fm_url);
};

// Create link to a callsign, with country tooltip, etc.
Utils.linkifyCallsign = function(callsign) {
    // Strip callsign of modifiers
    var id = callsign.replace(/[-/].*$/, '');
    // Add country name as a tooltip
    return this.linkify(id, this.callsign_url, callsign, this.call2country(id));
};

// Create link to a maritime vessel, with country tooltip, etc.
Utils.linkifyVessel = function(mmsi) {
    // Add country name as a tooltip
    return this.linkify(mmsi, this.vessel_url, mmsi, this.mmsi2country(mmsi));
};

// Create link to a flight or an aircraft
Utils.linkifyFlight = function(flight, content = null) {
    return this.linkify(flight, this.flight_url, content);
};

// Create link to a MODE-S ICAO ID
Utils.linkifyIcao = function(icao, content = null) {
    return this.linkify(icao, this.icao_url, content);
};

// Create link to tune OWRX to the given frequency and modulation.
Utils.linkifyFreq = function(freq, mod) {
    return '<a target="openwebrx-rx" href="/#freq='
        + freq + ',mod=' + mod + '">' + Utils.printFreq(freq) + '</a>';
};

// Create link to a map locator
Utils.linkifyLocator = function(locator) {
    return '<a target="openwebrx-map" href="map?locator='
        + encodeURIComponent(locator) + '">' + locator + '</a>';
}

// Linkify given content so that clicking them opens the map with
// the info bubble.
Utils.linkToMap = function(id, content = null, attrs = "") {
    if (id) {
        return '<a ' + attrs + ' href="map?callsign='
            + encodeURIComponent(id) + '" target="openwebrx-map">'
            + (content != null? content  : id) + '</a>';
    } else if (content != null) {
        return '<div ' + attrs + '>' + content + '</div>';
    } else {
        return '';
    }
};

// Print time in hours, minutes, and seconds.
Utils.HHMMSS = function(t) {
    var pad = function (i) { return ('' + i).padStart(2, "0") };

    // Convert timestamps into dates
    if (!(t instanceof Date)) t = new Date(t);

    return pad(t.getUTCHours()) + ':' + pad(t.getUTCMinutes()) + ':' + pad(t.getUTCSeconds());
};

// Compute distance, in kilometers, between two latlons. Use receiver
// location if the second latlon is not provided.
Utils.distanceKm = function(p1, p2) {
    // Use receiver location if second latlon not given
    if (p2 == null) p2 = this.receiver_pos;
    // Convert from map objects to latlons
    if ("lng" in p1) p1 = { lat : p1.lat(), lon : p1.lng() };
    if ("lng" in p2) p2 = { lat : p2.lat(), lon : p2.lng() };
    // Earth radius in km
    var R = 6371.0;
    // Convert degrees to radians
    var rlat1 = p1.lat * (Math.PI/180);
    var rlat2 = p2.lat * (Math.PI/180);
    // Compute difference in radians
    var difflat = rlat2 - rlat1;
    var difflon = (p2.lon - p1.lon) * (Math.PI/180);
    // Compute distance
    d = 2 * R * Math.asin(Math.sqrt(
        Math.sin(difflat/2) * Math.sin(difflat/2) +
        Math.cos(rlat1) * Math.cos(rlat2) * Math.sin(difflon/2) * Math.sin(difflon/2)
    ));
    return Math.round(d);
};

// Truncate string to a given number of characters, adding "..." to the end.
Utils.truncate = function(str, count) {
    return str.length > count? str.slice(0, count) + '&mldr;'  : str;
};

// Convert degrees to compass direction.
Utils.degToCompass = function(deg) {
    dir = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
    return dir[Math.floor((deg/22.5) + 0.5) % 16];
};

// Convert given name to an information section title.
Utils.makeListTitle = function(name) {
    return '<div style="border-bottom:2px solid;padding-top:1em;"><b>' + name + '</b></div>';
};

// Convert given name/value to an information section item.
Utils.makeListItem = function(name, value) {
    return '<div style="display:flex;justify-content:space-between;border-bottom:1px dotted;white-space:nowrap;">'
        + '<span>' + name + '&nbsp;&nbsp;&nbsp;&nbsp;</span>'
        + '<span>' + value + '</span>'
        + '</div>';
};

// Get opacity value in the 0..1 range based on the given age.
Utils.getOpacityScale = function(age) {
    var scale = 1;
    if (age >= retention_time / 2) {
        scale = (retention_time - age) / (retention_time / 2);
    }
    return Math.max(0, Math.min(1, scale));
};

// Get country flag from a two-letter country code.
Utils.ccode2flag = function(ccode) {
    if (!ccode || (ccode.length != 2))
        return '';
    else
        return '&#' + (0x1F1E6 + ccode.charCodeAt(0) - 0x61)
            + ';&#' + (0x1F1E6 + ccode.charCodeAt(1) - 0x61)
            + ';';
};

// Get country name from a HAM callsign.
Utils.call2country = function(callsign) {
    for (var j=4 ; j>0 ; j--) {
        var pfx = callsign.substring(0, j);
        if (pfx in this.CALL2COUNTRY) return this.CALL2COUNTRY[pfx];
    }
    return '';
};

// Get country name from an AIS MID.
Utils.mmsi2country = function(mmsi) {
    var mid = mmsi.substring(0, 3);
    return mid in this.MID2COUNTRY? this.MID2COUNTRY[mid] : '';
};

// Check if a MID corresponds to a ground station.
Utils.mmsiIsGround = function(mmsi) {
    return mmsi.substring(0, 2) === '00';
};

// Convert Maidenhead locator ID to lat/lon pair.
Utils.loc2latlng = function(id) {
    return [
        (id.charCodeAt(1) - 65 - 9) * 10 + Number(id[3]) + 0.5,
        (id.charCodeAt(0) - 65 - 9) * 20 + Number(id[2]) * 2 + 1.0
    ];
};

// Save given canvas into a PNG file.
Utils.saveCanvas = function(canvas) {
    // Get canvas by its ID
    var c = document.getElementById(canvas);
    if (c == null) return;

    // Convert canvas to a data blob
    c.toBlob(function(blob) {
        // Create and click a link to the canvas data URL
        var a = document.createElement('a');
        a.href = window.URL.createObjectURL(blob);
        a.style = 'display: none';
        a.download = canvas + ".png";
        document.body.appendChild(a);
        a.click();

        // Get rid of the canvas data URL
        setTimeout(function() {
            document.body.removeChild(a);
            window.URL.revokeObjectURL(a.href);
        }, 0);
    }, 'image/png');
};

//
// Local Storage Access
//

function LS() {}

// Return true of setting exist in storage.
LS.has = function(key) {
    return localStorage && (localStorage.getItem(key)!=null);
};

// Save named UI setting to local storage.
LS.save = function(key, value) {
    if (localStorage) localStorage.setItem(key, value);
};

// Load named UI setting from local storage.
LS.loadStr = function(key) {
    return localStorage? localStorage.getItem(key) : null;
};

LS.loadInt = function(key) {
    var x = localStorage? localStorage.getItem(key) : null;
    return x!=null? parseInt(x) : 0;
}

LS.loadBool = function(key) {
    var x = localStorage? localStorage.getItem(key) : null;
    return x==='true';
}

//
// HAM callsign prefix to country name conversion
//

Utils.CALL2COUNTRY = {
  "0S"  : "Principality of Seborga",
  "1A"  : "Sovereign Military Order of Malta",
  "1B"  : "Northern Cyprus or Blenheim Reef",
  "1G"  : "Geyser Reef",
  "1L"  : "Liberland",
  "1M"  : "Minerva Reefs",
  "1S"  : "Principality of Sealand",
  "1Z"  : "Kayin State",
  "2"   : "United Kingdom",
  "3A"  : "Monaco",
  "3B"  : "Mauritius",
  "3C"  : "Equatorial Guinea",
  "3DA" : "Swaziland",
  "3DB" : "Swaziland",
  "3DC" : "Swaziland",
  "3DD" : "Swaziland",
  "3DE" : "Swaziland",
  "3DF" : "Swaziland",
  "3DG" : "Swaziland",
  "3DH" : "Swaziland",
  "3DI" : "Swaziland",
  "3DJ" : "Swaziland",
  "3DK" : "Swaziland",
  "3DL" : "Swaziland",
  "3DM" : "Swaziland",
  "3DN" : "Fiji",
  "3DO" : "Fiji",
  "3DP" : "Fiji",
  "3DQ" : "Fiji",
  "3DR" : "Fiji",
  "3DS" : "Fiji",
  "3DT" : "Fiji",
  "3DU" : "Fiji",
  "3DV" : "Fiji",
  "3DW" : "Fiji",
  "3DX" : "Fiji",
  "3DY" : "Fiji",
  "3DZ" : "Fiji",
  "3E"  : "Panama",
  "3F"  : "Panama",
  "3G"  : "Chile",
  "3H"  : "People's Republic of China",
  "3I"  : "People's Republic of China",
  "3J"  : "People's Republic of China",
  "3K"  : "People's Republic of China",
  "3L"  : "People's Republic of China",
  "3M"  : "People's Republic of China",
  "3N"  : "People's Republic of China",
  "3O"  : "People's Republic of China",
  "3P"  : "People's Republic of China",
  "3Q"  : "People's Republic of China",
  "3R"  : "People's Republic of China",
  "3S"  : "People's Republic of China",
  "3T"  : "People's Republic of China",
  "3U"  : "People's Republic of China",
  "3V"  : "Tunisia",
  "3W"  : "Vietnam",
  "3X"  : "Guinea",
  "3Y"  : "Norway",
  "3Z"  : "Poland",
  "4A"  : "Mexico",
  "4B"  : "Mexico",
  "4C"  : "Mexico",
  "4D"  : "Philippines",
  "4E"  : "Philippines",
  "4F"  : "Philippines",
  "4G"  : "Philippines",
  "4H"  : "Philippines",
  "4I"  : "Philippines",
  "4J"  : "Azerbaijan",
  "4K"  : "Azerbaijan",
  "4L"  : "Georgia",
  "4M"  : "Venezuela",
  "4O"  : "Montenegro",
  "4P"  : "Sri Lanka",
  "4Q"  : "Sri Lanka",
  "4R"  : "Sri Lanka",
  "4S"  : "Sri Lanka",
  "4T"  : "Peru",
  "4U"  : "United Nations (non-geographical)",
  "4V"  : "Haiti",
  "4W"  : "East Timor",
  "4X"  : "Israel",
  "4Y"  : "International Civil Aviation Organization (non-geographical)",
  "4Z"  : "Israel",
  "5A"  : "Libya",
  "5B"  : "Cyprus",
  "5C"  : "Morocco",
  "5D"  : "Morocco",
  "5E"  : "Morocco",
  "5F"  : "Morocco",
  "5G"  : "Morocco",
  "5H"  : "Tanzania",
  "5I"  : "Tanzania",
  "5J"  : "Colombia",
  "5K"  : "Colombia",
  "5L"  : "Liberia",
  "5M"  : "Liberia",
  "5N"  : "Nigeria",
  "5O"  : "Nigeria",
  "5P"  : "Denmark",
  "5Q"  : "Denmark",
  "5R"  : "Madagascar",
  "5S"  : "Madagascar",
  "5T"  : "Mauritania",
  "5U"  : "Niger",
  "5V"  : "Togo",
  "5W"  : "Western Samoa",
  "5X"  : "Uganda",
  "5Y"  : "Kenya",
  "5Z"  : "Kenya",
  "6A"  : "Egypt",
  "6B"  : "Egypt",
  "6C"  : "Syria",
  "6D"  : "Mexico",
  "6E"  : "Mexico",
  "6F"  : "Mexico",
  "6G"  : "Mexico",
  "6H"  : "Mexico",
  "6I"  : "Mexico",
  "6J"  : "Mexico",
  "6K"  : "South Korea",
  "6L"  : "South Korea",
  "6M"  : "South Korea",
  "6N"  : "South Korea",
  "6O"  : "Somalia",
  "6P"  : "Pakistan",
  "6Q"  : "Pakistan",
  "6R"  : "Pakistan",
  "6S"  : "Pakistan",
  "6T"  : "Sudan",
  "6U"  : "Sudan",
  "6V"  : "Senegal",
  "6W"  : "Senegal",
  "6X"  : "Madagascar",
  "6Y"  : "Jamaica",
  "6Z"  : "Liberia",
  "7A"  : "Indonesia",
  "7B"  : "Indonesia",
  "7C"  : "Indonesia",
  "7D"  : "Indonesia",
  "7E"  : "Indonesia",
  "7F"  : "Indonesia",
  "7G"  : "Indonesia",
  "7H"  : "Indonesia",
  "7I"  : "Indonesia",
  "7J"  : "Japan",
  "7K"  : "Japan",
  "7L"  : "Japan",
  "7M"  : "Japan",
  "7N"  : "Japan",
  "7O"  : "Yemen",
  "7P"  : "Lesotho",
  "7Q"  : "Malawi",
  "7R"  : "Algeria",
  "7S"  : "Sweden",
  "7T"  : "Algeria",
  "7U"  : "Algeria",
  "7V"  : "Algeria",
  "7W"  : "Algeria",
  "7X"  : "Algeria",
  "7Y"  : "Algeria",
  "7Z"  : "Saudi Arabia",
  "8A"  : "Indonesia",
  "8B"  : "Indonesia",
  "8C"  : "Indonesia",
  "8D"  : "Indonesia",
  "8E"  : "Indonesia",
  "8F"  : "Indonesia",
  "8G"  : "Indonesia",
  "8H"  : "Indonesia",
  "8I"  : "Indonesia",
  "8J"  : "Japan",
  "8K"  : "Japan",
  "8L"  : "Japan",
  "8M"  : "Japan",
  "8N"  : "Japan",
  "8O"  : "Botswana",
  "8P"  : "Barbados",
  "8Q"  : "Maldives",
  "8R"  : "Guyana",
  "8S"  : "Sweden",
  "8T"  : "India",
  "8U"  : "India",
  "8V"  : "India",
  "8W"  : "India",
  "8X"  : "India",
  "8Y"  : "India",
  "8Z"  : "Saudi Arabia",
  "9A"  : "Croatia",
  "9B"  : "Iran",
  "9C"  : "Iran",
  "9D"  : "Iran",
  "9E"  : "Ethiopia",
  "9F"  : "Ethiopia",
  "9G"  : "Ghana",
  "9H"  : "Malta",
  "9I"  : "Zambia",
  "9J"  : "Zambia",
  "9K"  : "Kuwait",
  "9L"  : "Sierra Leone",
  "9M0" : "Spratly Islands",
  "9M"  : "Malaysia",
  "9N"  : "Nepal",
  "9O"  : "Democratic Republic of the Congo",
  "9P"  : "Democratic Republic of the Congo",
  "9Q"  : "Democratic Republic of the Congo",
  "9R"  : "Democratic Republic of the Congo",
  "9S"  : "Democratic Republic of the Congo",
  "9T"  : "Democratic Republic of the Congo",
  "9U"  : "Burundi",
  "9V"  : "Singapore",
  "9W"  : "Malaysia",
  "9X"  : "Rwanda",
  "9Y"  : "Trinidad and Tobago",
  "9Z"  : "Trinidad and Tobago",
  "A2"  : "Botswana",
  "A3"  : "Tonga",
  "A4"  : "Oman",
  "A5"  : "Bhutan",
  "A6"  : "United Arab Emirates",
  "A7"  : "Qatar",
  "A8"  : "Liberia",
  "A9"  : "Bahrain",
  "AA"  : "United States",
  "AB"  : "United States",
  "AC"  : "United States",
  "AD"  : "United States",
  "AE"  : "United States",
  "AF"  : "United States",
  "AG"  : "United States",
  "AH"  : "United States",
  "AI"  : "United States",
  "AJ"  : "United States",
  "AK"  : "United States",
  "AL"  : "United States",
  "AM"  : "Spain",
  "AN"  : "Spain",
  "AO"  : "Spain",
  "AP"  : "Pakistan",
  "AQ"  : "Pakistan",
  "AR"  : "Pakistan",
  "AS"  : "Pakistan",
  "AT"  : "India",
  "AU"  : "India",
  "AV"  : "India",
  "AW"  : "India",
  "AX"  : "Australia",
  "AY"  : "Argentina",
  "AZ"  : "Argentina",
  "BM"  : "Taiwan",
  "BN"  : "Taiwan",
  "BO"  : "Taiwan",
  "BP"  : "Taiwan",
  "BQ"  : "Taiwan",
  "BU"  : "Taiwan",
  "BV9" : "Spratly Islands",
  "BV"  : "Taiwan",
  "BW"  : "Taiwan",
  "BX"  : "Taiwan",
  "B"   : "People's Republic of China",
  "C2"  : "Nauru",
  "C3"  : "Andorra",
  "C4"  : "Cyprus",
  "C5"  : "The Gambia",
  "C6"  : "Bahamas",
  "C7"  : "World Meteorological Organization (non-geographical)",
  "C8"  : "Mozambique",
  "C9"  : "Mozambique",
  "CA"  : "Chile",
  "CB"  : "Chile",
  "CC"  : "Chile",
  "CD"  : "Chile",
  "CE"  : "Chile",
  "CF"  : "Canada",
  "CG"  : "Canada",
  "CH"  : "Canada",
  "CI"  : "Canada",
  "CJ"  : "Canada",
  "CK"  : "Canada",
  "CL"  : "Cuba",
  "CM"  : "Cuba",
  "CN"  : "Morocco",
  "CO"  : "Cuba",
  "CP"  : "Bolivia",
  "CQ"  : "Portugal",
  "CR"  : "Portugal",
  "CS"  : "Portugal",
  "CT"  : "Portugal",
  "CU"  : "Portugal",
  "CV"  : "Uruguay",
  "CW"  : "Uruguay",
  "CX"  : "Uruguay",
  "CY"  : "Canada",
  "CZ"  : "Canada",
  "D0"  : "Donetsk",
  "D1"  : "Donetsk",
  "D2"  : "Angola",
  "D3"  : "Angola",
  "D4"  : "Cape Verde",
  "D5"  : "Liberia",
  "D6"  : "Comoros",
  "D7"  : "South Korea",
  "D8"  : "South Korea",
  "D9"  : "South Korea",
  "DA"  : "Germany",
  "DB"  : "Germany",
  "DC"  : "Germany",
  "DD"  : "Germany",
  "DE"  : "Germany",
  "DF"  : "Germany",
  "DG"  : "Germany",
  "DH"  : "Germany",
  "DI"  : "Germany",
  "DJ"  : "Germany",
  "DK"  : "Germany",
  "DL"  : "Germany",
  "DM"  : "Germany",
  "DN"  : "Germany",
  "DO"  : "Germany",
  "DP"  : "Germany",
  "DQ"  : "Germany",
  "DR"  : "Germany",
  "DS"  : "South Korea",
  "DT"  : "South Korea",
  "DU"  : "Philippines",
  "DV"  : "Philippines",
  "DW"  : "Philippines",
  "DX0" : "Spratly Islands",
  "DX"  : "Philippines",
  "DY"  : "Philippines",
  "DZ"  : "Philippines",
  "E2"  : "Thailand",
  "E3"  : "Eritrea",
  "E4"  : "Palestine",
  "E5"  : "Cook Islands",
  "E6"  : "Niue",
  "E7"  : "Bosnia and Herzegovina",
  "EA"  : "Spain",
  "EB"  : "Spain",
  "EC"  : "Spain",
  "ED"  : "Spain",
  "EE"  : "Spain",
  "EF"  : "Spain",
  "EG"  : "Spain",
  "EH"  : "Spain",
  "EI"  : "Ireland",
  "EJ"  : "Ireland",
  "EK"  : "Armenia",
  "EL"  : "Liberia",
  "EM"  : "Ukraine",
  "EN"  : "Ukraine",
  "EO"  : "Ukraine",
  "EP"  : "Iran",
  "EQ"  : "Iran",
  "ER"  : "Moldova",
  "ES"  : "Estonia",
  "ET"  : "Ethiopia",
  "EU"  : "Belarus",
  "EV"  : "Belarus",
  "EW"  : "Belarus",
  "EX"  : "Kyrgyzstan",
  "EY"  : "Tajikistan",
  "EZ"  : "Turkmenistan",
  "F"   : "France",
  "G"   : "United Kingdom",
  "H2"  : "Cyprus",
  "H3"  : "Panama",
  "H4"  : "Solomon Islands",
  "H5"  : "Bophuthatswana",
  "H6"  : "Nicaragua",
  "H7"  : "Nicaragua",
  "H8"  : "Panama",
  "H9"  : "Panama",
  "HA"  : "Hungary",
  "HB3Y" : "Liechtenstein",
  "HB0" : "Liechtenstein",
  "HBL" : "Liechtenstein",
  "HB"  : "Switzerland",
  "HC"  : "Ecuador",
  "HD"  : "Ecuador",
  "HE"  : "Switzerland",
  "HF"  : "Poland",
  "HG"  : "Hungary",
  "HH"  : "Haiti",
  "HI"  : "Dominican Republic",
  "HJ"  : "Colombia",
  "HK"  : "Colombia",
  "HL"  : "South Korea",
  "HM"  : "North Korea",
  "HN"  : "Iraq",
  "HO"  : "Panama",
  "HP"  : "Panama",
  "HQ"  : "Honduras",
  "HR"  : "Honduras",
  "HS"  : "Thailand",
  "HT"  : "Nicaragua",
  "HU"  : "El Salvador",
  "HV"  : "Vatican City",
  "HW"  : "France",
  "HX"  : "France",
  "HY"  : "France",
  "HZ"  : "Saudi Arabia",
  "I"   : "Italy",
  "J2"  : "Djibouti",
  "J3"  : "Grenada",
  "J4"  : "Greece",
  "J5"  : "Guinea-Bissau",
  "J6"  : "Saint Lucia",
  "J7"  : "Dominica",
  "J8"  : "Saint Vincent and the Grenadines",
  "JA"  : "Japan",
  "JB"  : "Japan",
  "JC"  : "Japan",
  "JD"  : "Japan",
  "JE"  : "Japan",
  "JF"  : "Japan",
  "JG"  : "Japan",
  "JH"  : "Japan",
  "JI"  : "Japan",
  "JJ"  : "Japan",
  "JK"  : "Japan",
  "JL"  : "Japan",
  "JM"  : "Japan",
  "JN"  : "Japan",
  "JO"  : "Japan",
  "JP"  : "Japan",
  "JQ"  : "Japan",
  "JR"  : "Japan",
  "JS"  : "Japan",
  "JT"  : "Mongolia",
  "JU"  : "Mongolia",
  "JV"  : "Mongolia",
  "JW"  : "Norway",
  "JX"  : "Norway",
  "JY"  : "Jordan",
  "JZ"  : "Indonesia",
  "K"   : "United States",
  "L2"  : "Argentina",
  "L3"  : "Argentina",
  "L4"  : "Argentina",
  "L5"  : "Argentina",
  "L6"  : "Argentina",
  "L7"  : "Argentina",
  "L8"  : "Argentina",
  "L9"  : "Argentina",
  "LA"  : "Norway",
  "LB"  : "Norway",
  "LC"  : "Norway",
  "LD"  : "Norway",
  "LE"  : "Norway",
  "LF"  : "Norway",
  "LG"  : "Norway",
  "LH"  : "Norway",
  "LI"  : "Norway",
  "LJ"  : "Norway",
  "LK"  : "Norway",
  "LL"  : "Norway",
  "LM"  : "Norway",
  "LN"  : "Norway",
  "LO"  : "Argentina",
  "LP"  : "Argentina",
  "LQ"  : "Argentina",
  "LR"  : "Argentina",
  "LS"  : "Argentina",
  "LT"  : "Argentina",
  "LU"  : "Argentina",
  "LV"  : "Argentina",
  "LW"  : "Argentina",
  "LX"  : "Luxembourg",
  "LY"  : "Lithuania",
  "LZ"  : "Bulgaria",
  "M"   : "United Kingdom",
  "N"   : "United States",
  "O1"  : "South Ossetia",
  "OA"  : "Peru",
  "OB"  : "Peru",
  "OC"  : "Peru",
  "OD"  : "Lebanon",
  "OE"  : "Austria",
  "OF"  : "Finland",
  "OG"  : "Finland",
  "OH"  : "Finland",
  "OI"  : "Finland",
  "OJ"  : "Finland",
  "OK"  : "Czech Republic",
  "OL"  : "Czech Republic",
  "OM"  : "Slovakia",
  "ON"  : "Belgium",
  "OO"  : "Belgium",
  "OP"  : "Belgium",
  "OQ"  : "Belgium",
  "OR"  : "Belgium",
  "OS"  : "Belgium",
  "OT"  : "Belgium",
  "OU"  : "Denmark",
  "OV"  : "Denmark",
  "OW"  : "Denmark",
  "OX"  : "Denmark",
  "OY"  : "Denmark",
  "OZ"  : "Denmark",
  "P2"  : "Papua New Guinea",
  "P3"  : "Cyprus",
  "P4"  : "Aruba",
  "P5"  : "North Korea",
  "P6"  : "North Korea",
  "P7"  : "North Korea",
  "P8"  : "North Korea",
  "P9"  : "North Korea",
  "PA"  : "Netherlands",
  "PB"  : "Netherlands",
  "PC"  : "Netherlands",
  "PD"  : "Netherlands",
  "PE"  : "Netherlands",
  "PF"  : "Netherlands",
  "PG"  : "Netherlands",
  "PH"  : "Netherlands",
  "PI"  : "Netherlands",
  "PJ"  : "Netherlands - former Netherlands Antilles",
  "PK"  : "Indonesia",
  "PL"  : "Indonesia",
  "PM"  : "Indonesia",
  "PN"  : "Indonesia",
  "PO"  : "Indonesia",
  "PP"  : "Brazil",
  "PQ"  : "Brazil",
  "PR"  : "Brazil",
  "PS"  : "Brazil",
  "PT"  : "Brazil",
  "PU"  : "Brazil",
  "PV"  : "Brazil",
  "PW"  : "Brazil",
  "PX"  : "Brazil",
  "PY"  : "Brazil",
  "PZ"  : "Suriname",
  "RA6" : "Chechnya",
  "R"   : "Russia",
  "S0"  : "Western Sahara",
  "S2"  : "Bangladesh",
  "S3"  : "Bangladesh",
  "S5"  : "Slovenia",
  "S6"  : "Singapore",
  "S7"  : "Seychelles",
  "S8"  : "South Africa",
  "S9"  : "São Tomé and Príncipe",
  "SA"  : "Sweden",
  "SB"  : "Sweden",
  "SC"  : "Sweden",
  "SD"  : "Sweden",
  "SE"  : "Sweden",
  "SF"  : "Sweden",
  "SG"  : "Sweden",
  "SH"  : "Sweden",
  "SI"  : "Sweden",
  "SJ"  : "Sweden",
  "SK"  : "Sweden",
  "SL"  : "Sweden",
  "SM"  : "Sweden",
  "SN"  : "Poland",
  "SO"  : "Poland",
  "SP"  : "Poland",
  "SQ"  : "Poland",
  "SR"  : "Poland",
  "SSA" : "Egypt",
  "SSB" : "Egypt",
  "SSC" : "Egypt",
  "SSD" : "Egypt",
  "SSE" : "Egypt",
  "SSF" : "Egypt",
  "SSG" : "Egypt",
  "SSH" : "Egypt",
  "SSI" : "Egypt",
  "SSJ" : "Egypt",
  "SSK" : "Egypt",
  "SSL" : "Egypt",
  "SSM" : "Egypt",
  "SS"  : "Sudan",
  "ST"  : "Sudan",
  "SU"  : "Egypt",
  "SV"  : "Greece",
  "SW"  : "Greece",
  "SX"  : "Greece",
  "SY"  : "Greece",
  "SZ"  : "Greece",
  "T0"  : "Principality of Seborga",
  "T1"  : "Transnistria",
  "T2"  : "Tuvalu",
  "T3"  : "Kiribati",
  "T4"  : "Cuba",
  "T5"  : "Somalia",
  "T6"  : "Afghanistan",
  "T7"  : "San Marino",
  "T8"  : "Palau",
  "TA"  : "Turkey",
  "TB"  : "Turkey",
  "TC"  : "Turkey",
  "TD"  : "Guatemala",
  "TE"  : "Costa Rica",
  "TF"  : "Iceland",
  "TG"  : "Guatemala",
  "TH"  : "France",
  "TI"  : "Costa Rica",
  "TJ"  : "Cameroon",
  "TK"  : "France",
  "TL"  : "Central African Republic",
  "TM"  : "France",
  "TN"  : "Congo",
  "TO"  : "France",
  "TP"  : "France",
  "TQ"  : "France",
  "TR"  : "Gabon",
  "TS"  : "Tunisia",
  "TT"  : "Chad",
  "TU"  : "Ivory Coast",
  "TV"  : "France",
  "TW"  : "France",
  "TX"  : "France",
  "TY"  : "Benin",
  "TZ"  : "Mali",
  "UA"  : "Russia",
  "UB"  : "Russia",
  "UC"  : "Russia",
  "UD"  : "Russia",
  "UE"  : "Russia",
  "UF"  : "Russia",
  "UG"  : "Russia",
  "UH"  : "Russia",
  "UI"  : "Russia",
  "UJ"  : "Uzbekistan",
  "UK"  : "Uzbekistan",
  "UL"  : "Uzbekistan",
  "UM"  : "Uzbekistan",
  "UN"  : "Kazakhstan",
  "UO"  : "Kazakhstan",
  "UP"  : "Kazakhstan",
  "UQ"  : "Kazakhstan",
  "UR"  : "Ukraine",
  "US"  : "Ukraine",
  "UT"  : "Ukraine",
  "UU"  : "Ukraine",
  "UV"  : "Ukraine",
  "UW"  : "Ukraine",
  "UX"  : "Ukraine",
  "UY"  : "Ukraine",
  "UZ"  : "Ukraine",
  "V2"  : "Antigua and Barbuda",
  "V3"  : "Belize",
  "V4"  : "Saint Kitts and Nevis",
  "V5"  : "Namibia",
  "V6"  : "Federated States of Micronesia",
  "V7"  : "Marshall Islands",
  "V8"  : "Brunei",
  "VA"  : "Canada",
  "VB"  : "Canada",
  "VC"  : "Canada",
  "VD"  : "Canada",
  "VE"  : "Canada",
  "VF"  : "Canada",
  "VG"  : "Canada",
  "VH"  : "Australia",
  "VI"  : "Australia",
  "VJ"  : "Australia",
  "VK"  : "Australia",
  "VL"  : "Australia",
  "VM"  : "Australia",
  "VN"  : "Australia",
  "VO"  : "Canada (Newfoundland)",
  "VP"  : "United Kingdom",
  "VQ"  : "United Kingdom",
  "VR"  : "Hong Kong",
  "VS"  : "United Kingdom",
  "VT"  : "India",
  "VU"  : "India",
  "VV"  : "India",
  "VW"  : "India",
  "VX"  : "Canada",
  "VY"  : "Canada",
  "VZ"  : "Australia",
  "W"   : "United States",
  "XA"  : "Mexico",
  "XB"  : "Mexico",
  "XC"  : "Mexico",
  "XD"  : "Mexico",
  "XE"  : "Mexico",
  "XF"  : "Mexico",
  "XG"  : "Mexico",
  "XH"  : "Mexico",
  "XI"  : "Mexico",
  "XJ"  : "Canada",
  "XK"  : "Canada",
  "XL"  : "Canada",
  "XM"  : "Canada",
  "XN"  : "Canada",
  "XO"  : "Canada",
  "XP"  : "Denmark",
  "XQ"  : "Chile",
  "XR"  : "Chile",
  "XS"  : "People's Republic of China",
  "XT"  : "Burkina Faso",
  "XU"  : "Cambodia",
  "XV"  : "Vietnam",
  "XW"  : "Laos",
  "XX"  : "Macao",
  "XY"  : "Burma",
  "XZ"  : "Burma",
  "Y2"  : "Germany",
  "Y3"  : "Germany",
  "Y4"  : "Germany",
  "Y5"  : "Germany",
  "Y6"  : "Germany",
  "Y7"  : "Germany",
  "Y8"  : "Germany",
  "Y9"  : "Germany",
  "YA"  : "Afghanistan",
  "YB"  : "Indonesia",
  "YC"  : "Indonesia",
  "YD"  : "Indonesia",
  "YE"  : "Indonesia",
  "YF"  : "Indonesia",
  "YG"  : "Indonesia",
  "YH"  : "Indonesia",
  "YI"  : "Iraq",
  "YJ"  : "Vanuatu",
  "YK"  : "Syria",
  "YL"  : "Latvia",
  "YM"  : "Turkey",
  "YN"  : "Nicaragua",
  "YO"  : "Romania",
  "YP"  : "Romania",
  "YQ"  : "Romania",
  "YR"  : "Romania",
  "YS"  : "El Salvador",
  "YT"  : "Serbia",
  "YU"  : "Serbia",
  "YV"  : "Venezuela",
  "YW"  : "Venezuela",
  "YX"  : "Venezuela",
  "YY"  : "Venezuela",
  "Z2"  : "Zimbabwe",
  "Z3"  : "Republic of Macedonia",
  "Z6"  : "Kosovo",
  "Z8"  : "South Sudan",
  "ZA"  : "Albania",
  "ZB"  : "United Kingdom",
  "ZC"  : "United Kingdom",
  "ZD"  : "United Kingdom",
  "ZE"  : "United Kingdom",
  "ZF"  : "United Kingdom",
  "ZG"  : "United Kingdom",
  "ZH"  : "United Kingdom",
  "ZI"  : "United Kingdom",
  "ZJ"  : "United Kingdom",
  "ZK"  : "New Zealand",
  "ZL"  : "New Zealand",
  "ZM"  : "New Zealand",
  "ZN"  : "United Kingdom",
  "ZO"  : "United Kingdom",
  "ZP"  : "Paraguay",
  "ZQ"  : "United Kingdom",
  "ZR"  : "South Africa",
  "ZS"  : "South Africa",
  "ZT"  : "South Africa",
  "ZU"  : "South Africa",
  "ZV"  : "Brazil",
  "ZW"  : "Brazil",
  "ZX"  : "Brazil",
  "ZY"  : "Brazil",
  "ZZ"  : "Brazil",
};

//
// AIS MID prefix to country name conversion
//

Utils.MID2COUNTRY = {
  "002" : "Europe Coast Station",
  "003" : "North America Coast Station",
  "004" : "Asia Coast Station",
  "005" : "Oceania Coast Station",
  "006" : "Africa Coast Station",
  "007" : "South America Coast Station",
  "501" : "Adelie Land (France)",
  "401" : "Afghanistan",
  "303" : "Alaska (USA)",
  "201" : "Albania",
  "605" : "Algeria",
  "559" : "Samoa (USA)",
  "202" : "Andorra",
  "603" : "Angola",
  "301" : "Anguilla",
  "304" : "Antigua and Barbuda",
  "305" : "Antigua and Barbuda",
  "701" : "Argentina",
  "216" : "Armenia",
  "307" : "Aruba",
  "608" : "Ascension Island",
  "503" : "Australia",
  "203" : "Austria",
  "423" : "Azerbaijan",
  "204" : "Azores (Portugal)",
  "308" : "Bahamas",
  "309" : "Bahamas",
  "311" : "Bahamas",
  "408" : "Bahrain",
  "405" : "Bangladesh",
  "314" : "Barbados",
  "206" : "Belarus",
  "205" : "Belgium",
  "312" : "Belize",
  "610" : "Benin",
  "310" : "Bermuda",
  "410" : "Bhutan",
  "720" : "Bolivia",
  "306" : "Bonaire, Sint Eustatius and Saba (Netherlands)",
  "478" : "Bosnia and Herzegovina",
  "611" : "Botswana",
  "710" : "Brazil",
  "378" : "Virgin Islands (UK)",
  "508" : "Brunei",
  "207" : "Bulgaria",
  "633" : "Burkina Faso",
  "609" : "Burundi",
  "514" : "Cambodia",
  "515" : "Cambodia",
  "613" : "Cameroon",
  "316" : "Canada",
  "617" : "Cape Verde",
  "319" : "Cayman Islands",
  "612" : "Central African Republic",
  "670" : "Chad",
  "725" : "Chile",
  "412" : "China",
  "413" : "China",
  "414" : "China",
  "516" : "Christmas Island",
  "523" : "Cocos (Keeling) Islands",
  "730" : "Colombia",
  "616" : "Comoros",
  "620" : "Comoros",
  "615" : "Congo",
  "518" : "Cook Islands",
  "321" : "Costa Rica",
  "619" : "Côte d'Ivoire",
  "238" : "Croatia",
  "618" : "Crozet Archipelago",
  "323" : "Cuba",
  "306" : "Curaçao (Netherlands)",
  "209" : "Cyprus",
  "210" : "Cyprus",
  "212" : "Cyprus",
  "270" : "Czech Republic",
  "445" : "North Korea",
  "676" : "Congo",
  "219" : "Denmark",
  "220" : "Denmark",
  "621" : "Djibouti",
  "325" : "Dominica",
  "327" : "Dominican Republic",
  "735" : "Ecuador",
  "622" : "Egypt",
  "359" : "El Salvador",
  "631" : "Equatorial Guinea",
  "625" : "Eritrea",
  "276" : "Estonia",
  "624" : "Ethiopia",
  "740" : "Falkland Islands (Malvinas)",
  "231" : "Faroe Islands",
  "520" : "Fiji",
  "230" : "Finland",
  "226" : "France",
  "227" : "France",
  "228" : "France",
  "546" : "French Polynesia",
  "626" : "Gabon",
  "629" : "Gambia",
  "213" : "Georgia",
  "211" : "Germany",
  "218" : "Germany (former DDR)",
  "627" : "Ghana",
  "236" : "Gibraltar",
  "237" : "Greece",
  "239" : "Greece",
  "240" : "Greece",
  "241" : "Greece",
  "331" : "Greenland",
  "330" : "Grenada",
  "329" : "Guadeloupe (France)",
  "332" : "Guatemala",
  "745" : "Guiana (France)",
  "632" : "Guinea",
  "630" : "Guinea-Bissau",
  "750" : "Guyana",
  "336" : "Haiti",
  "334" : "Honduras",
  "477" : "Hong Kong",
  "243" : "Hungary",
  "251" : "Iceland",
  "419" : "India",
  "525" : "Indonesia",
  "422" : "Iran",
  "425" : "Iraq",
  "250" : "Ireland",
  "428" : "Israel",
  "247" : "Italy",
  "339" : "Jamaica",
  "431" : "Japan",
  "432" : "Japan",
  "438" : "Jordan",
  "436" : "Kazakhstan",
  "634" : "Kenya",
  "635" : "Kerguelen Islands",
  "529" : "Kiribati",
  "440" : "Korea",
  "441" : "Korea",
  "447" : "Kuwait",
  "451" : "Kyrgyzstan",
  "531" : "Laos",
  "275" : "Latvia",
  "450" : "Lebanon",
  "644" : "Lesotho",
  "636" : "Liberia",
  "637" : "Liberia",
  "642" : "Libya",
  "252" : "Liechtenstein",
  "277" : "Lithuania",
  "253" : "Luxembourg",
  "453" : "Macao",
  "274" : "Macedonia",
  "647" : "Madagascar",
  "255" : "Madeira (Portugal)",
  "655" : "Malawi",
  "533" : "Malaysia",
  "455" : "Maldives",
  "649" : "Mali",
  "215" : "Malta",
  "229" : "Malta",
  "248" : "Malta",
  "249" : "Malta",
  "256" : "Malta",
  "538" : "Marshall Islands",
  "347" : "Martinique (France)",
  "654" : "Mauritania",
  "645" : "Mauritius",
  "345" : "Mexico",
  "510" : "Micronesia",
  "214" : "Moldova",
  "254" : "Monaco",
  "457" : "Mongolia",
  "262" : "Montenegro",
  "348" : "Montserrat",
  "242" : "Morocco",
  "650" : "Mozambique",
  "506" : "Myanmar",
  "659" : "Namibia",
  "544" : "Nauru",
  "459" : "Nepal",
  "244" : "Netherlands",
  "245" : "Netherlands",
  "246" : "Netherlands",
  "540" : "New Caledonia",
  "512" : "New Zealand",
  "350" : "Nicaragua",
  "656" : "Niger",
  "657" : "Nigeria",
  "542" : "Niue",
  "536" : "Northern Mariana Islands (USA)",
  "257" : "Norway",
  "258" : "Norway",
  "259" : "Norway",
  "461" : "Oman",
  "463" : "Pakistan",
  "511" : "Palau",
  "443" : "Palestine",
  "351" : "Panama",
  "352" : "Panama",
  "353" : "Panama",
  "354" : "Panama",
  "355" : "Panama",
  "356" : "Panama",
  "357" : "Panama",
  "370" : "Panama",
  "371" : "Panama",
  "372" : "Panama",
  "373" : "Panama",
  "374" : "Panama",
  "553" : "Papua New Guinea",
  "755" : "Paraguay",
  "760" : "Peru",
  "548" : "Philippines",
  "555" : "Pitcairn Islands",
  "261" : "Poland",
  "263" : "Portugal",
  "358" : "Puerto Rico (USA)",
  "466" : "Qatar",
  "660" : "Réunion (France)",
  "264" : "Romania",
  "273" : "Russia",
  "661" : "Rwanda",
  "665" : "Saint Helena",
  "341" : "Saint Kitts and Nevis",
  "343" : "Saint Lucia",
  "607" : "Saint Paul and Amsterdam Islands",
  "361" : "Saint Pierre and Miquelon",
  "375" : "Saint Vincent and the Grenadines",
  "376" : "Saint Vincent and the Grenadines",
  "377" : "Saint Vincent and the Grenadines",
  "561" : "Samoa",
  "268" : "San Marino",
  "668" : "São Tomé and Príncipe",
  "403" : "Saudi Arabia",
  "663" : "Senegal",
  "279" : "Serbia",
  "664" : "Seychelles",
  "667" : "Sierra Leone",
  "563" : "Singapore",
  "564" : "Singapore",
  "565" : "Singapore",
  "566" : "Singapore",
  "306" : "Sint Maarten (Netherlands)",
  "267" : "Slovakia",
  "278" : "Slovenia",
  "557" : "Solomon Islands",
  "666" : "Somalia",
  "601" : "South Africa",
  "224" : "Spain",
  "225" : "Spain",
  "417" : "Sri Lanka",
  "638" : "South Sudan",
  "662" : "Sudan",
  "765" : "Suriname",
  "669" : "Swaziland",
  "265" : "Sweden",
  "266" : "Sweden",
  "269" : "Switzerland",
  "468" : "Syria",
  "416" : "Taiwan",
  "472" : "Tajikistan",
  "674" : "Tanzania",
  "677" : "Tanzania",
  "567" : "Thailand",
  "671" : "Togo",
  "570" : "Tonga",
  "362" : "Trinidad and Tobago",
  "672" : "Tunisia",
  "271" : "Turkey",
  "434" : "Turkmenistan",
  "364" : "Turks and Caicos Islands",
  "572" : "Tuvalu",
  "675" : "Uganda",
  "272" : "Ukraine",
  "470" : "United Arab Emirates",
  "471" : "United Arab Emirates",
  "232" : "United Kingdom",
  "233" : "United Kingdom",
  "234" : "United Kingdom",
  "235" : "United Kingdom",
  "379" : "Virgin Islands (USA)",
  "338" : "United States",
  "366" : "United States",
  "367" : "United States",
  "368" : "United States",
  "369" : "United States",
  "770" : "Uruguay",
  "437" : "Uzbekistan",
  "576" : "Vanuatu",
  "577" : "Vanuatu",
  "208" : "Vatican",
  "775" : "Venezuela",
  "574" : "Vietnam",
  "578" : "Wallis and Futuna Islands",
  "473" : "Yemen",
  "475" : "Yemen",
  "678" : "Zambia",
  "679" : "Zimbabwe"
};
