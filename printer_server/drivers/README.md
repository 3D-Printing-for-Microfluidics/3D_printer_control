# 3D Printer Hardware Drivers

This directory contains the hardware drivers for controlling various components of the 3D printer system. The drivers are designed with a modular architecture that supports both real hardware and dummy implementations for testing.

## Driver Architecture

The driver system follows a hierarchical design with:
- Abstract base classes in `generic_drivers/` defining common interfaces
- Concrete implementations for specific hardware
- Dummy implementations for testing and development

### Base Classes

The `generic_drivers/` directory contains abstract base classes for different types of hardware:

1. **Stage Drivers**
   - `BPStageDriver`: Build platform stage control
   - `XYStageDriver`: XY motion stage control
   - `FocusStageDriver`: Focus stage control
   - `TTRStageDriver`: Tip-tilt-rotate stage control

2. **Communication Drivers**
   - `EthernetSerial`: Base class for Ethernet-based serial communication
   - `USBSerial`: Base class USB-based serial communication

## Available Drivers

### Motion Control
- `acs/`: ACS motion controller driver
- `galil/`: Galil motion controller driver
- `hexapod/`: Hexapod stage driver
- `thorlabs_apt`: Thorlabs motor driver for KDC101 and LTS stages
- `tiptilt/`: Custom Tip-tilt stage driver for optical alignment

### Light Control
- `screen/`: Screen control system
- `visitech/`: Visitech light engine driver
- `wintech/`: Wintech DLP controller driver

### Sensors
- `accelerometer/`: Accelerometer driver
- `environmental_sensors/`: Environmental monitoring sensors
- `keyence/`: Keyence confocal displacement sensor driver
- `loadcell/`: Load cell sensor for force measurement
- `photodiode/`: Photodiode sensor driver
- `spectrometer/`: Spectrometer driver

### Auxillary Control
- `external_control/`: External control system interface
- `gpio/`: General Purpose I/O control
- `mks/`: MKS 946 pressure controller driver
- `mks_teensy/`: Teensy-based MKS controller and GPIO interface

### Other
- `coord_systems/`: Coordinate system transformation utilities


## Driver Implementation

Each driver follows a common pattern:
1. Inherits from appropriate base class
2. Implements required interface methods
3. Provides hardware-specific functionality
4. Includes error handling and logging
5. Supports both real and dummy implementations

### Example Usage

```python
from printer_server.drivers.galil import Galil, Galil_dummy

# For real hardware
driver = Galil(config_dict=config, log_level=logging.INFO)

# For testing/development
driver = Galil_dummy(config_dict=config, log_level=logging.INFO)
```

## Adding New Drivers

To add a new driver:

1. Create a new directory in `drivers/`
2. Implement the driver class inheriting from appropriate base class
3. Create a dummy implementation for testing
4. Add driver configuration to hardware configuration JSON
5. Update `hardware_configuration.py` to support the new driver

## Testing

Each driver should have:
- A dummy implementation for testing
- Appropriate Manual Control _snip code

## Configuration

Drivers are configured through JSON files in the `hardware_configuration/` directory. Each driver can specify:
- Connection parameters
- Hardware-specific settings
- Dummy mode for testing
- Logging configuration

## Error Handling

Drivers implement comprehensive error handling:
- Connection failures
- Hardware communication errors
- Invalid commands
- Timeout handling
- Recovery procedures

## Logging

All drivers use the Python logging system with:
- Configurable log levels
- Hardware-specific log messages
- Error tracking
- Performance monitoring 