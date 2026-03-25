$(document).ready(function () {
    var socket = io.connect("http://" + document.domain + ":" + location.port + "/print_history");

    $('.btn-sm').on('click', function (e) {
        let id = $(this).closest('tr').prop('id');
        socket.emit("add_to_queue", id);
    });

    socket.on("flash", function (message) {
        let flash_msg = `
        <div class="alert alert-${message.category} justify-center">
         <a class="close" title="Close" href="#" data-dismiss="alert">&times;</a>
         <pre>${message.text}</pre>
        </div>
        `;
        console.log(message)
        $("table").before(flash_msg);
    });

    function submitFilters() {
        const params = new URLSearchParams({
            start: $('#start-date').val(),
            end: $('#end-date').val(),
            search: $('#search-text').val(),
            design_user: $('#design-user').val(),
            design_purpose: $('#design-purpose').val(),
            design_description: $('#design-description').val(),
            design_resin: $('#design-resin').val(),
            design_printer: $('#design-printer').val(),
            design_slicer: $('#design-slicer').val(),
            design_slice_date: $('#design-slice-date').val(),
            completed: $('#completed-filter').val(),
            sort: typeof print_history_sort !== 'undefined' ? print_history_sort : 'start_time',
            dir: typeof print_history_dir !== 'undefined' ? print_history_dir : 'desc'
        });
        location.href = print_history_url + '?' + params.toString();
    }

    const filterInputs = '#search-text, #design-user, #design-purpose, #design-description, #design-resin, #design-printer, #design-slicer, #design-slice-date, #start-date, #end-date, #completed-filter';

    $(filterInputs).on('change', function () {
        submitFilters();
    });

    $(filterInputs).on('blur', function () {
        submitFilters();
    });

    $(filterInputs).on('keypress', function (e) {
        if (e.which === 13) {
            submitFilters();
        }
    });

    function setAdvancedFilters(show) {
        $('.advanced-filters').toggle(show);
    }

    const savedAdvanced = localStorage.getItem('printHistoryShowAdvanced');
    if (savedAdvanced !== null) {
        setAdvancedFilters(savedAdvanced === 'true');
    }

    $('#advanced_toggle').on('click', function () {
        const isVisible = $('.advanced-filters').is(':visible');
        const nextState = !isVisible;
        localStorage.setItem('printHistoryShowAdvanced', nextState);
        setAdvancedFilters(nextState);
    });

    function applyColumnVisibility() {
        $('.column-toggle').each(function () {
            const columnClass = $(this).data('column');
            const isChecked = $(this).is(':checked');
            $('.' + columnClass).toggle(isChecked);
        });
    }

    const savedColumns = localStorage.getItem('printHistoryColumns');
    if (savedColumns) {
        const columnState = JSON.parse(savedColumns);
        $('.column-toggle').each(function () {
            const columnClass = $(this).data('column');
            if (columnState.hasOwnProperty(columnClass)) {
                $(this).prop('checked', columnState[columnClass]);
            }
        });
    }
    applyColumnVisibility();

    $('.column-toggle').on('change', function () {
        const columnState = {};
        $('.column-toggle').each(function () {
            columnState[$(this).data('column')] = $(this).is(':checked');
        });
        localStorage.setItem('printHistoryColumns', JSON.stringify(columnState));
        applyColumnVisibility();
    });
});