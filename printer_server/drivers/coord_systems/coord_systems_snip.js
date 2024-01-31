$(document).ready(function () {
    // Change coordinate systems
    $("#coord_systems :input").change(function () {
        socket.emit("set_coodinate_system", $(this).parent().text().toLowerCase());
        socket.emit("save_coodinate_system", $(this).parent().text().toLowerCase());
    });
});