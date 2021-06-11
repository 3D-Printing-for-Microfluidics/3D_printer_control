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
var count = 0;

function draw_loadcell_graph() {

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
            borderwidth: 2
        },
        autosize: true,
        height: 500,
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
        let force = data.force;

        Plotly.extendTraces('loadcell-data',
        {
            y: [[force]],
            x: [[time]]
        },
        [0], 200)
        count += 1;
        if (count >=25){
            count = 0;
            var temp = new Date()
            var minuteView = {
                xaxis: {
                    linecolor: 'black',
                    linewidth: 2,
                    mirror: true,
                    type: 'date',
                }
            };
            Plotly.relayout('loadcell-data', minuteView);
        }
     
    }
}

$(document).ready(function () {
    console.log("doc ready")
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/loadcell");

    draw_loadcell_graph();

    socket.emit('graph_start')
    socket.on("graph_data", function (message) {
        update_loop(message)
    })
})