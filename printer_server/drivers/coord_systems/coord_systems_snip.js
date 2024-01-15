$(document).ready(function () {
    // Change coordinate systems
    $("#coord_systems :input").change(function () {
        // socket.emit("galil_set_coodinate_system", $(this).parent().text().toLowerCase());
        socket.emit("galil_set_coodinate_system", JSON.stringify(hardware["coord_systems"][$(this).parent().text().toLowerCase()]));
    });
});