#!/bin/bash

# =========== INFO ============
# This script parses the hardware_config.json files and looks for firmware to flash.
#
# Valid json objects have at least the objects in the example below: 
#    "vendor_id": 5824,
#    "product_id": 1155,
#    "serial_number": "5746950",
#    "firmware_path": "mks_firmware/mks_firmware.ino",
#    "microcontroller": "Teensy3.2" (options are currently ArduinoNano, Teensy3.2, Teensy4.0, and Teensy4.1)
#
# Usage: source flash_firmware.sh (then select which firmware to flash)
# - or -
# source flash_firmware.sh --auto (to flash all fimware)
# =============================

# ======= Configuration =======
CONFIG_PATH="test.json"  # Path to the JSON configuration file
# =============================


# Function to get board settings
get_board_settings() {
    case $1 in
        ArduinoNano)
            FQBN="arduino:avr:nano"
            UPLOAD_TOOL="avrdude"
            MCU="atmega328p"
            UPLOAD_SPEED="57600"
            ;;
        Teensy3.2)
            FQBN="teensy:avr:teensy31"
            UPLOAD_TOOL="teensy_loader_cli"
            MCU="teensy32"
            ;;
        Teensy4.0)
            FQBN="teensy:avr:teensy40"
            UPLOAD_TOOL="teensy_loader_cli"
            MCU="teensy40"
            ;;
        Teensy4.1)
            FQBN="teensy:avr:teensy40"
            UPLOAD_TOOL="teensy_loader_cli"
            MCU="teensy40"
            ;;
        *)
            echo "Unsupported microcontroller: $1"
            read -p "Press enter to continue"
            exit 1
            ;;
    esac
}

# Add binaries to system path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$SCRIPT_DIR/bin:$SCRIPT_DIR/bin/teensy_loader_cli:$PATH"

# Find correct hardware config
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")
HOSTNAME=$(hostname)
CONFIG_PATH=$(find "$PROJECT_ROOT/printer_server/hardware_configuration" -type f -name "$HOSTNAME.json")

# Check if --auto is enabled
AUTO_FLASH="false"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --auto)
            AUTO_FLASH="true"
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# Check for required tools
if ! command -v arduino-cli &> /dev/null; then
    echo "arduino-cli not found. Please install it and try again."
    read -p "Press enter to continue"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo "jq not found. Please install it and try again."
    read -p "Press enter to continue"
    exit 1
fi

if ! command -v avrdude &> /dev/null || ! command -v teensy_loader_cli &> /dev/null; then
    echo "Required upload tools (avrdude or teensy_loader_cli) not found. Please install them and try again."
    read -p "Press enter to continue"
    exit 1
fi

# Load the JSON configuration
if [[ ! -f $CONFIG_PATH ]]; then
    echo "Configuration file not found: $CONFIG_PATH"
    read -p "Press enter to continue"
    exit 1
fi

# Extract valid keys
echo "Checking hardware configurations..."
VALID_KEYS=($(jq -r '
    to_entries[] |
    select(.value | type == "object" and has("vendor_id") and has("product_id") and has("serial_number") and has("firmware_path") and has("microcontroller")) |
    .key
' $CONFIG_PATH))

if [[ ${#VALID_KEYS[@]} -eq 0 ]]; then
    echo "No valid hardware configurations found in $CONFIG_PATH."
    read -p "Press enter to continue"
    exit 1
fi

# Display valid keys
echo "Found the following hardware configurations:"
for i in "${!VALID_KEYS[@]}"; do
    echo "[$i] ${VALID_KEYS[$i]}"
done


if [[ "$AUTO_FLASH" == "true" ]]; then
    SELECTED_KEYS=($(seq 0 $((${#VALID_KEYS[@]} - 1))))
else
    # Manual selection logic
    read -p "Enter the numbers corresponding to the hardware to upload firmware to (comma-separated): " SELECTION
    IFS=',' read -r -a SELECTED_KEYS <<< "$SELECTION"
fi

# ... Other functions (get_board_settings, etc.) remain unchanged

for index in "${SELECTED_KEYS[@]}"; do
    if [[ $index =~ ^[0-9]+$ ]] && [[ $index -ge 0 ]] && [[ $index -lt ${#VALID_KEYS[@]} ]]; then
        KEY="${VALID_KEYS[$index]}"
        HARDWARE=$(jq -r --arg key "$KEY" '.[$key]' $CONFIG_PATH)
        
        # Extract data
        VENDOR_ID=$(echo "$HARDWARE" | jq -r '.vendor_id')
        PRODUCT_ID=$(echo "$HARDWARE" | jq -r '.product_id')
        SERIAL_NUMBER=$(echo "$HARDWARE" | jq -r '.serial_number')
        FIRMWARE_PATH=$(echo "$HARDWARE" | jq -r '.firmware_path')
        FIRMWARE_PATH="$PROJECT_ROOT/printer_server/drivers/$KEY/firmware/$FIRMWARE_PATH"
        MICROCONTROLLER=$(echo "$HARDWARE" | jq -r '.microcontroller')

        echo "Processing $KEY with firmware: $FIRMWARE_PATH on $MICROCONTROLLER..."

        # Get board settings
        get_board_settings $MICROCONTROLLER

        # Locate firmware directory
        FIRMWARE_DIR=$(dirname "$FIRMWARE_PATH")
        if [[ ! -d "$FIRMWARE_DIR" ]]; then
            echo "Firmware directory not found: $FIRMWARE_DIR"
            continue
        fi

        # Compile the firmware
        echo "Compiling ${FIRMWARE_PATH}..."
        LIBRARIES_DIR="${FIRMWARE_DIR}/libraries"
        OUTPUT_DIR="${FIRMWARE_DIR}/build"
        arduino-cli compile --fqbn ${FQBN} --libraries ${LIBRARIES_DIR} --output-dir "${OUTPUT_DIR}" ${FIRMWARE_DIR}
        if [[ $? -ne 0 ]]; then
            echo "Compilation failed for ${FIRMWARE_PATH}."
            continue
        fi

        # Locate the compiled firmware
        HEX_FILE="${OUTPUT_DIR}/$(basename ${FIRMWARE_PATH%.*}).ino.hex"
        if [[ ! -f "${HEX_FILE}" ]]; then
            echo "Compiled firmware not found: ${HEX_FILE}"
            continue
        fi

        # Identify the serial port
        echo "Identifying the connected device..."
        DEVICE=$(python3 - <<EOF
import serial.tools.list_ports

ports = serial.tools.list_ports.comports()
for port in ports:
    # print(port.vid)
    # print(port.pid)
    # print(port.serial_number)
    # print(port.manufacturer)
    # print(port.product)
    # print(port.device)
    if port.vid == ${VENDOR_ID} and port.pid == ${PRODUCT_ID}:
        if "${SERIAL_NUMBER}" is None or "${SERIAL_NUMBER}".upper() in port.serial_number:
            print(port.device)
            break
EOF
)

        echo $DEVICE

        if [[ -z "$DEVICE" ]]; then
            echo "Device with VID:PID ${VENDOR_ID}:${PRODUCT_ID} and serial ${SERIAL_NUMBER} not found."
            continue
        fi

        echo "Device found: $DEVICE"

        # Flash the firmware
        echo "Flashing firmware to ${DEVICE}..."
        if [[ "$UPLOAD_TOOL" == "avrdude" ]]; then
            avrdude -v -p ${MCU} -c arduino -P ${DEVICE} -b ${UPLOAD_SPEED} -D -U flash:w:${HEX_FILE}:i
        elif [[ "$UPLOAD_TOOL" == "teensy_loader_cli" ]]; then
            teensy_loader_cli -v --mcu=${MCU} -w ${HEX_FILE}
        else
            echo "Unknown upload tool: ${UPLOAD_TOOL}"
            continue
        fi

        if [[ $? -eq 0 ]]; then
            echo "Firmware flashed successfully to ${KEY}!"
        else
            echo "Failed to flash firmware to ${KEY}."
        fi
    else
        echo "Invalid selection: $index"
    fi
done
read -p "Press enter to continue"