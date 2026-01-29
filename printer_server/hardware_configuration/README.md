# Hardware Configuration System

This directory contains JSON configuration files that define the hardware setup for each 3D printer in the system. Each printer has its own configuration file named after its hostname (e.g., `HR5.json`, `MR1v1.json`).

## Configuration Structure

Each configuration file contains several key sections:

### 1. Schema Version
```json
"valid_schema_versions": ["v4", "v3", "v2"]
```
Specifies which schema versions are supported by the configuration.

### 2. Coordinate Systems
```json
"_systems": {
    "global": { "X": 0, "Y": 0, "Focus": 0, "Build Platform": 0 },
    "parked": { "X": 100, "Y": 85, "Focus": 0, "Build Platform": 0 },
    "visitech": { "X": -0.4, "Y": 1.06, "Focus": 2.893, "Build Platform": 0 }
}
```
Defines different inate systems for various components and positions.

### 3. Stage Configuration
```json
"stages": {
    "bp_stage": "acs",
    "focus_stage": "hexapod",
    "xy_stage": "acs",
    "ttr_stage": "hexapod"
}
```
Specifies which drivers control each stage of the printer.

### 4. Hardware Components

Each hardware component has its own configuration section with common fields:
- `dummy`: Boolean flag for testing/development
- Component-specific parameters (addresses, ports, calibration values, etc.)

#### Motion Control
- `acs/`: ACS motion controller settings
- `galil/`: Galil motion controller settings
- `kdc101_ttrf/`: Thorlabs KDC101 settings for Tip/Tilt/Focus stage
- `lts_xy`: Thorlabs LTS settings for XY stage
- `hexapod/`: Hexapod stage settings
- `tiptilt/`: Tip-tilt stage settings

#### Light Control
- `visitech/`: Visitech light engine settings
- `wintech/`: Wintech DLP controller settings
- `screen/`: Screen control settings
- `light_engines/`: List of available light engines

#### Sensors
- `keyence/`: Keyence sensor settings
- `loadcell/`: Load cell settings
- `spectrometer/`: Spectrometer settings
- `environmental_sensors/`: Environmental monitoring settings
- `accelerometer/`: Accelerometer settings

#### GPIO Control
- `gpio/`: General Purpose I/O settings

## Example Configuration

Here's a simplified example of a configuration file:

```json
{
    "valid_schema_versions": ["v3", "v2"],
    "_systems": {
        "global": { "X": 0, "Y": 0, "Focus": 0, "Build Platform": 0 }
    },
    "stages": {
        "bp_stage": "acs",
        "focus_stage": "hexapod",
        "xy_stage": "acs",
        "ttr_stage": "hexapod"
    },
    "acs": {
        "dummy": false,
        "address": "192.168.0.5",
        "port": 701,
        "axes": ["0", "1", "2"],
        "axes_common_names": ["X", "Y", "Build Platform"]
    },
    "hexapod": {
        "dummy": false,
        "address": "192.168.0.6",
        "port": 50000,
        "axes": ["Z", "U", "V", "W"],
        "axes_common_names": ["Focus", "Tip", "Tilt", "Rotate"]
    }
}
```

## Adding New Hardware

To add new hardware to a printer:

1. Create a new driver in the `drivers/` directory
2. Add a configuration section to the printer's JSON file
3. Update `hardware_configuration.py` to support the new hardware
4. Add any necessary inate systems or stage mappings

## Firmware Management

The configuration system supports firmware management through the `flash_firmware.sh` script. Hardware components that require firmware updates should include:
- `vendor_id`
- `product_id`
- `serial_number`
- `firmware_path`
- `microcontroller` type

## Testing

For development and testing:
1. Set `"dummy": true` for hardware components
2. Use the dummy implementations of drivers
3. Test with simulated hardware responses

## Validation

Configuration files are validated against a JSON schema to ensure:
- Required fields are present
- Values are within expected ranges
- Hardware combinations are compatible
- Coordinate systems are properly defined 