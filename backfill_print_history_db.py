"""Create a new database and backfill design metadata for Print History."""
import argparse
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, BadZipFile

from flask import Flask

from printer_server.extensions import db
from printer_server.models import PrintRecord
from printer_server.settings import Config


log = logging.getLogger("print_history_backfill")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def parse_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def build_zip_filename(upload_time_value):
    upload_time = parse_datetime(upload_time_value)
    if upload_time is None:
        return None
    return f"{upload_time.strftime('job-%Y-%m-%d_%H-%M-%S.%f')}.zip"


def extract_design_metadata(zip_path):
    try:
        with ZipFile(zip_path, "r") as zip_file_handle, TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            namelist = zip_file_handle.namelist()
            for name in list(namelist):
                if (".csv" in name) or (".log" in name) or ("exposure_data" in name):
                    namelist.remove(name)
            zip_file_handle.extractall(temp_dir, members=namelist)
            json_files = list(temp_dir.glob("*.json"))
            with open(json_files[0], "r") as file_handle:
                print_settings = json.load(file_handle)

    except (BadZipFile, FileNotFoundError, ValueError, OSError) as ex:
        log.info("Skipping metadata for %s: %s", zip_path, ex)
        return {}

    design = print_settings.get("Design") or {}
    return {
        "design_user": design.get("User"),
        "design_purpose": design.get("Purpose"),
        "design_description": design.get("Description"),
        "design_resin": design.get("Resin"),
        "design_printer": design.get("3D printer"),
        "design_slicer": design.get("Slicer"),
        "design_slice_date": design.get("Date"),
    }


def get_table_columns(conn, table_name):
    rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    return [row[1] for row in rows]


def copy_table(conn_src, conn_tgt, table_name, transform=None):
    src_cols = get_table_columns(conn_src, table_name)
    tgt_cols = get_table_columns(conn_tgt, table_name)
    common_cols = [col for col in src_cols if col in tgt_cols]

    log.info("Copying table: %s", table_name)

    if not common_cols:
        log.info("\tSkipping %s (no common columns)", table_name)
        return

    quoted_cols = ", ".join([f'"{c}"' for c in common_cols])
    rows = conn_src.execute(
        f'SELECT {quoted_cols} FROM "{table_name}"'
    ).fetchall()

    if not rows:
        return

    records = []
    for row in rows:
        record = dict(zip(common_cols, row))
        if transform:
            record.update(transform(record))
        records.append(record)

    insert_cols = [col for col in tgt_cols if any(col in record for record in records)]
    placeholders = ", ".join([":" + col for col in insert_cols])
    insert_sql = f'INSERT INTO "{table_name}" ({", ".join(insert_cols)}) VALUES ({placeholders})'

    normalized_records = []
    for record in records:
        normalized = {col: record.get(col) for col in insert_cols}
        normalized_records.append(normalized)

    conn_tgt.executemany(insert_sql, normalized_records)
    conn_tgt.commit()


def build_app(db_path):
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    return app


def backfill_print_history(source_db, target_db, print_history_dir):
    app = build_app(target_db)
    with app.app_context():
        db.create_all()

    conn_src = sqlite3.connect(source_db)
    conn_tgt = sqlite3.connect(target_db)

    tables = [
        row[0]
        for row in conn_src.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]

    for table_name in tables:
        if table_name == PrintRecord.__tablename__:
            def transform(record):
                zip_name = build_zip_filename(record.get("upload_time"))
                if not zip_name:
                    return {}
                zip_path = Path(print_history_dir) / zip_name
                return extract_design_metadata(zip_path)

            copy_table(conn_src, conn_tgt, table_name, transform=transform)
        else:
            copy_table(conn_src, conn_tgt, table_name)

    conn_src.close()
    conn_tgt.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create a new DB and backfill Print History design metadata."
    )
    parser.add_argument(
        "--source-db",
        default=Config.DB_PATH,
        help="Path to existing DB (default: current DB)",
    )
    parser.add_argument(
        "--target-db",
        default=os.path.join(Config.PROJECT_ROOT, "3d_printer_database_backfilled.db"),
        help="Path for the new DB to create",
    )
    parser.add_argument(
        "--print-history-dir",
        default=os.path.join(Config.UPLOAD_FOLDER, "print_history"),
        help="Path to print_history zip folder",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite target DB if it already exists",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    target_path = Path(args.target_db)
    if target_path.exists():
        if not args.overwrite:
            raise SystemExit(
                f"Target DB already exists: {target_path}. Use --overwrite to replace it."
            )
        target_path.unlink()

    backfill_print_history(args.source_db, args.target_db, args.print_history_dir)
    log.info("Backfill complete: %s", target_path)


if __name__ == "__main__":
    main()
