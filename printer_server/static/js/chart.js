function draw_temperature_graphs() {
    let s_trace = {
        x: [new Date()],
        y: [0],
        mode: 'lines',
        name: "1",
        line: {
            shape: 'spline'
        }
    };
    let d_trace = {
        x: [new Date()],
        y: [0],
        mode: 'lines',
        name: "2",
        line: {
            shape: 'spline'
        }
    };
    var traces = [s_trace, d_trace];

    var defaultPlotlyConfiguration = {
        displayModeBar: false,
        displaylogo: false,
        scrollZoom: true,
        showTips: false
    };

    var layout = {
        xaxis: {
            linecolor: 'black',
            linewidth: 2,
            mirror: true
        },
        yaxis: {
            ticksuffix: "",
            range: [0, 80],
            autorange: false,
            linecolor: 'black',
            linewidth: 2,
            mirror: true
        },
        margin: {
            l: 40,
            r: 20,
            b: 40,
            t: 20,
            pad: 0
        },
        legend: {
            x: 0,
            y: 1,
            traceorder: 'normal',
            // bgcolor: '#E2E2E2',
            // bordercolor: '#FFFFFF',
            borderwidth: 2
        },
        autosize: true,
        height: 500,
        // width: 350,
        // paper_bgcolor: "whitesmoke",
        // plot_bgcolor: "whitemsoke"
        paper_bgcolor: '#222',
        plot_bgcolor: '#222"',
        font: {
            color: '#999'
        }
    }
    Plotly.plot('light-source-temperature',
        traces,
        layout, defaultPlotlyConfiguration);
    // update_loop();

}

function update_loop(message) {
    var time = new Date();
    let led = message.x1;       // led temperature
    let board = message.x2;     // board temperature

    var olderTime = time.setMinutes(time.getMinutes() - 1);
    var futureTime = time.setMinutes(time.getMinutes() + 1);
    var minuteView = {
        xaxis: {
            linecolor: 'black',
            linewidth: 2,
            mirror: true,
            type: 'date',
            range: [olderTime, futureTime]
        }
    };

    Plotly.relayout('light-source-temperature', minuteView);
    Plotly.extendTraces('light-source-temperature',
        {
            y: [[led], [board]],
            x: [[time], [time]]
        },
        [0, 1])
    // setTimeout(update_loop, 500);
}




$(document).ready(function () {

    console.log("doc ready")
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/chart");
    // socket.emit("start_graph", {});
    draw_temperature_graphs();

    socket.emit('graph_ready')
    socket.on("graph_data", function (message) {
        update_loop(message)
        socket.emit('graph_ready')
    })



})