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
            range: [-30, 30],
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
    // update_loop();

}

function update_loop(message) {
    let array = message.data;
    
    if(array.length > 0){
        element = array.pop()
        let time = new Date(element.timestamp);
        let index = element.index;
        let raw_data = element.raw_data;
        let force = element.force;
        let avg = element.avg;
        console.log(avg)

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
    
    /*let time = new Date();
    let index = 0;
    let raw_data = 0;
    let force = 0;
    let avg = 0;
    array.forEach(function (element) {
        let time = new Date(element.timestamp);
        let index = element.index;
        let raw_data = element.raw_data;
        let force = element.force;
        let avg = element.avg;
        console.log(avg)
        
        var olderTime = time.setSeconds(time.getSeconds() - 5);
        var futureTime = time.setSeconds(time.getSeconds() + 5);
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
    });*/
}




$(document).ready(function () {

    console.log("doc ready")
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/loadcell");
    // socket.emit("start_graph", {});
    draw_loadcell_graph();

    socket.emit('graph_ready')
    socket.on("graph_data", function (message) {
        update_loop(message)
        socket.emit('graph_ready')
    })



})
