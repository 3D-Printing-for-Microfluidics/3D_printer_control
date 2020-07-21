# -*- coding: utf-8 -*-
"""Database models"""
import datetime as dt

from printer_server.database import (
    Column,
    Model,
    SurrogatePK,
    db,
    reference_col,
    relationship,
)


class User(SurrogatePK, Model):
    """A user of the app."""

    __tablename__ = "Users"
    username = Column(db.String(80), unique=True, nullable=False)
    email = Column(db.String(80), unique=True, nullable=False)
    password = Column(db.Binary(128), nullable=True)  #: The hashed password
    created_at = Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    first_name = Column(db.String(30), nullable=True)
    last_name = Column(db.String(30), nullable=True)
    active = Column(db.Boolean(), default=False)
    is_admin = Column(db.Boolean(), default=False)

    def __init__(self, username, email, password=None, **kwargs):
        """Create instance."""
        db.Model.__init__(self, username=username, email=email, **kwargs)
        if password:
            self.set_password(password)
        else:
            self.password = None

    def set_password(self, password):
        """Set password."""
        self.password = b"[password]" + password.encode()

    def check_password(self, value):
        """Check password."""
        return self.password == b"[password]" + value.encode()

    @property
    def full_name(self):
        """Full user name."""
        return "{0} {1}".format(self.first_name, self.last_name)

    def __repr__(self):
        """Represent instance as a unique string."""
        return "<User({username!r})>".format(username=self.username)


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

    @property
    def zip_filename(self):
        """The filename used to archive the ZIP file is based on
        its upload time.

        Example::

            upload_time -- 2018/04/30 10:00:00.123456.
            zip_filename -- job-2018-05-10T02-41-18.960939.zip
        """
        return "{}.zip".format(self.upload_time.strftime("job-%Y-%m-%d_%H-%M-%S.%f"))


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
    start_ip = Column(db.String(30))
    start_time = Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    end_time = Column(db.DateTime)
    completed = Column(db.Boolean, nullable=False, default=False)

    @property
    def zip_filename(self):
        """The filename used to archive the ZIP file is based on
        its upload time.

        Example::

            upload_time -- 2018/04/30 10:00:00.123456.
            zip_filename -- job-2018-05-10T02-41-18.960939.zip
        """
        return "{}.zip".format(self.upload_time.strftime("job-%Y-%m-%d_%H-%M-%S.%f"))


class ServerLog(SurrogatePK, Model):
    __tablename__ = "Logs"
    logger = Column(db.String)  # the name of the logger. (e.g. myapp.views)
    level = Column(db.String)  # info, debug, or error?
    trace = Column(db.String)  # the full traceback printout
    msg = Column(db.String)  # any custom log you may have included
    created_at = Column(db.DateTime, default=dt.datetime.utcnow)  # the current timestamp

    def __init__(self, logger=None, level=None, trace=None, msg=None):
        self.logger = logger
        self.level = level
        self.trace = trace
        self.msg = msg

    def __unicode__(self):
        return self.__repr__()

    def __repr__(self):
        return "<Log: %s - %s>" % (
            self.created_at.strftime("%m/%d/%Y-%H:%M:%S"),
            self.msg[:50],
        )
