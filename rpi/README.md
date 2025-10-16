# Raspberry Pi Scripts

This directory contains scripts and utilities for managing the 3D printer control system on Raspberry Pi devices.

## Scripts Overview

### `local_server_start.sh`
Starts the printer server manually for development or testing purposes.
```bash
# Usage
cd /path/to/3D_printer_control
source rpi/local_server_start.sh
```

### `flask_db_setup.sh`
Initializes and configures the Flask database for the printer control system.
```bash
# Usage
cd /path/to/3D_printer_control
source rpi/flask_db_setup.sh
```

### `flash_firmware.sh`
Automated firmware flashing utility for supported hardware components.
```bash
# Usage
cd /path/to/3D_printer_control
source rpi/flash_firmware.sh
```
This script:
- Detects connected hardware
- Verifies firmware versions
- Handles firmware updates
- Provides error reporting
- Supports multiple hardware types

### `install_firmware_flasher.sh`
Installs the firmware flashing utility and its dependencies.
```bash
# Usage
cd /path/to/3D_printer_control
source rpi/install_firmware_flasher.sh
```

## Directory Structure

```
rpi/
├── bin/                    # Binary files and utilities
├── flash_firmware.sh       # Firmware flashing script
├── flask_db_setup.sh       # Database initialization
├── install_firmware_flasher.sh  # Firmware utility installer
└── local_server_start.sh   # Manual server start script
```

## Troubleshooting

### Server Start Issues
- Ensure you're in the correct directory
- Check if the virtual environment is activated
- Verify all dependencies are installed
- Check system logs for errors

### Database Setup Problems
- Verify database permissions
- Check for existing database files
- Ensure Flask environment is properly configured
- Review error logs

### Firmware Flashing Issues
- Check hardware connections
- Verify firmware file integrity
- Ensure proper permissions
- Review hardware-specific documentation

## Notes

- All scripts should be run from the top-level `3D_printer_control` directory
- Scripts use `source` to ensure environment variables are properly set
- Some operations may require root privileges
- Always backup data before firmware updates
