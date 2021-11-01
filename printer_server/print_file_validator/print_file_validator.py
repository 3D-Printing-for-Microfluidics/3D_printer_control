import json
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from tempfile import TemporaryDirectory
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError
from PIL import Image


def validate_v02(print_file):
    """Validate a version 0.2 print file and return the print settings
    as JSON. If an error is detected, a ValueError is raised with
    appropriate information.
    """
    try:
        with ZipFile(
            print_file, "r"
        ) as zip_file_handle, TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            zip_file_handle.extractall(temp_dir)
            print_settings = check_for_unique_print_settings(temp_dir)
            check_version(print_settings)
            validate_against_schema(print_settings, "schema_v0.2.json")
            check_slices_folder_exists(zip_file_handle, print_settings)
            check_referenced_images_exist(print_settings, temp_dir)
            return print_settings
    except BadZipFile:
        msg = "File is not a .zip file."
        raise ValueError(msg)


def read_json(path_to_file):
    """Helper function to return the json data from a file."""
    with open(path_to_file, "r") as file_handle:
        return json.load(file_handle)


def check_for_unique_print_settings(unzipped_dir):
    """Return the print settings as JSON, checking that there is only 1
    print settings file in the directory.
    """
    json_files = list(unzipped_dir.glob("*.json"))
    if len(json_files) < 1:
        msg = "Could not find a json file. "
        msg += "Make sure there is a json file in the top level directory."
        raise ValueError(msg)
    if len(json_files) > 1:
        raise ValueError(f"More than 1 json file: {json_files}")
    return read_json(json_files[0])


def check_slices_folder_exists(zip_file_handle, print_settings):
    """Ensure the specified image folder exists in the print file."""
    slices_folder = print_settings["Header"]["Image directory"]
    if not any(slices_folder for f in zip_file_handle.namelist()):
        raise ValueError(f"Could not find image folder: {slices_folder}")


def check_version(print_settings):
    """Check the version of print settings file. Should be '0.2'."""
    if print_settings["Header"]["Schema version"] != "0.2":
        msg = "File is not version 0.2. Use converter to convert to version 0.2"
        raise ValueError(msg)


def validate_against_schema(print_settings, schema):
    """Check the print settings against the schema."""
    here = Path(__file__).parent.absolute()
    schema = here / Path(schema)
    try:
        Draft7Validator(read_json(schema)).validate(print_settings)
    except ValidationError as e:
        path_string = " -> ".join(f"'{str(v)}'" for v in e.path)
        msg = f"  {e.message}\n  Check {path_string}"
        raise ValueError(msg)


def check_image_format(image_file):
    """Ensure the image is an 8-bit grayscale PNG."""
    with Image.open(image_file) as img:
        if img.format != "PNG" or img.mode != "L":
            msg = f"Bad image. '{image_file}' must be an 8-bit grayscale PNG."
            raise ValueError(msg)


def check_referenced_images_exist(print_settings, temp_dir):
    """Ensure that all images referenced in the print settings are
    included in the print file. Uses the default image if no override is
    provided.
    """
    slices_folder = Path(print_settings["Header"]["Image directory"])
    slices = list(temp_dir.glob(f"{slices_folder}/*.png"))
    img = print_settings["Default layer settings"]["Image settings"]["Image file"]

    if temp_dir / slices_folder / Path(img) not in slices:
        msg = f"Missing image. Default image {img} could not be found.\n"
        msg += "  Check 'Default layer settings' -> 'Image settings' -> 'Image file'"
        raise ValueError(msg)
    for layer in print_settings["Layers"]:
        if "Image settings list" in layer:
            for image_setting in layer["Image settings list"]:
                if "Image file" in image_setting:
                    img = image_setting["Image file"]
                    img_path = temp_dir / slices_folder / Path(img)
                    if img_path not in slices:
                        msg = f"Missing image: '{img}' could not be found."
                        raise ValueError(msg)
                    check_image_format(img_path)


if __name__ == "__main__":
    for print_job in Path("test_print_files_v2").glob("*.zip"):
        try:
            validate_v02(print_job)
            print(f"{print_job} is good")
        except ValueError as e:
            print(f"Error in {print_job}:\n {e}")
