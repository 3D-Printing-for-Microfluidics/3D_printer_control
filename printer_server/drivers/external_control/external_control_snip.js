$(document).ready(function () {
    // Read value of external control select button
    $("#external_enable :input").change(function () {
        socket.emit("set_external_control_enable", $(this).parent().text());
    });

});