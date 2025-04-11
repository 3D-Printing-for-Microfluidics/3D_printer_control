# Print File Validator

This directory contains the validation system for 3D printer print job files. The validator ensures that print job files follow the correct format and contain all required information before they are processed by the printer.

## Overview

The print file validator:
1. Validates print job files against JSON schemas
2. Supports multiple schema versions (v0.1, v2.x, v3.x, v4.x)
3. Checks for file integrity and required components
4. Validates image references and settings
5. Ensures compatibility with printer hardware

## Schema Versions

The system supports several schema versions:

### v0.1 (Legacy)
- Basic print job format
- Simple layer settings
- Limited validation

### v2.x (Current)
- Enhanced validation
- Support for named settings
- Template system
- Improved layer control

### v3.x (Current)
- Extended features
    - Adds XY stages
- Additional validation rules
- Enhanced template support

### v4.x (Current)
- Latest features
    - Adds multiple light engine support
- Advanced validation
- Extended hardware support

### v999 (Testing)
- Special schema for testing
- Allows custom functions
- Minimal validation

## Print Job Structure

A valid print job file is a ZIP archive containing:

1. **JSON Configuration File**
   - Header information
   - Design details
   - Default settings
   - Layer-specific settings

2. **Image Directory**
   - Layer images
   - Support files
   - Calibration data

## Validation Process

The validator performs several checks:

1. **File Structure**
   - Valid ZIP archive
   - Single JSON configuration file
   - Required directories present

2. **Schema Validation**
   - JSON structure matches schema
   - Required fields present
   - Values within valid ranges

3. **Reference Validation**
   - Image files exist
   - Templates are valid
   - Named settings are defined

4. **Compatibility**
   - Schema version supported
   - Hardware requirements met
   - Settings within printer limits

## Usage

```python
from printer_server.print_file_validator import validate_schema

# Validate a print job file
try:
    print_settings, schema_version = validate_schema("print_job.zip")
    print(f"Valid {schema_version} print job")
except ValueError as ex:
    print(f"Validation failed: {ex}")
```

## Schema Examples

### Basic Print Job (v2.x)
```json
{
    "Header": {
        "Schema version": "2.3.0",
        "Image directory": "slices",
        "Print under vacuum": false
    },
    "Design": {
        "Purpose": "Test print",
        "Description": "Simple test structure",
        "Resin": "PEGDA"
    },
    "Default layer settings": {
        "Layer thickness (um)": 50,
        "Distance up (mm)": 5,
        "Initial wait (ms)": 100
    }
}
```

## Error Handling

The validator provides detailed error messages for:
- Invalid file formats
- Missing required fields
- Invalid values
- Missing references
- Schema version mismatches

## Testing

The validator includes test files in `test_print_files_v2/` for:
- Valid print jobs
- Common error cases
- Edge cases
- Version compatibility

## Integration

The validator is integrated with:
- Print job upload system
- Printer control system
- Web interface
- Job queue management

## Adding New Schema Versions

To add a new schema version:

1. Create new schema file (e.g., `schema_v5.json`)
2. Update version checking in `print_file_validator.py`
3. Add schema to printer configuration
4. Update documentation
5. Add test cases 