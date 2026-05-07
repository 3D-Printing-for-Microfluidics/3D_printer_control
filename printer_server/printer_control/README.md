# Printer Control System

This directory contains the core control system for the 3D printer. The system implements a modular, thread-safe architecture for controlling various hardware components during the printing process.

## Overview

The printer control system:
1. Manages hardware initialization and connection
2. Handles print job execution and control
3. Provides real-time monitoring and feedback
4. Implements safety checks and error handling
5. Supports pause/resume/stop operations

## Core Components

### Base Control Class (`print_control.py`)
The `PrintControl` class provides the foundation for all printer operations:
- Thread management for long-running operations
- State management (uninitialized, initialized, planarizing, printing, etc.)
- Basic hardware control interfaces
- Error handling and recovery
- Logging and event tracking

### Hardware Control Classes

1. **Build Platform Control** (`bp_control.py`)
   - Manages build platform movement
   - Handles planarization
   - Controls layer positioning
   - Implements safety limits

2. **Light Engine Control** (`light_engine_control.py`)
   - Controls light exposure
   - Manages LED power
   - Handles grayscale correction
   - Implements light engine sequencing

3. **XY Stage Control** (`xy_control.py`)
   - Manages XY positioning
   - Handles stage movement
   - Controls stage calibration
   - Implements position logging

4. **Focus Control** (`focus_control.py`)
   - Manages focus stage
   - Handles focus positioning
   - Controls focus calibration
   - Implements focus logging

5. **TTR Control** (`ttr_control.py`)
   - Manages tip-tilt-rotate stage
   - Handles TTR positioning
   - Controls TTR calibration
   - Implements TTR logging

6. **Load Cell Control** (`loadcell_control.py`)
   - Monitors build platform force
   - Implements loadcell based planarization
   - Implement force squeezing
   - Implements force logging

7. **Light Measurement Control** (`light_measurement_control.py`)
   - Measures light intensity
   - Implements light logging

8. **GPIO Control** (`gpio_control.py`)
   - Manages general I/O
   - Handles system signals

9. **Accelerometer Control** (`accelerometer_control.py`)
   - Monitors vibration

10. **Keyence Focus Control** (`keyence_focus_control.py`)
    - Manages distance sensing
    - Switches focus to distance based measurement
    - Implements height logging

## Print Process Flow

1. **Initialization**
   ```python
   printer = PrintControl()
   printer.initialize(critical_error_handle)
   ```

2. **Planarization**
   ```python
   printer.planarization_step_1()  # Lower platform
   printer.planarization_step_2()  # Set reference position
   ```

3. **Print Job Execution**
   ```python
   printer.start(job_id)  # Start print
   # ... printing occurs ...
   printer.pause()  # Optional pause
   printer.resume()  # Resume after pause
   printer.stop()    # Stop print
   ```

## Thread Safety

The system uses a thread-safe architecture:
- Each hardware component runs in its own thread
- Thread synchronization using events and locks
- Safe state transitions
- Error propagation between threads

## Error Handling

The system implements comprehensive error handling:
- Hardware connection failures
- Communication errors
- Motion errors
- Safety limit violations
- Critical error handling

## Logging

The system provides detailed logging:
- Event logging
- Hardware state logging
- Error logging
- Performance metrics
- Calibration data

## Integration

The control system integrates with:
- Web interface
- Job queue management
- Hardware configuration
- Print file validation
- Calibration system

## Development

To add new hardware support:
1. Create new control class inheriting from `PrintControl`
2. Implement required methods
3. Add hardware initialization
4. Implement error handling
5. Add logging support
6. Update hardware configuration 