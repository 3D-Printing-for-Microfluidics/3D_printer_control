$(document).ready(function () {
    socket.on("wintech_adj_update", function (message) {
        if (!$.isEmptyObject(message)) {
            for (var adj in hardware['coord_systems']['coord_adjustments']) {
                if (hardware['coord_systems']['coord_adjustments'].hasOwnProperty(adj)) {
                    document.getElementById(adj).innerHTML = message[adj];
                }
            }
        }
    });

    // Change coordinate systems
    $("#coord_systems :input").change(function () {
        socket.emit("set_coodinate_system", $(this).parent().text().toLowerCase());
        socket.emit("set_galil_coodinate_system", $(this).parent().text().toLowerCase());
    });

    var show_wintech_adj = function (btn) {
        $("#toggle-wintech-adj").text("Hide Wintech Adjustments");
        $("#collapseWintechAdj").addClass('show');
    };

    var hide_wintech_adj = function (btn) {
        $("#toggle-wintech-adj").text("Show Wintech Adjustments");
        $("#collapseWintechAdj").removeClass('show');
    };

    $("#toggle-wintech-adj").on("click", function () {
        if ($("#collapseWintechAdj").hasClass("show")) {
            hide_wintech_adj();
        } else {
            show_wintech_adj();
        }
    });

    $(`.wintech-adj-cntrl-txt`).on('change', function () {
        var value = $(this).val();
        var adj_name = $(this).closest(".container").attr('aria-label');

        if (!isNaN(parseFloat(value)) && isFinite(value)) {
            var message = {}
            message[adj_name] = parseFloat(value);
            socket.emit("set_wintech_adjustments", message);
        }
    });
});