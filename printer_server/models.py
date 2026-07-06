"""Database models"""
import os
import glob
import json
import logging
from enum import Enum
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy.ext.hybrid import hybrid_property
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from printer_server.settings import Config
from printer_server.database import (
    Column,
    Model,
    SurrogatePK,
    db,
    reference_col,
    relationship,
)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class User(SurrogatePK, Model, UserMixin):
    """A user of the app."""

    __tablename__ = "Users"
    username = Column(db.String(80), unique=True, nullable=False)
    email = Column(db.String(80), unique=True, nullable=False)
    password = Column(db.LargeBinary(256), nullable=True)  #: The hashed password
    created_at = Column(db.DateTime, nullable=False, default=datetime.now)
    first_name = Column(db.String(30), nullable=True)
    last_name = Column(db.String(30), nullable=True)
    full_name = Column(db.String(60), nullable=True)
    print_permissions = Column(db.Boolean(), default=False)
    calibration_permissions = Column(db.Boolean(), default=False)
    advanced_permissions = Column(db.Boolean(), default=False)
    admin_permissions = Column(db.Boolean(), default=False)
    token = Column(db.String(256), nullable=True)
    reset_otc = Column(db.String(256), nullable=True)
    token_expiration = Column(db.DateTime, nullable=True)

    def __init__(self, username, email, password=None, **kwargs):
        """Create instance."""
        db.Model.__init__(self, username=username, email=email, **kwargs)
        if password:
            self.set_password(password)
        else:
            self.password = None
        if self.first_name and self.last_name:
            self.full_name = self.first_name + " " + self.last_name
        elif self.first_name:
            self.full_name = self.first_name
        elif self.last_name:
            self.full_name = self.last_name
        else:
            self.full_name = None

    def set_password(self, password):
        """Set password."""
        self.password = generate_password_hash(password).encode()

    def check_password(self, value):
        """Check password."""
        return check_password_hash(self.password.decode(), value)

    def generate_token(self, need_otc=True):
        """Generate a reset token for the user."""
        import secrets
        token = secrets.token_urlsafe(16)
        self.token = token
        self.token_expiration = datetime.now() + timedelta(minutes=10)

        otc = None
        if need_otc:
            otc = secrets.token_urlsafe(6)
            otc = otc[:6]  # Ensure the one-time code is 6 characters long
        self.reset_otc = otc
        self.save()
        return token, otc

    def verify_token(self, token, otc):
        """Verify the reset token and one-time code."""
        if (
            self.token == token
            and self.reset_otc == otc
            and self.token_expiration > datetime.now()
        ):
            return True
        return False

    def clear_token(self):
        """Clear the reset token and one-time code."""
        self.token = None
        self.reset_otc = None
        self.token_expiration = None
        self.save()

    def __repr__(self):
        """Represent instance as a unique string."""
        return "<User({username!r})>".format(username=self.username)


class Session(SurrogatePK, Model):
    """A session of printing activity"""
    
    __tablename__ = "Sessions"

    active = Column(db.Boolean, default=True)
    
    # Timestamp for the session
    start_time = Column(db.DateTime, nullable=False, default=datetime.now)
    end_time = Column(db.DateTime)
    
    # User associated with the session
    user_id = Column(db.Integer, db.ForeignKey('Users.id'))
    user = relationship("User", backref="sessions")

    prints_successful = Column(db.Integer, default=0)
    
    # Whether film was changed during session
    film_changed = Column(db.Boolean, default=False)
    
    # Focus/tip/tilt positions
    calibration_data_id = Column(db.Integer, db.ForeignKey('Calibration.id'), nullable=True)
    calibration_data = relationship("Calibration", backref="sessions")
    
    # Hardware issues
    hardware_issues = Column(db.Boolean, default=False)
    hardware_issues_details = Column(db.Text, default=None)

    # General comments for the entire session
    notes = Column(db.Text, default=None)

    @classmethod
    def get_active_session(cls):
        # Get latest session; if active, return it
        latest_session = cls.query.order_by(cls.start_time.desc()).first()
        if latest_session and latest_session.active:
            return latest_session
        return None

        # """Get the active session using active (only one can be active at a time)."""
        # return cls.query.filter(cls.active == True).first()

        # """Get the active session using end_time (only one can be active at a time)."""
        # return cls.query.filter(cls.end_time.is_(None)).first()

    @classmethod
    def session_active(cls):
        """Check if the session is active."""
        return cls.get_active_session() is not None
    
    @classmethod
    def get_session_user(cls):
        """Get the active user."""
        if cls.session_active():
            return cls.get_active_session().user
        return None
    
    @hybrid_property
    def total_prints(self):
        return len(self.print_records)

    @total_prints.expression
    def total_prints_in_session(cls):
        return (
            db.select(db.func.count(PrintRecord.id))
            .where(PrintRecord.session_id == cls.id)
            .scalar_subquery()
        )


class PrintQueue(SurrogatePK, Model):
    """Print jobs in queue

    .. py:attribute:: original_filename

        str -- Because the ZIP file uploaded will be renamed
        based on the upload time, this column holds the
        original filename for it.

    .. py:attribute:: upload_time

        datetime -- the utc time when the ZIP file is uploaded

    .. py:attribute:: upload_ip

        str -- the IP address where the ZIP file is uploaded
    """

    __tablename__ = "Print Queue"
    original_filename = Column(db.String(128), index=True, nullable=False)
    upload_time = Column(db.DateTime, nullable=False)
    upload_ip = Column(db.String(30))
    user_id = Column(db.Integer, db.ForeignKey('Users.id'))
    user = relationship("User", backref="queue")

    @property
    def zip_filename(self):
        """The filename used to archive the ZIP file is based on
        its upload time.

        Example::

            upload_time -- 2018/04/30 10:00:00.123456.
            zip_filename -- job-2018-05-10T02-41-18.960939.zip
        """
        return "{}.zip".format(self.upload_time.strftime("job-%Y-%m-%d_%H-%M-%S.%f"))

    @classmethod
    def remove_orphaned_entries(cls):
        queue_path = Path(Config.UPLOAD_FOLDER) / "queue"
        entries = cls.query.order_by(cls.id).all()
        for entry in entries:
            entry_path = queue_path / entry.zip_filename
            if not entry_path.exists():
                log.info(
                    "Removing orphaned queue db entry: {}".format(entry.original_filename)
                )
                entry.delete()

    @classmethod
    def remove_orphaned_files(cls):
        queue_path = Path(Config.UPLOAD_FOLDER) / "queue"
        zips = list(queue_path.glob("*.zip"))
        for entry in cls.query.order_by(cls.id).all():
            entry_path = queue_path / entry.zip_filename
            zips.remove(entry_path)
        for entry in zips:
            try:
                log.info("Removing orphaned queue zip: {}".format(entry))
                os.remove(entry)
            except FileNotFoundError:
                log.warning("Error: Failed to remove zip")


class PrintRecord(SurrogatePK, Model):
    """Print Record

    .. py:attribute:: original_filename

        str -- Because the ZIP file uploaded will be renamed
        based on the upload time, this column holds the
        original filename for it.

    .. py:attribute:: upload_time

        datetime -- the utc time when the ZIP file is uploaded

    .. py:attribute:: upload_ip

        str -- the IP address where the ZIP file is uploaded

    .. py:attribute:: start_ip

        str -- the IP address where the print job is started

    .. py:attribute:: start_time

        datetime -- the utc time when the print job is started

    .. py:attribute:: end_time

        datetime -- the utc time when the print job is either
        completed or stopped

    .. py:attribute:: completed

        boolean -- whether the print job is completed or stopped

    """

    __tablename__ = "Print History"
    original_filename = Column(db.String(128), index=True, nullable=False)
    upload_time = Column(db.DateTime, nullable=False)
    upload_ip = Column(db.String(30))
    user_id = Column(db.Integer, db.ForeignKey('Users.id'))
    user = relationship("User", backref="print_records")
    session_id = Column(db.Integer, db.ForeignKey('Sessions.id'))
    session = relationship("Session", backref="print_records")
    start_ip = Column(db.String(30))
    start_time = Column(db.DateTime, nullable=False, default=datetime.now)
    end_time = Column(db.DateTime)
    completed = Column(db.Boolean, nullable=False, default=False)
    design_user = Column(db.String(128), index=True)
    design_purpose = Column(db.String(256))
    design_description = Column(db.Text)
    design_resin = Column(db.String(128), index=True)
    design_printer = Column(db.String(128), index=True)
    design_slicer = Column(db.String(128), index=True)
    design_slice_date = Column(db.String(64))

    # Define FailureModeEnum for print failures
    class FailureModeEnum(Enum):
        NO_FAILURE = "None"
        DELAMINATION = "Print Delamination from Glass"
        ADHESION = "Glass Detached from Build Platform"
        SPLITTING = "Mid-Print Delamination"
        PITTING = "Device Pitting/Damaged Film"
        OPTICS = "Dirty Optics"
        PRINTER_FAILURE = "Printer Hardware Issue"
        OTHER_FAILURE = "Other"
    logged = Column(db.Boolean, default=False)
    successful = Column(db.Boolean, default=None)
    failure_mode = Column(db.Enum(FailureModeEnum), default=FailureModeEnum.NO_FAILURE)
    other_failure_mode = Column(db.String(256), default=None)
    notes = Column(db.Text, default=None)

    @property
    def zip_filename(self):
        """The filename used to archive the ZIP file is based on
        its upload time.

        Example::

            upload_time -- 2018/04/30 10:00:00.123456.
            zip_filename -- job-2018-05-10T02-41-18.960939.zip
        """
        return "{}.zip".format(self.upload_time.strftime("job-%Y-%m-%d_%H-%M-%S.%f"))

    @classmethod
    def remove_orphaned_entries(cls):
        print_history_path = Path(Config.UPLOAD_FOLDER) / "print_history"
        entries = cls.query.order_by(cls.id).all()
        for entry in entries:
            entry_path = print_history_path / entry.zip_filename
            if not entry_path.exists():
                log.info(
                    "Removing orphaned print histroy db entry: {}".format(
                        entry.original_filename
                    )
                )
                entry.delete()

    @classmethod
    def remove_orphaned_files(cls):
        print_history_path = Path(Config.UPLOAD_FOLDER) / "print_history"
        zips = list(print_history_path.glob("*.zip"))
        for entry in cls.query.order_by(cls.id).all():
            entry_path = print_history_path / entry.zip_filename
            zips.remove(entry_path)
        for entry in zips:
            try:
                log.info("Removing orphaned print_history zip: {}".format(entry))
                os.remove(entry)
            except FileNotFoundError:
                log.warning("Error: Failed to remove zip")

    @classmethod
    def remove_old_jobs(cls):
        MAX_ENTRIES = 15000
        print_history_path = Path(Config.UPLOAD_FOLDER) / "print_history"
        entries_count = len(cls.query.order_by(cls.id).all())
        num_entries_to_delete = entries_count - MAX_ENTRIES
        if num_entries_to_delete <= 0:
            num_entries_to_delete = 0
        else:
            log.info(
                "Cleaning print history ({} jobs removed)".format(num_entries_to_delete)
            )

        entries_to_be_deleted = (
            cls.query.order_by(cls.id).limit(num_entries_to_delete).all()
        )

        for entry in entries_to_be_deleted:
            try:
                os.remove(os.path.join(print_history_path / entry.zip_filename))
            except FileNotFoundError:
                pass
            entry.delete()

    @classmethod
    def remove_old_logs(cls):
        MAX_ENTRIES = 14
        host = Config.HOSTNAME
        log_list = glob.glob(f"logs/{host}_log*.txt")
        log_list.sort(key=os.path.getmtime)
        entries_count = len(log_list)
        num_entries_to_delete = entries_count - MAX_ENTRIES
        if num_entries_to_delete <= 0:
            num_entries_to_delete = 0
        else:
            log.info("Removing old logs")

        for i in range(num_entries_to_delete):
            try:
                os.remove(Path(Config.PROJECT_ROOT) / log_list[i])
            except FileNotFoundError:
                pass

class Calibration(SurrogatePK, Model):
    __tablename__ = "Calibration"
    # Add your calibration fields here
    calibration_date = Column(db.DateTime, default=datetime.now)
    calibration_data = Column(db.JSON)

    @classmethod
    def init_Calibration_from_old_text_logs(cls):
        # This method should initialize the Calibration table from old text logs
        if cls.get_last_positions() is None or cls.get_last_positions() == {}:
            log.info("Initializing Calibration from old text logs")
            # Initialize from old text logs here
            """Return the last focused position from the position log file."""
            log_file = Path(Config.PROJECT_ROOT) / "logs" / "calibration_position_log.txt"
            last_line = None
            try:
                with open(log_file) as f:
                    for line in f:
                        last_line = line.rstrip()
                        log.info("Processing line: %s", last_line)
                        
                        calibration = Calibration(
                            calibration_date=datetime.strptime(last_line[:19], "%Y-%m-%d_%H-%M-%S"),
                            calibration_data=json.loads(last_line[20:].replace("'", '"'))
                        )
                        calibration.save()
                        log.info("Calibration saved: %s", calibration)

            except FileNotFoundError:
                return

    @classmethod
    def get_last_positions(cls):
        # This method should return the last calibration positions from the database
        last_calibration = cls.query.order_by(cls.calibration_date.desc()).first()
        if last_calibration:
            return last_calibration.calibration_data
        return {}


## DEPRECATED DUE TO EXCESSIVE DB SIZE ##
# class ServerLog(SurrogatePK, Model):
#     __tablename__ = "Logs"
#     logger = Column(db.String)  # the name of the logger. (e.g. myapp.views)
#     level = Column(db.String)  # info, debug, or error?
#     trace = Column(db.String)  # the full traceback printout
#     msg = Column(db.String)  # any custom log you may have included
#     created_at = Column(db.DateTime, default=datetime.now)  # the current timestamp

#     def __init__(self, logger=None, level=None, trace=None, msg=None):
#         self.logger = logger
#         self.level = level
#         self.trace = trace
#         self.msg = msg

#     def __unicode__(self):
#         return self.__repr__()

#     def __repr__(self):
#         return "<Log: %s - %s>" % (
#             self.created_at.strftime("%m/%d/%Y-%H:%M:%S"),
#             self.msg[:50],
#         )
