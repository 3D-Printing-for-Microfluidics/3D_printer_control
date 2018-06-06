from factory import PostGenerationMethodCall, Sequence, LazyFunction, LazyAttribute
from factory.alchemy import SQLAlchemyModelFactory
from datetime import datetime

from printer_server.database import db
from printer_server.models import User, PrintJob, PrintRecord


class BaseFactory(SQLAlchemyModelFactory):
    """Base factory."""

    class Meta:
        """Factory configuration."""

        abstract = True
        sqlalchemy_session = db.session


class UserFactory(BaseFactory):
    """User factory."""

    username = Sequence(lambda n: 'user{0}'.format(n))
    email = Sequence(lambda n: 'user{0}@example.com'.format(n))
    password = PostGenerationMethodCall('set_password', 'example')
    active = True

    class Meta:
        """Factory configuration."""
        model = User


class PrintJobFactory(BaseFactory):
    
    original_filename = Sequence(lambda n: 'job{0}.zip'.format(n))
    upload_time = LazyFunction(datetime.now)
    ip = Sequence(lambda n: '{0}.{0}.{0}.{0}'.format(n))
    
    class Meta:
        model = PrintJob


class PrintRecordFactory(BaseFactory):
    
    original_filename = Sequence(lambda n: 'job{0}.zip'.format(n))
    upload_time = Sequence(lambda n: datetime(2018, 5, n%30+1))
    upload_ip = Sequence(lambda n: '{0}.{0}.{0}.{0}'.format(n))
    start_ip = LazyAttribute(lambda a: '{0}'.format(a.upload_ip))
    start_time = Sequence(lambda n: datetime(2018, 5, n%30+1))
    end_time = Sequence(lambda n: datetime(2018, 5, n%30+1))
    completed = Sequence(lambda n: (n%2)==0)
    
    class Meta:
        model = PrintRecord
