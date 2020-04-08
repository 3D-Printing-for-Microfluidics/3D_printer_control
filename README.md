

# Purpose - 4/08/2020

This repository's `master` branch contains the code being actively used by the Raspberry Pi 3 B+ (RPi) on the HR3.3 3D printer.

A summary of the active branches is listed below:  

  * `HR2` - software in use on the HR2 3D printer
  * `EMBL_stable` - software in use on the EMBL 3D printer
  * `EMBL` - buggy software intended for the EMBL 3D printer, but abandoned
  * `HR3v2` - software in use on the HR3.2 3D printer
  * `HR3v3` - software in use for the HR3.3 3D printer. This branch will stay up to date with `master` until `master` diverges for a newer printer
  * `gen1-1` - software used on the now defunct gen1-1 (now named HR1.1) 3D printer  


# Running the dummy server

## Setup 

To run the dummy server to develop on, do the following: 
  * Check which version of pip you are using with `pip --version`. If it is not the python 3.5 version, then try `pip3 --version`. If you have to use `pip3` to get the correct version, use `pip3` instead of `pip` below. 
  * The server must be run in a python virtual environment. Install the virtual environment with `pip install virtualenv` or `pip3` if applicable. 
  * Create the virtual environment with `python -m virtualenv env`. This will create a virtual environment called `env` that will be ignored by git
  * Activate the virtual enviropnment with `source /env/bin/activate` 
  * Check to make sure you are now in the virtual environment with `which python`. You should see something like `path/to/here/env/bin/python`. If you see something like `/usr/bin.python` you are not in the virtual environment.  
  * Install all required modules with `pip install -r requirements/dev.txt` or `pip3 install -r requirements/dev.txt` as appropriate
    * both python and pip are likely the correct version now that you installed them in the virtual environment, so you may no longer have to use `pip3` or `python3`. You can check with `python --version` or `pip --version` again from inside the new virtual environment
  * Set the required $FLASK_APP environment variable. This varies based on platform. For bash do `export FLASK_APP=tests/dummy_server.py`
  * If you get an error that you don't have mttkinter, run `pip install mttkinter` or `pip3 install mttkinter`
  * Do the following only if you don't have a database built yet (i.e. it's your first time running this app)
    * Source the new setup script in `printer_server/rpi/`   
      -- or do it manually --   
    * Initialize the database with `flask db init`
    * Migrate it with `flask db migrate`
    * Upgrade it with `flask db upgrade` 

## Debug Mode (Recommended for development)
You can also optionally enable debug mode, which gives you feedback in the terminal and automatically restarts the server on file changes, by setting the debug environment variable with `export FLASK_DEBUG=1`. Set this to 0 to disable it again later. 

After this is all done, run the dummy server with `python $FLASK_APP` or `python3 $FLASK_APP`. (Make sure you are using Python 3.5, using `python --version` to double check if it doesn't work) (\*Note from Clayton: I got the dummy server to work without Anaconda.) 

In debug mode, the server will automatically reload changed Python and HTML files. We suggest using Incognito mode during development to prevent your browser from caching old versions of files. `CNTL+F5` can also help on Chrome if files aren't updating when you save them. This seems to happen especially with CSS files. 

Right now the page is hosted locally at `http://127.0.0.1:5000` but this is configurable. To host it to the public IP of your computer, change the IP address to `0.0.0.0:some_port` in `app.py`

## More info 

This page talks all about flask and how to use it. It is very helpful if you want to know more about how the server runs: http://flask.pocoo.org/docs/1.0/quickstart/

Additionally, here is some good info on the python virtual environment we are using: https://docs.python.org/3/tutorial/venv.html
