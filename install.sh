#!/usr/bin/env bash


MODULE_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"


# check if display present
lsusb | grep -i qinheng || exit 1

# Add udev rule
# Bazzite does not allow easily to add user to dialout group
RULES_FILE='/etc/udev/rules.d/99-usbmonitor.rules'
if [ -f "$RULES_FILE" ]; then
    echo Udev rules exists.
else
    sudo tee "$RULES_FILE" >/dev/null <<'EOF'
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="5722", MODE="0666"
EOF

    sudo udevadm control --reload-rules
    sudo udevadm trigger
    # Verify access changed
    ls -l /dev/ttyACM0
fi


cd "$MODULE_DIR"

python3 -m venv venv
source venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt


# Install and start service
mkdir -p ~/.config/systemd/user

echo "\
[Unit]
Description=Turing Smart Screen Startup
After=graphical-session.target

[Service]
Type=simple
WorkingDirectory=$MODULE_DIR
ExecStart=$MODULE_DIR/venv/bin/python3 $MODULE_DIR/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=default.target" > ~/.config/systemd/user/turing.service

systemctl --user daemon-reload
systemctl --user enable turing.service
systemctl --user start turing.service

systemctl --user status turing.service
