"""
    Standard for Print Job
    ======================

    JSON File
    ---------

    Boilerplate
    ^^^^^^^^^^^

    The JSON file contains all the information needed for a print 
    besides the images. Here is a most simplified version, namely, 
    all the entries are necessary. ::

        {
        "Header": {
            "Schema version": "0.1",
            "Image directory": "slices"
        },
        "Default settings": {
            "Light engine power setting": 100,
            "Layer exposure time (ms)": 400,
            "Layer thickness (um)": 10,
            "Number of duplications": 1,
            "Solus command chain": [
            "WAIT 0.1",
            "BP UP 1 SPEED 300",
            "QW DOWN 6 SPEED 400",
            "WAIT 1.5",
            "BP UP 2 SPEED 400",
            "QW UP 6 SPEED 400",
            "BP DOWN 3 SPEED 400",
            "WAIT 1.5"
            ]
        },
        "Layers": [
            {
            "Images": [
                "0000.png"
            ]
            }
        ]
        }

    **Explanation of all entries**

    #. Header

        #. Schema version - for backward compatibility
        #. Image directory - relative the directory of JSON file

    #. Default settings - Default values

        #. Light engine power setting - an integer between 0 and 1000
        #. Layer exposure time (ms)
        #. Layer thickness (um)
        #. Number of duplications - If a number of consective layers 
        share the same images and parameters, we can set 
        ``Number of duplications`` to reduce json file footprint.
        #. Solus command chain - command chain 
        to tell solus how to move BP and QW. 
        (Details: :ref:`solus_command_chain`)

    #. Layers - a list of layer settings. Each item in the list 
    is corresponding to multiple layers, when 
    ``Number of duplications`` is greater than 1.


    .. _solus_command_chain:

    Solus command chain
    ^^^^^^^^^^^^^^^^^^^

    The Solus movement starts from right after exposure, and ends 
    right before another exposure. Here, a new API for moving build 
    platform and quartz window is introduced. With the new API, any 
    arbitrary combination of movements can be implemented by 
    chaining a list of commands. 

    **Command format examples**

    * Wait (WAIT)

        * Wait 1.5 seconds
            * ``WAIT 1.5``

    * Build Platform (BP)

        * Move build platform up 1 mm at 300 mm/min
            * ``BP UP 1 SPEED 300``

        * Move build platform down 1.5 mm at 400 mm/min
            * ``BP DOWN 1.5 SPEED 400``

    * Quartz Window (QW)

        * Move quartz window up 2 mm at 500 mm/min
            * ``QW UP 1.5 SPEED 500``

        * Move quartz window down 1 mm at 600 mm/min
            * ``QW DOWN 1 SPEED 600``

    **Rules**

    We can almost chain commands however we want to, but there are 
    still some rules.

    * ``BP`` rules

        #. Speed must be positive integer.
        #. Max speed: 800 mm/min
        #. The total distance of ``BP UP`` should be the same as 
        ``BP DOWN``. 
        #. The build platform absolute position should always be 
        between layer position and 90 mm. 

    * ``QW`` rules

        #. Speed must be positive integer.
        #. Max speed: 800 mm/min
        #. The total distance of ``QW UP`` should be the same as 
        ``QW DOWN``.
        #. The quartz window absolute position should always be 
        between 0 and 6 mm. 

    .. Note::
        Because ``BP UP`` distance is equal to ``BP DOWN`` distance, 
        there is not a new layer of resin between the printed part 
        and the teflon film. But it is taken care of by 
        Solus.printCycle method, where it automatically reduce the 
        last ``BP DOWN`` distance by the layer thickness.


    JSON with extra information and customized layer settings
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    Besides basic information, we can add detailed description under 
    other entries. This extra information does not affect the print 
    in any way. Example ::

        {
        "Design": {
            "Purpose": "String with short statement about design's 
                        purpose.",
            "Description": "String containing description of design 
                            to be printed with this JSON file. Could 
                            be multi-line by using '\\n' to separate 
                            lines.",
            "Resin": "Resin that this design is intended to be used 
                    with. Example: PEGDA with 2% NPS and 1% 
                    Irgacure 819.",
            "3D printer": "3D printer that this design is intended 
                        to be printed on.",
            "Design file": "<filename> (OpenSCAD or other 3D CAD file 
                            containing design)",
            "STL file": "<filename>",
            "Slicer": "Specify which slicer was used to create png 
                    images from STL file.",
            "Date": "Date file was sliced."
        },
        "Header": {
            "Comment": "This section contains information about the 
                        schema and the directory where to find images, 
                        which is specified relative to the directory 
                        in which this json file resides. If the json 
                        file is in the same directory as the png 
                        images, this would be `.`",
            "Schema version": "0.1",
            "Image directory": "slices"
        }
        "Default settings": {
            "Comment": "Default settings for the Printer. Unless 
                        otherwise defined in the layer, these are 
                        the values that are to be used for each 
                        layer.",
            "Light engine power setting": 100,
            "Layer exposure time (ms)": 400,
            "Layer thickness (um)": 10,
            "Number of duplications": 1,
            "Solus command chain": [
            "WAIT 0.1",
            "BP UP 1 SPEED 300",
            "QW DOWN 6 SPEED 400",
            "WAIT 1.5",
            "BP UP 2 SPEED 400",
            "QW UP 6 SPEED 400",
            "BP DOWN 3 SPEED 400",
            "WAIT 1.5"
            ]
        },
        "Layers": [
            {
            "Images": [
                "0000.png"
            ],
            "Layer exposure time (ms)": [
                20000
            ],
            "Layer thickness (um)": 20,
            "Comment": "This layer has a custom exposure time and 
                        layer thickness."
            },
            {
            "Images": [
                "0000.png"
            ],
            "Layer exposure time (ms)": [
                10000
            ],
            "Number of duplications": 2,
            "Comment": "This layer is duplicated twice, which means 
                        it is actually for layer 2 and 3."
            },
            {
            "Images": [
                "0000.png"
            ],
            "Layer exposure time (ms)": [
                5000
            ],
            "Light engine power setting": [
                200
            ],
            "Comment": "This layer has custom light engine power 
                        setting."
            },
            {
            "Images": [
                "0001.png",
                "0001a.png"
            ],
            "Comment": "This layer exposes 2 images using default 
                        settings."
            },
            {
            "Images": [
                "0002.png",
                "0002a.png"
            ],
            "Layer exposure time (ms)": [
                400,
                200
            ],
            "Comment": "This layer exposes 2 images with different 
                        exposure times."
            },
            {
            "Images": [
                "0003.png",
                "0003a.png"
            ],
            "Light engine power setting": [
                200,
                400,
            ],
            "Comment": "This layer exposes 2 images with different 
                        light engine power settings."
            },
            {
            "Images": [
                "0004.png",
                "0004a.png"
            ],
            "Layer exposure time (ms)": [
                400,
                200
            ],
            "Light engine power setting": [
                200,
                400,
            ],
            "Comment": "This layer exposes 2 images with different 
                        exposure times and light engine power 
                        settings."
            },
            {
            "Images": [
                "0005.png"
            ],
            "Solus command chain": [
                "WAIT 0.1",
                "BP UP 3 SPEED 300",
                "QW DOWN 6 SPEED 400",
                "WAIT 1.5",
                "QW UP 6 SPEED 400",
                "BP DOWN 3 SPEED 400",
                "WAIT 1.5"
            ],
            "Comment": "The layer has its own command chain to 
                        control Solus."
            },
            {
            "Images": [
                "0006.png"
            ],
            "Comment": "A normal layer"
            }
        ]
        }

    We can customize any layer by override the default values. In 
    the above JSON file, the first list item in ``Layers`` contains 
    ``Layer exposure time (ms)`` and ``Layer thickness (um)``, 
    which means the first layer will have exposure time of 20000 ms 
    and layer thickness of 20 um. Note that a number of consective 
    layers can share one list item by making 
    ``Number of duplications`` greater than 1. The purpose is to 
    reduce repetitive information. For instance, in the second list 
    item above, ``Number of duplications`` is 2, which is mapped to 
    layer 2 and 3. 

    Also, a layer can expose however many images. For every image, 
    you can set exposure times and light engine power settings, 
    repectively. If so, every image must have an exposure time. Same 
    for light engine power setting. 


    Format of A Print Job
    ---------------------

    To submit a print job to the 3D printer, a ZIP file is the only 
    format the 3D printer accepts. This ZIP file should contain only 
    one JSON file, named ``print_settings.json``, and all the images 
    that will be used for this print job. The file structure in the 
    ZIP file should be as following ::

        .
        ├── print_settings.json
        └── slices
            ├── 0000.png
            ├── 0001.png
            ├── 0002.png
            └── 0003.png
                .
                .
                .

    The name of the JSON file must be ``print_settings.json``, and 
    the names of the images and image folder name need to match what 
    is specified in the json file. 

    .. Note::
        After the ZIP file is extracted, the JSON file directory will 
        be used as the root directory. Image directory is relative 
        to the root directory. 

"""
import os 
import sys 
import json
import argparse
from PIL import Image
from zipfile import ZipFile 
from datetime import datetime

# Default output filename includes the date and time of creation 
output_filename = '{}.zip'.format(datetime.now().strftime('print_%Y-%m-%d_%H-%M-%S.%f')[:-4])

normal_layer_um  = 10               # Normal layer thickness 
normal_exp_time_ms = 600            # Normal layer exposure time 
normal_le_power = 100               # Normal light engine power 
slices_folder = "slices"            # The folder the slices are located in 

# Add argument parser and options 
parser = argparse.ArgumentParser(add_help=False)

help_msg = "Set output filename. Defaults to time of creation."
parser.add_argument("-o", dest='output_filename', help=help_msg)

help_msg = "Set layer thickness (um). Defaults to " + str(normal_layer_um ) + "."
parser.add_argument("-z", dest='layer_thickness', type=int, help=help_msg)

help_msg = "Set layer exposure time (ms). Defaults to " + str(normal_exp_time_ms) + "."
parser.add_argument("-e", dest='normal_exp_time', type=int, help=help_msg)

help_msg = "Set path to the folder containing the slices. Defaults to '" + slices_folder + "'."
parser.add_argument("-s", dest='slices_folder', help=help_msg)

parser.add_argument("-h", "--help", help="Show this help message and exit.", action='help')

args = parser.parse_args()

# If an option is selected, update it's value 
if args.output_filename: output_filename    = args.output_filename
if args.layer_thickness: normal_layer_um    = args.layer_thickness
if args.normal_exp_time: normal_exp_time_ms = args.normal_exp_time
if args.slices_folder  : slices_folder      = args.slices_folder

# Other default values that aren't updatable via cmd line 
nomal_solus_chain = [                       # Normal solus command chain 
    "WAIT 0.1",
    "BP UP 1 SPEED 400",
    "QW DOWN 3 SPEED 300",
    "WAIT 1.0",
    "BP UP 2 SPEED 400",
    "QW UP 3 SPEED 300",
    "BP DOWN 3 SPEED 400",
    "WAIT 1.0"
]
bi_exp_ms = [20000, 10000, 5000, 1000, 500] # Burn in exposure times 
data = {                                    # Default fields  
    "Design": {
        "Purpose": "",
        "Description": "",
        "Resin": "",
        "3D printer": "",
        "Design file": "",
        "STL file": "",
        "Slicer": "",
        "Date": ""
    },
    "Header": {
        "Comment": "",
        "Schema version": "0.1",
        "Image directory": slices_folder
    },
    "Default settings": {
        "Comment": "Settings used for each layer, if not overridden by layer specific settings.",
        "Light engine power setting": normal_le_power,
        "Layer exposure time (ms)": normal_exp_time_ms,
        "Layer thickness (um)": normal_layer_um,
        "Number of duplications": 1,
        "Solus command chain": nomal_solus_chain
    },
    "Layers": []   # a list of dictionaries that represent each layer 
}

def validate_slice(imageFile):
    try: 
        with Image.open(imageFile) as pilImage:                     # Open file as PIL object 
            if pilImage.format == "PNG" and pilImage.mode == "L":   # Check format and mode
                return True                                         # Image is good 
    except (OSError, FileNotFoundError):                            # File has big issues 
        pass
    return False                                                    # Image is bad 

try:
    # Open a zip archive to write to 
    with ZipFile(output_filename, 'x') as myzip:

        # Get the directory this script is executing from 
        this_directory = os.path.dirname(os.path.realpath(sys.argv[0]))

        # Try opening the slices folder and generating a list of images 
        try: 
            slices = os.listdir(slices_folder)   
        except (OSError, FileNotFoundError): 
            error_msg = "Error: Folder '" + slices_folder + "' does not exist\n"
            error_msg += "Try '" + sys.argv[0] + " --help' for help."
            sys.exit(error_msg)

        # Iterate over the slices 
        for i in range(len(slices)):   
            curr_slice = slices[i]
            path_to_slice = os.path.join(this_directory, slices_folder, curr_slice)

            # Check to see if each slice is good 
            if not validate_slice(path_to_slice): 
                error_msg = "Error: Bad slice provided: " + curr_slice + "\n"
                error_msg += "All images must be 8-bit grayscale PNG format"
                sys.exit(error_msg)

            # Add the image file to print data for this layer 
            this_layer = {"Images": [curr_slice]}

            # Add the image to the print zip archive 
            myzip.write(os.path.join(slices_folder, curr_slice))

            # If this is a burn in layer and the normal exposure is lower than 
            # the burn in exposure, use the burn in exposure  
            if i < len(bi_exp_ms) and bi_exp_ms[i] > normal_exp_time_ms:
                    this_layer["Layer exposure time (ms)"] = [bi_exp_ms[i]]

            # Add the full dictionary for this layer to the full print data
            data["Layers"].append(this_layer)

        # Write print settings file 
        print_settings_filename = 'print_settings.json'
        with open(print_settings_filename, 'w', newline='\r\n') as fileOut:
            json.dump(data, fileOut, indent=2)

        # Add to zip archive 
        myzip.write(print_settings_filename)

        # Remove temp file from system 
        os.remove(print_settings_filename)

except FileExistsError:
    error_msg =  "Error: The file '" + output_filename
    error_msg += "' already exists. Delete ot or use a different name."
    sys.exit(error_msg)