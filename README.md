

# Purpose - 9/2/19 - GN

This repository's `master` branch contains the code being actively used by the Raspberry Pi 3 B+ (RPi) on the HR3 3D printer. Going forward, the code in this branch should always be the active code being used on the RPi. Therefore all development focused on modifying and improving the actively used HR3 (and, soon, HR3.1) RPi code must be done on this branch.

**The `HR3P2` branch has the current software in development for the new HR3.2 printer.** 


# To do

- Change load cell Teensy and python code so that data errors are handled without generating malformed csv files
- Fix format of file with encoder data that is recorded for each print run
- Change motor control on front end so that arbitrary positions can be entered rather than only being able to jog to a position in at minimum 10 &mu;m increments


# Running the dummy server

## Setup 

To run the dummy server to develop on, do the following: 
  * Navigate to the printer_server directory (3D_printer_control/printer_server)
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
