# Running the dummy server

### Setup 

To run the dummy server to develop on, do the following: 
  * Navigate to the printer_server directory (3D_printer_control/printer_server)
  * Check which version of pip you are using with `pip --version`. If it is not the python 3.5 version, then try `pip3 --version`. If you have to use `pip3` to get the correct version, use `pip3` instead of `pip` below. 
  * Install all required modules with `pip install -r requirements/dev.txt` or `pip3 install -r requirements/dev.txt` as appropriate
  * Set the required $FLASK_APP environment variable. This varies based on platform. For bash do `export FLASK_APP=tests/dummy_server.py`
  * If you get an ereror that you don't have mttkinter, run `pip install mttkinter` or `pip3 install mttkinter`
  * Do the following only if you don't have a database built yet (i.e. it's your first time running this app)
    * Initialize the database with `flask db init`
    * Migrate it with `flask db migrate`
    * Upgrade it with `flask db upgrade` 

### Debug Mode (Recommended for development)
You can also optionally enable debug mode, which gives you feedback in the terminal, by setting the debug environment variable with `export FLASK_DEBUG=1`. Set this to 0 to disable it again later. 

After this is all done, run the dummy server with `python $FLASK_APP` or `python3 $FLASK_APP`. (Make sure you are using Python 3.5, using `python --version` to double check if it doesn't work) (\*Note from Clayton: I got the dummy server to work without Anaconda.) 

In debug mode, the server will automatically reload changed Python and HTML files. We suggest using Incognito mode during development to prevent your browser from caching old versions of files. `CNTL+F5` can also help on Chrome if files aren't updating when you save them. This seems to happen especially with CSS files. 

Right now the page is hosted locally at `http://127.0.0.1:5000` but this is configurable. 

### More info 

This page talks all about flask and how to use it. It is very helpful if you want to know more about how the server runs: http://flask.pocoo.org/docs/1.0/quickstart/

