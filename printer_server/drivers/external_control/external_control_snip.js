$(document).ready(function () {
    socket.on("external_control_return_enable", function (message) {
        if(message == true){
            $(`#external-enabled`).prop('checked', true).closest('label').addClass('active');
            $(`#external-disabled`).prop('checked', false).closest('label').removeClass('active');
        }
        else{
            $(`#external-enabled`).prop('checked', false).closest('label').removeClass('active');
            $(`#external-disabled`).prop('checked', true).closest('label').addClass('active');
        }
    });

    // Read value of external control select button
    $("#external_enable :input").change(function () {
        socket.emit("external_control_set_enable", $(this).parent().text());
    });

});