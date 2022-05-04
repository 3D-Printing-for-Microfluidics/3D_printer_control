var disable_all_buttons = function () {
    $('button').prop('disabled', true);
}

var enable_all_buttons = function () {
    $('button').prop('disabled', false);
}

$(document).ready(function () {
    socket = io.connect("http://" + document.domain + ":" + location.port + "/manual");

});
