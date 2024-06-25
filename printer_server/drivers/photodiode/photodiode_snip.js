
var enable_button = function () {
    $(`#read_photodiode_power`).prop('disabled', false);
    $(`#read_photodiode_power`).addClass('btn-outline-info');
    $(`#read_photodiode_power`).removeClass('btn-outline-secondary');
}

var disable_button = function () {
    $(`#read_photodiode_power`).prop('disabled', true);
    $(`#read_photodiode_power`).removeClass('btn-outline-info');
    $(`#read_photodiode_power`).addClass('btn-outline-secondary');
}

$(document).ready(function () {

    socket.on("photodiode_power", function (message) {
        document.getElementById(`photodiode_power`).innerHTML = message["power"];
        enable_button();
    });

    $(`#read_photodiode_power`).on("click", function () {
        var wavelengthElement = document.getElementById("wavelength_350_405");
        var activeButton = $("#wavelength_350_405 .active");
        var wavelength = activeButton.text().trim().split(" ")[0]; // Split to get the wavelength value
        socket.emit("get_photodiode_power", { "wavelength": wavelength }) // ... figure out what element its sending 
        disable_button();
    });
});

