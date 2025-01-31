$(document).ready(function () {
    socket.on("get_coodinate_system", function (message) {
        message = message.replace(/ /g, '-');
        $('.coord input[type="radio"]').prop('checked', false)
        $('.coord label').removeClass('active')
        $(`#${message}`).prop('checked', true).closest('label').addClass('active');
    });

    // Change coordinate systems
    $("#coord_systems :input").change(function () {
        socket.emit("coodinate_system_set_system", $(this).parent().text().toLowerCase());
        socket.emit("bp_set_coodinate_system", $(this).parent().text().toLowerCase());
        socket.emit("focus_set_coodinate_system", $(this).parent().text().toLowerCase());
        socket.emit("xy_set_coodinate_system", $(this).parent().text().toLowerCase());
    });
});