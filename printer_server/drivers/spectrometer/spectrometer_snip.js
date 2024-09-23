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
    let SpectrometerIntegrationElement = document.getElementById("spectrometer-integration-txt");
    let SpectrometerAveragesElement = document.getElementById("spectrometer-averages-txt");

    socket.on("spectrometer_load", function (message) {
        document.getElementById("spectrometer-integration-txt").value = message['integration'];
        document.getElementById("spectrometer-averages-txt").value = message['averages'];
    });

    socket.on("spectrometer_done", function (message) {
        document.getElementById("spectrometer-integration-txt").value = message['integration'];

        // Convert the 2D array to CSV string
        const convertArrayToCSV = (array) => {
            const rows = [];
            for (let i = 0; i < array[0].length; i++) {
                rows.push(`${array[0][i]},${array[1][i]}`);
            }
            return rows.join('\n');
        };

        // Combine header and CSV data
        const header = `HEADER INFORMATION...\nIntegration time: ${message['integration']} ms\nNumber of Averages: ${message['averages']}\n\nwavelength (nm),counts\n`;
        const csvData = convertArrayToCSV(message["spectra"]);
        const csvContent = header + csvData;

        const blob = new Blob([csvContent], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `data.csv`;

        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        enable_button();
    });

    $("#spectrometer-auto-chkbx").click(function () {
        let autoCheckboxElement = document.getElementById("spectrometer-auto-chkbx");
        let auto = Number(autoCheckboxElement.checked);
        if (auto == 1) {
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
        let autoCheckboxElement = document.getElementById("spectrometer-auto-chkbx");
        let integration = SpectrometerIntegrationElement.value;
        let averages = SpectrometerAveragesElement.value;
        let auto = Number(autoCheckboxElement.checked);

        if (!/^\d+$/.test(averages) && !averages > 0) {
            SpectrometerAveragesElement.classList.add("is-invalid")
            return
        }

        if (!/^\d+$/.test(integration) && !integration > 0) {
            if (auto == 0) {
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