# How to start the dummy server

    $ cd /path/to/tests
    $ export FLASK_APP=dummy_server.py
    $ export FLASK_DEBUG=1
    $ flask db init
    $ flask db migrate
    $ flask db upgrade
    $ python dummy_server.py