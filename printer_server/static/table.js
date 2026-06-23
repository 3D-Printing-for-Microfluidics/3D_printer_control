$(document).ready(function () {});

function appendParam(params, key, value, type) {
    if (value === '' || ((type === 'boolean' || type === 'checkbox') && value === "all")) {
        return params;
    }
    params += '&' + key + '=' + encodeURIComponent(value);
    return params;
}

function loadTable(table_key){
    const current_page = $('#' + table_key).data('current_page');
    const reload_route = $('#' + table_key).data('reload_route');
    const columns = $('#' + table_key).data('columns');
    const sort_by = $('#' + table_key).data('sort_by');
    const sort_dir = $('#' + table_key).data('sort_dir');
    const has_filters = $('#' + table_key).data('has_filters');
    const subtables = $('#' + table_key).data('subtables');
    
    var reload_function = async function (new_page, sort_by, sort_dir) {
        if (new_page === '...') {
            return;
        }
        else if (new_page === 'Previous') {
            new_page = current_page - 1;
        }
        else if (new_page === 'Next') {
            new_page = current_page + 1;
        }

        var fetch_search_parameters = '?table=' + table_key;
        fetch_search_parameters += '&page=' + new_page;
        if (has_filters) {
            for (var i = 0; i < columns.length; i++) {
                var column = columns[i];
                if (column.filterable == "Yes" || column.filterable == "Hidden") {
                    if (column.type == "datetime") {
                        fetch_search_parameters = appendParam(
                            fetch_search_parameters,
                            'filter_' + column.key + '-start',
                            $('#' + table_key + '-' + column.key + '-filter-start').val(),
                            column.type
                        );

                        fetch_search_parameters = appendParam(
                            fetch_search_parameters,
                            'filter_' + column.key + '-end',
                            $('#' + table_key + '-' + column.key + '-filter-end').val(),
                            column.type
                        );
                    }
                    else {
                        fetch_search_parameters = appendParam(
                            fetch_search_parameters,
                            'filter_' + column.key,
                            $('#' + table_key + '-' + column.key + '-filter').val(),
                            column.type
                        );
                    }
                }
            }
        }
        fetch_search_parameters += '&sort_dir=' + sort_dir
        fetch_search_parameters += '&sort_by=' + sort_by

        const response = await fetch(reload_route + fetch_search_parameters);
        const html = await response.text();
        document.getElementById(table_key).outerHTML = html;
        loadTable(table_key);
    }

    ////////////// Filters //////////////
    if (has_filters) {
        for (let j = 0; j < columns.length; j++) {
            if (columns[j].filterable !== "No") {
                var id_list = [];
                id_list.push('#' + table_key + '-' + columns[j].key + '-filter');
                if (columns[j].type === "datetime") {
                    id_list.push(id_list[0] + '-start');
                    id_list.push(id_list[0] + '-end');
                }
                for (let k = 0; k < id_list.length; k++) {
                    $(id_list[k]).on('change', function () {
                        reload_function(1, "", "desc")
                    });

                    $(id_list[k]).on('blur', function () {
                        reload_function(1, "", "desc")
                    });

                    $(id_list[k]).on('keypress', function (e) {
                        if (e.which === 13) {
                            reload_function(1, "", "desc")
                        }
                    });
                }
            }
        }

        ////////////// Advanced Filters Visability //////////////
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
    }

    ////////////// Toggles Visibility //////////////
    function setTogglesVisible(show) {
        $('.' + table_key + '-toggles').toggle(show);
    }

    const savedToggles = localStorage.getItem(table_key + 'ShowToggles');
    if (savedToggles !== null) {
        setTogglesVisible(savedToggles === 'true');
    }

    $('#' + table_key + '-toggles').on('click', function () {
        const isVisible = $('.' + table_key + '-toggles').is(':visible');
        const nextState = !isVisible;
        localStorage.setItem(table_key + 'ShowToggles', nextState);
        setTogglesVisible(nextState);
    });

    ////////////// Column Visibility //////////////
    function applyColumnVisibility(table) {
        $('.' + table + '-column-toggle').each(function () {
            const columnClass = $(this).data('column');
            const isChecked = $(this).is(':checked');
            $('.' + columnClass).toggle(isChecked);
        });
    }
    applyColumnVisibility(table_key);

    const savedColumns = localStorage.getItem(table_key + 'ColumnsVisability');
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

    $('.' + table_key + '-column-toggle').on('change', function () {
        const columnState = {};
        $('.' + table_key + '-column-toggle').each(function () {
            columnState[$(this).data('column')] = $(this).is(':checked');
        });
        localStorage.setItem(table_key + 'ColumnsVisability', JSON.stringify(columnState));
        applyColumnVisibility(table_key);
    });

    ////////////// Sort //////////////
    for (let j = 0; j < columns.length; j++) {
        if (columns[j].sortable) {
            $('#' + table_key + '-' + columns[j].key + '-sort').on('click', function () {
                const new_sort_dir = sort_by != columns[j].key || sort_dir != 'desc' ? 'desc' : 'asc';
                reload_function(1, columns[j].key, new_sort_dir);
            });
        }
    }

    ////////////// Row Details //////////////
    var load_subtable = async function(subtable_route, container_id, subtable_key) {
        console.log("Loading subtable: " + subtable_key);
        console.log("Subtable route: " + subtable_route);
        console.log("Container ID: " + container_id);
        const response = await fetch(subtable_route);
        const html = await response.text();
        document.getElementById(container_id).innerHTML = html;
        loadTable(subtable_key);
    }

    var clear_subtable = function(container_id) {
        document.getElementById(container_id).innerHTML = '';
    };

    $('.table-a').on('click', function (e) {
        e.stopPropagation();
    });

    $('.' + table_key + '-row').on('click', async function () {
        const row = $(this);
        const detailsRow = row.next('.details-row');
        detailsRow.toggle();
        if (detailsRow.is(':visible')) {
            row.addClass('expanded');
        } else {
            row.removeClass('expanded');
        }

        if (subtables) {
            if (detailsRow.is(':visible')) {
                // get id of the clicked row
                console.log("Loading subtables: " + Object.keys(subtables).join(', '));
                for (const [subtable_name, subtable_route] of Object.entries(subtables)) {
                    console.log("Loading subtable: " + subtable_name + ", Route: " + subtable_route);
                    await load_subtable(subtable_route + row.data('id'), table_key + '-' + subtable_name + '-subtable-' + row.data('id') + '-container', table_key + '-' + subtable_name + '-subtable-' + row.data('id'));
                }
            }
            else{
                for (const [subtable_name, subtable_route] of Object.entries(subtables)) {
                    clear_subtable(table_key + '-' + subtable_name + '-subtable-' +   row.data('id'));
                }
            }
        }
    });

    ////////////// Page Navigation //////////////
    $('.' + table_key + '-page-link').on('click', function () {
        reload_function($(this).attr('aria-label'), sort_by, sort_dir);
    });
}