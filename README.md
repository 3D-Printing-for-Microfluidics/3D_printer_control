# 3D Printer Control System

A sophisticated control system for custom DLP-SLA 3D printers, built with Flask and WebSocket communication. This system provides a robust web interface for controlling and monitoring 3D printing operations, with support for various hardware configurations and real-time feedback.

# Overview

This system is designed to control custom DLP-SLA 3D printers using a JSON-based print file format. The print files are validated using a custom JSON schema validator to ensure proper formatting and compatibility. The system supports multiple printer configurations and can be adapted to different hardware setups through its modular architecture.

## System Architecture

### Backend
- Built on Flask web server with modular blueprint structure
- Uses Socket.IO for real-time bidirectional communication between frontend and backend
- Implements a modular hardware driver system for various printer components
- Database-driven job queue management using SQLAlchemy
- Comprehensive logging system with configurable levels and file rotation
- Error handling and recovery mechanisms for hardware failures

### Frontend
- JINJA2 templating engine for HTML structure
- Bootstrap (Darkly theme) for responsive styling
- JavaScript libraries:
  - Socket.IO for real-time communication
  - AJAX for asynchronous requests
  - jQuery for DOM manipulation
  - Popper.js for tooltips and popovers
- Dynamic UI updates for real-time printer status
- Responsive design for various screen sizes

## Hardware Configuration

The system uses a flexible hardware configuration system that:
- Loads hardware configurations based on device hostname
- Supports multiple types of hardware drivers:
  - Virtual hardware (screen, coord_systems, external_control)
  - Abstract base classes and generic drivers (e.g., Visitech light engine, ACS XY/BP stage, Hexapod TTR/focus stage)
  - Regular hardware drivers
- Includes firmware management capabilities through `flash_firmware.sh` RPi script
- Provides dummy drivers for testing and development
- Supports hardware-specific calibration and configuration
- Implements hardware abstraction layers for consistent control interfaces

### Hardware Types
1. **Motion Control**
   - XY stages (ACS, custom implementations)
   - Z-axis control
   - Build plate control
   - Tip-tilt-rotate (TTR) stages
   - Focus stages

2. **Light Control**
   - DLP light engines
   - Screen control systems

3. **Sensors**
   - Load cells
   - Keyence sensors
   - Environmental sensors
   - Accelerometers
   - Light measurement systems

4. **Auxiliary Systems**
   - Vacuum control
   - GPIO control
   - Film control
   - Environmental monitoring

## Core Components

### Manual Controls
- Each hardware driver has associated frontend controls
- Automatically populated based on hardware configuration
- Provides fine-grained control over hardware components
- Allows modification of system settings
- Real-time feedback and status updates
- Safety interlocks and emergency stop functionality

### Views
1. **Print History**
   - Displays recent prints with detailed information
   - Enables job download and re-queue functionality
   - Print success/failure statistics
   - Job parameter history

2. **Server Logs**
   - Shows last 2 weeks of logs
   - Includes calibration position logs
   - Hardware-specific diagnostic information
   - Error tracking and debugging tools

3. **Calibration**
   - Manages printer calibration settings
   - Supports focus, tip, tilt adjustments
   - Integrates with Keyence sensors and Hexapod systems
   - Calibration profile management
   - Automated calibration routines

### Main Printer Control (home.py)
The central control system that:
- Manages print uploads and job queue
- Handles printer planarization
- Controls print operations (start/pause/resume/stop)
- Provides real-time feedback (loadcell data, log messages)
- Implements a dynamic class hierarchy for hardware control
- Error handling and recovery
- State management and synchronization

## Hardware Control Architecture

The system uses a dynamic class composition approach:
- Base `print_control` class defines core functionality
- Hardware-specific subclasses extend functionality
- Class composition is determined by hardware configuration
- Import order is critical for proper initialization and print operations
- Thread-safe operation handling
- Event-driven architecture for hardware interactions

# Raspberry Pi Deployment

This section details the setup process for deploying the system on a Raspberry Pi 5 with NVME storage. See also the `How to do a full install of a HR5 Raspberry Pi` ProjectWiki page for a more detailed guide with rationale.

### Hardware Requirements

- Raspberry Pi 5
- Pimoroni NVME base
- Crucial P3 Plus 1TB SSD (or compatible)
- External SSD housing (for initial setup)

### Initial Setup

1. **Physical Setup**
   - Install NVME SSD and Pimoroni NVME base
   - Follow [Pimoroni NVME base tutorial](https://learn.pimoroni.com/article/getting-started-with-nvme-base)

2. **OS Installation**
   - Download Raspberry Pi Imager
   - Flash Raspberry Pi OS (64-bit) 2024-03-15
   - Configure initial settings:
     - Set hostname (e.g., HR5, MR1v1, HR3v3)
     - Username: pi
     - Password: 3dprinter
     - Timezone: Denver
     - Enable SSH

3. **System Configuration**
   - Configure SSD boot:
     ```bash
     # Edit /boot/firmware/config.txt
     dtparam=pciex1
     nvme_core.default_ps_max_latency_us=0 pcie_aspm=off
     
     # Configure EEPROM
     sudo rpi-eeprom-config --edit
     # Set:
     BOOT_ORDER=0xf416
     PCIE_PROBE=1
     ```
   - Set system clock: `date -s 'YYYY-MM-DD HH:MM:SS'`
   - Configure network:
     - Connect to BYU-Wifi via https://onboard.byu.edu/guest/public/index.html
     - Set static ethernet address (192.168.0.1/24) using `sudo nmtui`
   - Switch to legacy X11:
     ```bash
     sudo raspi-config
     # Advanced Options -> Wayland -> X11
     ```
   - Disable screen blanking:
     ```bash
     sudo raspi-config
     # Display Options -> Screen Blanking -> No
     ```

4. **USB Device Configuration**
   - Create udev rules for USB devices:
     ```bash
     # Wintech
     sudo nano /etc/udev/rules.d/99-wintech.rules
     SUBSYSTEM=="usb",ATTRS{idVendor}=="0451",ATTRS{idProduct}=="c900",GROUP="users",MODE:="0666"
     
     # MKS Controller
     sudo nano /etc/udev/rules.d/99-mks.rules
     SUBSYSTEM=="usb",ATTRS{idVendor}=="0403",ATTRS{idProduct}=="6001",GROUP="users",MODE:="0666"
     
     # Thorlabs Power Meter
     sudo nano /etc/udev/rules.d/99-thorlabspm100.rules
     SUBSYSTEM=="usb",ATTRS{idVendor}=="1313",ATTRS{idProduct}=="8072",GROUP="users",MODE:="0666"
     ```
   - Reload udev rules: `sudo udevadm control --reload-rules`

5. **System Logging**
   - Configure journald:
     ```bash
     # Edit /etc/systemd/journald.conf
     [Journal]
     MaxRetentionSec=1week
     MaxFileSec=1day
     
     # Create journal directory
     mkdir /var/log/journal
     sudo systemd-tmpfiles --create --prefix /var/log/journal
     ```

### Software Installation

1. **Clone Repositories**
   ```bash
   git clone https://github.com/3D-Printing-for-Microfluidics/IP_address_service.git
   git clone https://github.com/gregnordin/3D_printer_control.git
   ```

2. **Install IP Address Service**
   ```bash
   cd IP_address_service/ip_address_service
   sudo -s source ip_address_service_setup.sh
   ```

3. **Setup Python Environment**
   ```bash
   cd 3D_printer_control
   python -m venv env
   source env/bin/activate
   mkdir logs
   
   # Upgrade pip and setuptools
   pip install pip --upgrade
   pip install setuptools --upgrade
   ```

4. **Install Galil Driver**
   ```bash
   # Install CGLib Software
   sudo apt install ./requirements/galil-release_1_all.deb
   sudo apt update
   sudo apt install gclib gcapsd
   
   # Install Python bindings
   pip install ./requirements/gclib-1.0.0-py3-none-any.whl
   ```

5. **Install Python Dependencies**
   ```bash
   pip install -r requirements/prod.txt  # For production
   # or
   pip install -r requirements/dev.txt   # For development
   ```

   Key dependencies include:
   - Flask 3.0.3 with Flask-SocketIO 5.3.6 for web server and real-time communication
   - SQLAlchemy 2.0.31 and Flask-SQLAlchemy 3.1.1 for database management
   - Hardware control libraries:
     - gclib for Galil motion controllers
     - gpiod 2.2.0 and gpiozero 2.0.1 for GPIO control
     - pyserial 3.5 for serial communication
     - pyusb 1.2.1 for USB device control
   - Scientific computing:
     - numpy 2.0.0 and scipy 1.14.1 for numerical operations
     - matplotlib 3.10.1 for plotting
     - pandas 2.2.3 for data manipulation
   - Hardware-specific:
     - ThorlabsPM100 1.2.2 for power meter control
     - seabreeze 2.9.2 for spectrometer integration
     - PIPython 2.10.2.1 for PI motion controllers
   - System utilities:
     - psutil 6.0.0 for system monitoring
     - zeroconf 0.132.2 for network discovery
   - Development tools:
     - jsonschema 4.22.0 for JSON validation
     - scapy 2.5.0 for network analysis

6. **Setup Flask Database**
   ```bash
   source rpi/flask_db_setup.sh
   ```

7. **Configure Systemd Service**
   ```bash
   # Allow X server access
   export DISPLAY=:0.0
   xhost si:localuser:pi
   
   # Create service file
   sudo nano /etc/systemd/system/3d-printer-server.service
   ```
   Add to service file:
   ```ini
   [Unit]
   Description=3D Printer Server
   After=network.target
   
   [Service]
   Type=simple
   WorkingDirectory=/home/pi/3D_printer_control
   Environment=FLASK_APP=/home/pi/3D_printer_control/autoapp.py
   Environment=XAUTHORITY=/home/pi/.Xauthority
   Environment=DISPLAY=:0.0
   ExecStart=/home/pi/3D_printer_control/env/bin/python /home/pi/3D_printer_control/autoapp.py
   Restart=always
   
   [Install]
   WantedBy=multi-user.target
   ```
   Enable and start service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable 3d-printer-server.service
   sudo systemctl start 3d-printer-server.service
   ```

### Display Configuration

1. **Setup Custom Resolutions**
   ```bash
   # Create autostart directory
   mkdir -p ~/.config/autostart
   
   # Create desktop entry
   nano ~/.config/autostart/xrandr.desktop
   ```
   Add to desktop entry:
   ```ini
   [Desktop Entry]
   Type=Application
   Exec=/home/pi/.config/autostart/xrandr.sh
   Hidden=false
   NoDisplay=false
   X-GNOME-Autostart-enabled=true
   Name[en_US]=Xrandr
   Name=Xrandr
   Comment[en_US]=Set custom resolution using xrandr
   Comment=Set custom resolution using xrandr
   ```
   
   Create resolution script:
   ```bash
   nano ~/.config/autostart/xrandr.sh
   ```
   Add to script:
   ```bash
   #!/bin/sh
   export DISPLAY=:0.0
   
   # Visitech resolution (2560x1600)
   xrandr --newmode "2560x1600_30" 132.68 2560 2608 2640 2720 1600 1603 1609 1623 +hsync -vsync
   xrandr --addmode HDMI-1 2560x1600_30
   xrandr --output HDMI-1 --mode 2560x1600_30
   
   # Wintech resolution (1920x1080)
   xrandr --newmode "1920x1080_60" 148.50 1920 2008 2096 2200 1080 1084 1089 1125 +hsync -vsync
   xrandr --addmode HDMI-2 1920x1080_60
   xrandr --output HDMI-2 --mode 1920x1080_60
   ```
   Make script executable:
   ```bash
   chmod +x ~/.config/autostart/xrandr.sh
   ```

### Additional Hardware Notes

- Spectrometer: Update firmware to NI-VISA version using Thorlabs Driver Switcher
- PI Hexapod stage: Update IP address to match subnet (192.168.x.x)
- ACS stages: Configure static IP and update to match subnet

# Development Setup

### Prerequisites
- Python 3.5 or higher
- Virtual environment (recommended)
- Required Python packages (see requirements/dev.txt)
- Git

### Installation Steps
1. Clone the repository
2. Create and activate virtual environment:
   ```bash
   python -m virtualenv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements/dev.txt
   ```
4. Set up environment variables:
   ```bash
   export FLASK_APP=tests/dummy_server.py
   export FLASK_DEBUG=1  # For development mode
   ```
5. Initialize database:
   ```bash
   flask db init
   flask db migrate
   flask db upgrade
   ```

### Running the Development Server
1. Start the server:
   ```bash
   python $FLASK_APP
   ```
2. Access the web interface at `http://127.0.0.1:5000`
3. For external access, modify `app.py` to use `0.0.0.0:port`

### Development Tips
- Use Incognito mode to prevent browser caching
- Press `Ctrl+F5` in Chrome to force refresh
- Monitor terminal output for debug information
- Check logs in `printer_server/logs/`

# Active Branches

This repository maintains several branches for different printer configurations:
- `master` - Stable branch for 3D printers
- `dev/ branches` - Current active development branches
- `feature/ branches` - Branches adding new feature to 3D printers
- `stable/ branches` - Legacy release branches no longer in use
- `gen1-1` - Legacy software for HR1.1 3D printer

# Troubleshooting

### Common Issues

1. **Hardware Connection**
   - Check USB connections
   - Verify permissions
   - Test hardware directly
   - Check logs for errors

2. **Firmware Issues**
   - Verify firmware version
   - Check flash process
   - Review error logs
   - Test with dummy firmware

3. **Web Interface**
   - Clear browser cache
   - Check Socket.IO connection
   - Verify JavaScript console
   - Test in incognito mode

# Additional Resources

- [Flask Documentation](http://flask.pocoo.org/docs/1.0/quickstart/)
- [Python Virtual Environment Guide](https://docs.python.org/3/tutorial/venv.html)
- [Socket.IO Documentation](https://socket.io/docs/)
- [Bootstrap Documentation](https://getbootstrap.com/docs/)

# License

This project is licensed under the terms specified in the LICENSE.txt file.