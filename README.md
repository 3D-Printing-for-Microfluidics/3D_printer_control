# Running the dummy server

### Setup 

To run the dummy server to develop on, do the following: 

  * Install all required modules with `pip install -r ../requirements/dev.txt`
  * Set the required $FLASK_APP environment variable. This varies based on platform, but for bash do `export FLASK_APP=tests/dummy_server.py`
  * Do the following only if you don't have a database built yet (i.e. it's your first time running this app)
    * Initialize the database with `flask db init`
    * Migrate it with `flask db migrate`
    * Upgrade it with `flask db upgrade` 

### Debug Mode (Recommended for development)
You can also optionally enable debug mode, which gives you feedback in the terminal, by setting the debug environment variable with `export FLASK_DEBUG=1`. Set this to 0 to disable it again later. 

After this is all done, run the dummy server with `python $FLASK_APP`. (Make sure you are using Anaconda)

In debug mode, the server will automatically reload changed Python and HTML files. We suggest using Incognito mode during development to prevent your browser from caching old versions of files. `CNTL+F5` can also help on Chrome if files aren't updating when you save them. This seems to happen especially with CSS files. 

Right now the page is hosted locally at `http://127.0.0.1:5000` but this is configurable. 



