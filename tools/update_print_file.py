from os import fdopen, remove, close
from shutil import move
import re
import sys
import zipfile
from tempfile import mkstemp
import PySimpleGUI as sg

layout = [
    [sg.Text('Pick files to update')],
    [sg.Input(key='_FILES_'), sg.FilesBrowse()],
    [sg.OK(), sg.Cancel()]
]

window = sg.Window('Convert print file', layout)
event, values = window.Read()


files_to_convert = values['_FILES_'].split(';')


for f in files_to_convert:
    # with zipfile.ZipFile(f, 'r') as zip_ref:
    #     zip_ref.extractall("./update_temp")


    # with open("./update_temp/print_settings.json", "r+") as new_file:
    #     for line in new_file:
    #         pass

    # file_path = "./update_temp/print_settings.json"
    file_path = f

    fh, abs_path = mkstemp()
    with fdopen(fh, 'w') as new_file:
        with open(file_path) as old_file:
            for line in old_file:
                # new_file.write(line.replace("^QW&", ""))
                new_file.write(re.sub(r"^QW$", "", line))   # strip any references to QW
                new_file.write(re.sub(r"\".*?command chain.*\"", "command chain", line))   # strip any references to QW

    #Remove original file
    remove(file_path)
    #Move new file
    move(abs_path, file_path)

    # clean up temporary files
    # close(fh)
    # remove(fh)
