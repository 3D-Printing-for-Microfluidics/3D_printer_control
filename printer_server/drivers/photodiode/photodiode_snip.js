
var enable_button = function (object) {
    $(object).prop('disabled', false);
    $(object).addClass('btn-outline-info');
    $(object).removeClass('btn-outline-secondary');
}

var disable_button = function (object) {
    $(object).prop('disabled', true);
    $(object).removeClass('btn-outline-info');
    $(object).addClass('btn-outline-secondary');
}

$(document).ready(function () {

    socket.on("photodiode_return_power", function (message) {
        document.getElementById(`photodiode_power`).innerHTML = message["power"];
        enable_button(`#read_photodiode_power`);
        enable_button(`#zero_photodiode`);
    });

    socket.on("photodiode_done", function () {
        enable_button(`#read_photodiode_power`);
        enable_button(`#zero_photodiode`);
    });

    $(`#read_photodiode_power`).on("click", function () {
        var wavelengthElement = document.getElementById("wavelength_350_405");
        var activeButton = $("#wavelength_350_405 .active");
        var wavelength = activeButton.text().trim().split(" ")[0]; // Split to get the wavelength value
        socket.emit("photodiode_get_power", { "wavelength": wavelength })
        disable_button(`#read_photodiode_power`);
        disable_button(`#zero_photodiode`);
    });

    $(`#zero_photodiode`).on("click", function () {
        socket.emit("photodiode_zero")
        disable_button(`#read_photodiode_power`);
        disable_button(`#zero_photodiode`);
    });
});

