
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

var select_wavelength = function (wavelength) {
    $('.photodiode input[type="radio"]').prop('checked', false)
    $('.photodiode label').removeClass('active')
    $(`#${wavelength}`).prop('checked', true).closest('label').addClass('active');
}

$(document).ready(function () {

    socket.on("photodiode_return_power", function (message) {
        document.getElementById(`photodiode_power`).innerHTML = message["power"] + " mW/cm²";
        select_wavelength(message["wavelength"]);
        enable_button(`#read_photodiode_power`);
        enable_button(`#zero_photodiode`);
    });

    socket.on("photodiode_done", function () {
        enable_button(`#read_photodiode_power`);
        enable_button(`#zero_photodiode`);
    });

    $(`#read_photodiode_power`).on("click", function () {
        let wavelengthElement = document.getElementById("wavelength_350_405");
        let activeButton = $("#wavelength_350_405 .active");
        let wavelength = activeButton.text().trim().split(" ")[0]; // Split to get the wavelength value
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

