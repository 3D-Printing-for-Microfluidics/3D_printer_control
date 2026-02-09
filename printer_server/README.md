# Printer Server

This directory contains the main server application for the 3D printer control system. The server provides a web interface for controlling the printer and managing print jobs.

## Core Application Files

### `app.py`
Main Flask application file that:
- Initializes the Flask application
- Sets up blueprints and routes
- Configures extensions and middleware
- Handles application-wide settings

### `database.py`
Database configuration and management:
- SQLAlchemy setup
- Database connection handling
- Migration management
- Session configuration

### `models.py`
Database models defining:
- Print job records
- User settings
- Server logs

### `forms.py`
Web form definitions for:
- User registration (not used)

### `settings.py`
Application settings and configuration:
- Environment variables
- System parameters
- Feature flags
- Default values

### `extensions.py`
Flask extensions initialization:
- SQLAlchemy
- Socket.IO
- Login manager
- Other third-party extensions

### `commands.py`
CLI commands for:
- Database management
- System maintenance
- Debug operations
- Development tasks

### `logging_handler.py`
Logging configuration and management:
- Log format setup
- File rotation
- Log levels

### `threading_wrapper.py`
Thread management utilities:
- Thread creation
- Error handling
- Thread logging
- Thread profiling

### `async_file_handler.py`
Asynchronous file operations:
- Log file management

### `compat.py`
Compatibility utilities:
- Version-specific code
- Platform-specific handling
- Backward compatibility
- System-specific features

## Directory Structure

- `printer_control/` - Hardware control system
- `print_file_validator/` - Print file validation
- `hardware_configuration/` - Hardware configuration
- `drivers/` - Hardware drivers
- `views/` - Web interface views
- `templates/` - HTML templates
- `static/` - Static web assets
- `grayscale_correction_data/` - Grayscale correction data 