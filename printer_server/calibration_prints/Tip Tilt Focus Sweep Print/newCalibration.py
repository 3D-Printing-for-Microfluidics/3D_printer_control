import pymfcad

import inspect

class focus_square(pymfcad.Component):
    def __init__(self, focus_shift=0, pillar_size=3, pillar_height=2, pillar_spacing=2, pillar_grid=(2,2), quiet = False):
        # Store constructor arguments for equality comparison.
        frame = inspect.currentframe()
        args, _, _, values = inspect.getargvalues(frame)
        self.init_args = [values[arg] for arg in args if arg != "self"]
        self.init_kwargs = {arg: values[arg] for arg in args if arg != "self"}

        # Initialize the base Component
        super().__init__(
            size=(
                pillar_size*pillar_grid[0]+pillar_spacing*(pillar_grid[0]-1),
                pillar_size*pillar_grid[1]+pillar_spacing*(pillar_grid[1]-1),
                pillar_height
            ),
            position=(0, 0, 0),
            px_size=0.0076,
            layer_size=0.01,
            quiet=quiet
        )
        
        # Add labels
        self.add_label("object", pymfcad.Color.from_name("xkcd:pumpkin", 256))
        self.add_label("exposure", pymfcad.Color.from_name("xkcd:teal", 125))

        # Add slicing settings (bulk exposure, default settings, etc)
        options = pymfcad.ExposureSettings(relative_focus_position=focus_shift, bulk_exposure_multiplier=2.0)
        self.add_default_exposure_settings(options, "exposure")

        # Add bulk
        for row in range(pillar_grid[0]):
            for col in range(pillar_grid[1]):
                square = pymfcad.Cube([pillar_size,pillar_size,pillar_height]).translate([col*(pillar_size+pillar_spacing),row*(pillar_size+pillar_spacing),0])
                self.add_bulk(f"pillar_{row}_{col}", square, "object")


px_size=0.0076
height = 20
focus_shift = 1
tiptilt_shift = 100
tip_position = 0
tilt_position = 0
dist_from_center = round(5/px_size)
bulk_height = 18
pillar_spacing = 2
pillar_size = 3
pillar_grid = (2,2)
grid_gap = 4

pillar_array_x = pillar_size*pillar_grid[0] + pillar_spacing*(pillar_grid[0]-1)
pillar_array_y = pillar_size*pillar_grid[1] + pillar_spacing*(pillar_grid[1]-1)

center_offset_x = (pillar_array_x*5+grid_gap*4)/2
center_offset_y = (pillar_array_y*5+grid_gap*4)/2

component = pymfcad.Device.with_visitech_1x(
    name="calibration_print",
    position=[0,0,0],
    layers=height,
)

component.add_label("bulk", pymfcad.Color.from_name("xkcd:light urple", 256))
component.add_label("text", pymfcad.Color.from_name("xkcd:kermit green", 128))

plus = pymfcad.TextExtrusion("+", bulk_height, font_size=500, quiet=True).translate([component.get_size()[0]-400,component.get_size()[1]-400,0])
minus = pymfcad.TextExtrusion("-", bulk_height, font_size=500, quiet=True).translate([160,100,0])

component.add_void("plus", plus, "text")
component.add_void("minus", minus, "text")


for x,y,pos in [[0,0,"origin"], [1,0,"right"], [-1,0,"left"], [0,1,"top"], [0,-1,"bottom"]]:
    x_pos = component.get_size()[0]/2-center_offset_x+x*dist_from_center
    y_pos = component.get_size()[1]/2-center_offset_y+y*dist_from_center
    pillar_position = -12
    for j in range(5):
        for i in range(5):
            pillar_array = focus_square(focus_shift=focus_shift*pillar_position if pos=="origin" else tiptilt_shift*pillar_position, quiet=True)
            pillar_array.translate([x_pos+(pillar_array_x+grid_gap)*i, y_pos+(pillar_array_y+grid_gap)*j, bulk_height])
            pillar_position += 1
            component.add_subcomponent(f"pillar_{pos}_{i}_{j}", pillar_array)

base = pymfcad.Cube([component.get_size()[0],component.get_size()[1],bulk_height])
component.add_bulk("base", base, label="bulk")

component.set_burn_in_exposure([10000.0, 5000.0, 2500.0])

component.preview()

from pymfcad import (
    Settings,
    ResinType,
    Printer,
    LightEngine,
    PositionSettings,
    ExposureSettings,
)

settings = Settings(
    printer=Printer(
        name="OS1",
        light_engines=[
            LightEngine(px_size=0.0076, px_count=(2560, 1600), wavelengths=[365], grayscale_available=[True])
        ],
        xy_stage_available=True,
    ),
    resin=ResinType(bulk_exposure=350.0, exposure_offset=0.0, monomer=[("PEG", 100)], uv_absorbers=[("AVO", 0.42)], initiators=[("IRG", 1.0)]),
    default_position_settings=PositionSettings(),
    default_exposure_settings=ExposureSettings(grayscale_correction=True),
)

from pymfcad import Slicer

slicer = Slicer(
    device=component,
    settings=settings,
    filename="OS1_calibration_1mrad_20um_350ms",
    minimize_file=True,
    zip_output=True,
    
)

slicer.make_print_file()