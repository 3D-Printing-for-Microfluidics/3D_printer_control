import logging
from datetime import datetime, timedelta
from flask import request

from printer_server.models import User
from printer_server.extensions import  db
import printer_server.views.home as home

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def get_user_lookup():
    return (
        db.session.query(User.id, User.full_name)
        .filter(User.full_name.isnot(None), User.full_name != "")
        .order_by(User.full_name)
        .all()
    )

def get_distinct_values(column):
    return [
        row[0]
        for row in db.session.query(column)
        .filter(column.isnot(None), column != "")
        .distinct()
        .order_by(column)
        .all()
    ]

def calculate_page_range(current_page, total_pages):
    """Calculate the page range to be displayed on the navbar.

    :param current_page: current page number
    :param total_pages: total page number
    :returns: the page number range to show in the pagination navbar and
     whether or not to display the beginning and end page shortcuts
    """
    window_size = 7
    if total_pages <= window_size:
        return 1, total_pages, (False, False)
    start = current_page - window_size / 2
    end = current_page + window_size / 2
    if start <= 1:
        return 1, window_size, (False, True)
    if end >= total_pages:
        return total_pages - window_size + 1, total_pages, (True, False)
    return int(start) + 1, int(end), (True, True)

def generate_datetime_lambda(db_column):
    def date_lambda(start_date, end_date):
        filters = []
        if start_date is not None:
            try:
                filters.append(db_column >= start_date)
            except ValueError:
                home.send_bootstrap_alert("Bad start date", level="danger")
        if end_date is not None:
            try:
                filters.append(db_column <= end_date + timedelta(days=1))
            except ValueError:
                home.send_bootstrap_alert("Bad end date", level="danger")
        return filters
    return date_lambda

def generate_boolean_lambda(db_column):
    def bool_lambda(value):
        if value in {"yes", "no"}:
            return db_column.is_(value == "yes")
    return bool_lambda

def generate_string_lambda(db_column):
    def string_lambda(value):
        return db_column.ilike(f"%{value}%")
    return string_lambda

def generate_nested_lambda(columns, lambda_func):
    def nested_lambda(value):
        result = lambda_func(columns[-1])(value)
        for col in reversed(columns[:-1]):
            result = col.has(result)
        return result
    return nested_lambda

def generate_duration_value(start_time, end_time):
    return (
        end_time - start_time
        if end_time is not None
        else None
    )

def generate_duration_db_column(start_db_column, end_db_column):
    return db.func.coalesce(
        (db.func.julianday(end_db_column) - db.func.julianday(start_db_column))
        * 86400,
        0,
    )

# Column(key=, name=, value=, type=, sortable=, filterable=, options=, visible=, db_col=, db_filter=, button_style=, button_name=, button_class=, href=, href_enabled=),
class Column:
    def __init__(self, 
                 key, 
                 name, 
                 value=None,
                 type="text", # text, link, datetime, duration, boolean, button, checkbox
                 sortable=True, 
                 filterable="Hidden", 
                 options=None,
                 visible=False,
                 db_col=None,
                 db_filter=None,
                 button_style="btn-outline-info",
                 button_name=None,
                 button_class=None,
                 href=None, # works for buttons, links, and checkboxes (will find and replace <id>)
                 href_enabled=True,
                 vertical_header=False
    ):
        self.key = key
        self.name = name
        self.value = value
        self.type = type
        self.sortable = sortable
        self.filterable = filterable
        self.filter = ""
        self.filter_start = ""
        self.filter_end = ""
        self.options = options
        self.visible = visible
        self.db_col = db_col
        self.db_filter = db_filter
        self.href = href
        self.href_enabled = href_enabled
        self.vertical_header = vertical_header
        if type == "button":
            self.button_style = button_style
            self.button_name = button_name
            self.button_class = button_class
        elif type == "checkbox":
            self.button_class = button_class

    def to_dict(self):
        output_dict = {
            "key": self.key,
            "name": self.name,
            "value": self.value,
            "type": self.type,
            "sortable": self.sortable,
            "filterable": self.filterable,
            "filter": self.filter,
            "filter_start": self.filter_start,
            "filter_end": self.filter_end,
            "options": self.options,
            "visible": self.visible,
            "href": self.href,
            "href_enabled": self.href_enabled,
            "vertical_header": self.vertical_header,
        }
        if self.type == "button":
            output_dict["button_style"] = self.button_style
            output_dict["button_name"] = self.button_name
            output_dict["button_class"] = self.button_class
        elif self.type == "checkbox":
            output_dict["button_class"] = self.button_class
        return output_dict

def generate_table(name, table_key, route, query, table_definition, has_filters, subtables, paginate, args):
    # var fetch_search_parameters = '?table=' + table_key

    current_page = args.get("page", 1, type=int)
    today = datetime.now().strftime("%Y-%m-%d")
    default_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    table_columns = table_definition["columns"]
    filter_lambdas = table_definition["filter_lambdas"]
    sort_cols = table_definition["sort_columns"]

    # Filters
    if has_filters:
        for column in table_columns:
            if column.filterable in ["Yes", "Hidden"]:
                if column.type == "datetime":
                    start_date = args.get(f"filter_{column.key}-start", default_start)
                    if start_date == "":
                        start_date = default_start
                    start_date_dt = datetime(*[int(i) for i in start_date.split("-")])
                    end_date = args.get(f"filter_{column.key}-end", today)
                    if end_date == "":
                        end_date = today
                    end_date_dt = datetime(*[int(i) for i in end_date.split("-")])
                    try:
                        for filter in filter_lambdas(column.key)(start_date_dt, end_date_dt):
                            query = query.filter(filter)
                    except AttributeError as e:
                        pass
                    column.filter_start = start_date
                    column.filter_end = end_date
                else:
                    value = args.get(f"filter_{column.key}", "")
                    if value != "":
                        try:
                            query = query.filter(filter_lambdas(column.key)(value))
                        except AttributeError as e:
                            pass

                    column.filter = value

    # Sort
    # get default sort column
    def_col = sort_cols("")
    for table_column in table_columns:
        if table_column.db_col == def_col:
            def_col = table_column.key
            break

    sort_by = args.get("sort_by", def_col, type=str).strip().lower()
    if sort_by == "":
        sort_by = def_col
    sort_dir = args.get("sort_dir", "desc", type=str).strip().lower()
    if sort_dir == "":
        sort_dir = "desc"
    sort_col = sort_cols(sort_by)
    if sort_dir == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # Paginate
    page_count = query.count()
    if paginate <= page_count and paginate > 0:
        records = query.paginate(page=current_page, per_page=paginate)
        start, end, boundaries = calculate_page_range(current_page, records.pages)
    else:
        records = query.paginate(page=current_page, per_page=query.count() or 1)
        start, end, boundaries = calculate_page_range(current_page, records.pages)
        
    table = {
        "name": name,
        "key": table_key,
        "reload_route": route,
        "has_filters": has_filters,
        "subtables": subtables,
        "records": records,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "columns": [col.to_dict() for col in table_columns]
    }
    if paginate <= page_count and paginate > 0:
        table["paginate"] = paginate
        table["start"] = start
        table["current_page"] = current_page
        table["end"] = end
        table["boundaries"] = boundaries

    return table