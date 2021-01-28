function draw_loadcell_graph() {
    let s_trace = {
        x: [new Date()],
        y: [0],
        mode: 'lines',
        name: "1",
        line: {
            shape: 'spline'
        }
    };
    var traces = [s_trace];

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
            range: [-50, 50],
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
    Plotly.plot('loadcell-data',
        traces,
        layout, defaultPlotlyConfiguration);

}

function update_loop(message) {
    let data = message.data;
    if (data != 0){
        let time = new Date(data.timestamp);
        let avg = data.avg;

        var olderTime = time.setSeconds(time.getSeconds() - 10);
        var futureTime = time.setSeconds(time.getSeconds() + 10);
        var minuteView = {
            xaxis: {
                linecolor: 'black',
                linewidth: 2,
                mirror: true,
                type: 'date',
                range: [olderTime, futureTime]
            }
        };
        Plotly.relayout('loadcell-data', minuteView);
        Plotly.extendTraces('loadcell-data',
        {
            y: [[avg]],
            x: [[time]]
        },
        [0])
    }
}

function update_source(message) {
    console.log("update source")
    if(message == 1){
        console.log("1")
        document.getElementById('loadcell_source').getElementById
        $("#loadcell_battery").prop("checked", true).trigger("click");
    }
    else{
        console.log("0")
        $("#loadcell_wall").prop("checked", true).trigger("click");
    }
}

$(document).ready(function () {
    console.log("doc ready")
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/loadcell");

    socket.emit("get_loadcell_source");
    
    // Read value of loadcell source select button
    $("#loadcell_source :input").change(function () {
        socket.emit("set_loadcell_source", $(this).parent().text());
    });

    socket.on("loadcell_source", function (message) {
        update_source(message);
    });

    draw_loadcell_graph();

    socket.emit('graph_start')
    socket.on("graph_data", function (message) {
        update_loop(message)
    })
})