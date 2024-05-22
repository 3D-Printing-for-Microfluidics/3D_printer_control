var enable_button = function () {
    $(`#download-spectra-btn`).prop('disabled', false);
    $(`#download-spectra-btn`).addClass('btn-outline-info');
    $(`#download-spectra-btn`).removeClass('btn-outline-secondary');
}

var disable_button = function () {
    $(`#download-spectra-btn`).prop('disabled', true);
    $(`#download-spectra-btn`).removeClass('btn-outline-info');
    $(`#download-spectra-btn`).addClass('btn-outline-secondary');
}

$(document).ready(function () {
    var SpectrometerIntegrationElement = document.getElementById("spectrometer-integration-txt");
    var SpectrometerAveragesElement = document.getElementById("spectrometer-averages-txt");

    socket.on("spectrometer_done", function (spectra) {
        // download spectra
        console.log(spectra);

        enable_button();
    });

    $("#spectrometer-auto-chkbx").click(function () {
        var autoCheckboxElement = document.getElementById("spectrometer-auto-chkbx");
        var auto = Number(!autoCheckboxElement.checked);
        if (auto == 0) {
            SpectrometerIntegrationElement.classList.remove("is-invalid")
            $('#spectrometer-integration-txt').prop('disabled', true);
        } else {
            $('#spectrometer-integration-txt').prop('disabled', false);
        }
    });

    $('#spectrometer-integration-txt').on('change', function () {
        integration = SpectrometerIntegrationElement.value;

        // Validate user input. Only allows positive integers > 0
        if (/^\d+$/.test(integration) && integration > 0) {
            SpectrometerIntegrationElement.classList.remove("is-invalid")
            enable_button();
        } else {
            SpectrometerIntegrationElement.classList.add("is-invalid")
            disable_button();
        }
    })

    $('#spectrometer-averages-txt').on('change', function () {
        averages = SpectrometerAveragesElement.value;

        // Validate user input. Only allows positive integers > 0
        if (/^\d+$/.test(averages) && averages > 0) {
            SpectrometerAveragesElement.classList.remove("is-invalid")
            enable_button();
        } else {
            SpectrometerAveragesElement.classList.add("is-invalid")
            disable_button();
        }
    })

    $(`#download-spectra-btn`).on("click", function (e) {
        var autoCheckboxElement = document.getElementById("spectrometer-auto-chkbx");
        var integration = SpectrometerIntegrationElement.value;
        var averages = SpectrometerAveragesElement.value;
        var auto = Number(!autoCheckboxElement.checked);

        if (!/^\d+$/.test(averages) && !averages > 0) {
            SpectrometerAveragesElement.classList.add("is-invalid")
        }

        if (!/^\d+$/.test(integration) && !integration > 0) {
            if (auto == 1) {
                SpectrometerIntegrationElement.classList.add("is-invalid")
                return
            } else {
                integration = 0
            }
        }

        socket.emit("spectrometer_capture", { "auto": auto, "integration": integration, "averages": averages });
        disable_button();
    });
});




// const data = [
//     { name: "John Doe", age: 28, email: "john@example.com" },
//     { name: "Jane Smith", age: 34, email: "jane@example.com" }
//   ];

//   function convertToCSV(data) {
//     const headers = Object.keys(data[0]);
//     const rows = data.map(row => 
//       headers.map(header => JSON.stringify(row[header] || "")).join(",")
//     );
//     return [headers.join(","), ...rows].join("\n");
//   }

//   const csvData = convertToCSV(data);
//   const blob = new Blob([csvData], { type: "text/csv" });
//   const url = URL.createObjectURL(blob);
//   const a = document.createElement("a");
//   a.href = url;
//   a.download = "data.csv";

//   document.body.appendChild(a);
//   a.click();
//   document.body.removeChild(a);
//   URL.revokeObjectURL(url);