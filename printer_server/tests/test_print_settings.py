import pytest
import json
import os

from printer_server.printer.print_settings import PrintSettings
from printer_server.settings import Config


class TestPrintSettings:
    
    def test_use_settings_arg_to_init(self):
        with open('tests/dummy_files/print_settings/print_settings.json', 'r') as f:
            settings = json.load(f)
        ps = PrintSettings(settings=settings)
        
    def test_use_filename_to_init(self):
        ps = PrintSettings.fromFile(filename='tests/dummy_files/print_settings/print_settings.json')
        
    def test_total_layer_number(self):
        ps = PrintSettings.fromFile(filename='tests/dummy_files/print_settings/print_settings.json')
        assert ps.totalLayerNum == 6
        
    def test_map_of_layers(self):
        ps = PrintSettings.fromFile(filename='tests/dummy_files/print_settings/print_settings.json')
        ps.images(1) == ['0001.png']
        ps.images(2) == ['0001.png']
        ps.images(3) == ['0002a.png', '0002b.png']
        ps.images(4) == ['0002a.png', '0002b.png']
        ps.images(5) == ['0002a.png', '0002b.png']
        
    # TODO: test when default `Number of duplications` is greater than 1.
        
    def test_layer_thickness_mm(self):
        ps = PrintSettings.fromFile(filename='tests/dummy_files/print_settings/print_settings.json')
        assert ps.layerThicknessMm(1) == 0.01
        assert ps.layerThicknessMm(2) == 0.01
        assert ps.layerThicknessMm(3) == 0.01
        assert ps.layerThicknessMm(4) == 0.01
        assert ps.layerThicknessMm(5) == 0.01
        assert ps.layerThicknessMm(6) == 0.005
        
    def test_validate_passed(self):
        fileToTest = os.path.join(Config.PROJECT_ROOT, 'tests', 'dummy_files', 
                                  'zipfiles', 'correct_job.zip')
        path = os.path.join(Config.UPLOAD_FOLDER, 'tmp')
        assert PrintSettings.validate(fileToTest, path)
        
    def test_validate_fails_when_BP_net_moving_distance_is_not_zero(self):
        fileToTest = os.path.join(Config.PROJECT_ROOT, 'tests', 'dummy_files', 
                                  'zipfiles', 'BP_net_moving_distance_is_not_zero.zip')
        path = os.path.join(Config.UPLOAD_FOLDER, 'tmp')
        assert not PrintSettings.validate(fileToTest, path)
        
    def test_validate_fails_when_zipfile_is_corrupted(self):
        fileToTest = os.path.join(Config.PROJECT_ROOT, 'tests', 'dummy_files', 
                                  'zipfiles', 'corrupted.zip')
        path = os.path.join(Config.UPLOAD_FOLDER, 'tmp')
        assert not PrintSettings.validate(fileToTest, path)
        
    def test_validate_fails_when_default_value_is_not_number(self):
        fileToTest = os.path.join(Config.PROJECT_ROOT, 'tests', 'dummy_files', 
                                  'zipfiles', 'default_value_is_not_number.zip')
        path = os.path.join(Config.UPLOAD_FOLDER, 'tmp')
        assert not PrintSettings.validate(fileToTest, path)
    
    def test_validate_fails_when_exposure_time_is_not_number(self):
        fileToTest = os.path.join(Config.PROJECT_ROOT, 'tests', 'dummy_files', 
                                  'zipfiles', 'exposure_time_is_not_number.zip')
        path = os.path.join(Config.UPLOAD_FOLDER, 'tmp')
        assert not PrintSettings.validate(fileToTest, path)
        
    def test_validate_fails_when_image_not_found(self):
        fileToTest = os.path.join(Config.PROJECT_ROOT, 'tests', 'dummy_files', 
                                  'zipfiles', 'image_not_found.zip')
        path = os.path.join(Config.UPLOAD_FOLDER, 'tmp')
        assert not PrintSettings.validate(fileToTest, path)
        
    def test_validate_fails_when_images_exposure_time_dont_match(self):
        fileToTest = os.path.join(Config.PROJECT_ROOT, 'tests', 'dummy_files', 
                                  'zipfiles', 'images_exposure_time_dont_match.zip')
        path = os.path.join(Config.UPLOAD_FOLDER, 'tmp')
        assert not PrintSettings.validate(fileToTest, path)
        
    def test_validate_fails_when_key_missing(self):
        fileToTest = os.path.join(Config.PROJECT_ROOT, 'tests', 'dummy_files', 
                                  'zipfiles', 'incomplete_default_parameters.zip')
        path = os.path.join(Config.UPLOAD_FOLDER, 'tmp')
        assert not PrintSettings.validate(fileToTest, path)
        
    def test_validate_fails_when_json_file_not_found(self):
        fileToTest = os.path.join(Config.PROJECT_ROOT, 'tests', 'dummy_files', 
                                  'zipfiles', 'json_file_not_found.zip')
        path = os.path.join(Config.UPLOAD_FOLDER, 'tmp')
        assert not PrintSettings.validate(fileToTest, path)
        
    def test_validate_fails_when_json_syntax_is_wrong(self):
        fileToTest = os.path.join(Config.PROJECT_ROOT, 'tests', 'dummy_files', 
                                  'zipfiles', 'json_syntax_is_wrong.zip')
        path = os.path.join(Config.UPLOAD_FOLDER, 'tmp')
        assert not PrintSettings.validate(fileToTest, path)


