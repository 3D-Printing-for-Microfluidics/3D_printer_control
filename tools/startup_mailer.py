import subprocess
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import time

# delay to give internet time to connect
time.sleep(30)

# change to your own account information
to = ['3d.printer.raspberry.pi@gmail.com']          # emails to send to.
gmail_user = '3d.printer.raspberry.pi@gmail.com'    # email to send from. (MUST BE GMAIL)
gmail_password = '3dprinter'                        # gmail password.
smtpserver = smtplib.SMTP('smtp.gmail.com', 587)    # server to use.

# helper function to make interface name more human friendly
def connect_type(word_list):
    """ This function takes a list of words, then, depeding which key word, returns the corresponding
    internet connection type as a string. ie) 'ethernet'.
    """
    if 'wlan0' in word_list or 'wlan1' in word_list:
        con_type = 'WiFi'
    elif 'eth0' in word_list:
        con_type = 'Ethernet'
    else:
        con_type = 'current'
    return con_type

# start a connection to the mail server
smtpserver.ehlo()                                   # say 'hello' to the server
smtpserver.starttls()                               # start TLS encryption
smtpserver.ehlo()
smtpserver.login(gmail_user, gmail_password)        # log in to server

# get hostname of device sending the email
hostname = subprocess.Popen('hostname', shell=True, stdout=subprocess.PIPE).communicate()[0].decode().strip()

# runs 'ip route list' in a hidden terminal
data = subprocess.Popen('ip route list', shell=True, stdout=subprocess.PIPE).communicate()[0]

# parse response for connection type and IP address
data = data.decode().splitlines()[0].split()
ip_address = data[data.index('src')+1]
connection_type = connect_type(data[data.index('src')-1])

# format the email
for recipient in to:
    msg = MIMEText('Your {} IP address is {}'.format(connection_type, ip_address))
    msg['Subject'] = 'IP address for {} RaspberryPi on {}'.format(hostname, datetime.now().strftime('%d %b %Y at %H:%M:%S'))
    msg['From'] = gmail_user
    msg['To'] = recipient

    # send the email
    smtpserver.sendmail(gmail_user, [recipient], msg.as_string())

# close the smtp server.
smtpserver.quit()
