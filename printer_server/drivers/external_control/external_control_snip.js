$(document).ready(function () {
    // Read value of external control select button
    $("#external_enable :input").change(function () {
        socket.emit("external_control_set_enable", $(this).parent().text());
    });

});