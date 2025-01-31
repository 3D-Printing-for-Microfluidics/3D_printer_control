sudo apt-get install avrdude libusb-dev jq flex

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd $SCRIPT_DIR

curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh

cd bin/teensy_loader_cli
make
export PATH="$SCRIPT_DIR/bin:$SCRIPT_DIR/bin/teensy_loader_cli:$PATH"
cd ..
sudo cp 00-teensy.rules.txt /etc/udev/rules.d/00-teensy.rules
cd ../..
sudo udevadm control --reload-rules
arduino-cli config add board_manager.additional_urls https://www.pjrc.com/teensy/package_teensy_index.json
arduino-cli core update-index
arduino-cli core install teensy:avr
arduino-cli core install arduino:avr

arduino-cli config dump
arduino-cli core list
arduino-cli board listall