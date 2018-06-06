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
        assert ps.totalLayerNum == 20
        
    def test_map_of_layers(self):
        ps = PrintSettings.fromFile(filename='tests/dummy_files/print_settings/print_settings.json')
        assert ps.__mapOfLayers == [0, 1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 
                                    10, 11, 12, 13, 14, 15, 16, 17, 18]
        
    def test_layer_thickness_mm(self):
        ps = PrintSettings.fromFile(filename='tests/dummy_files/print_settings/print_settings.json')
        assert ps.layerThicknessMm(1) == 0.02
        assert ps.layerThicknessMm(2) == 0.01
        assert ps.layerThicknessMm(3) == 0.01
        assert ps.layerThicknessMm(15) == 0.005
        assert ps.layerThicknessMm(16) == 0.0075
        assert ps.layerThicknessMm(17) == 0.008
        
    def test_validate_passed(self):
        fileToTest = os.path.join(Config.PROJECT_ROOT, 'tests', 'dummy_files', 
                                  'zipfiles', 'correct_job.zip')
        path = os.path.join(Config.UPLOAD_FOLDER, 'tmp')
        assert PrintSettings.validate(fileToTest, path)
        
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
        
    def test_validate_fails_when_key_missing(self):
        fileToTest = os.path.join(Config.PROJECT_ROOT, 'tests', 'dummy_files', 
                                  'zipfiles', 'key_missing.zip')
        path = os.path.join(Config.UPLOAD_FOLDER, 'tmp')
        assert not PrintSettings.validate(fileToTest, path)
        
    def test_validate_fails_when_too_many_json(self):
        fileToTest = os.path.join(Config.PROJECT_ROOT, 'tests', 'dummy_files', 
                                  'zipfiles', 'too_many_json.zip')
        path = os.path.join(Config.UPLOAD_FOLDER, 'tmp')
        assert not PrintSettings.validate(fileToTest, path)

