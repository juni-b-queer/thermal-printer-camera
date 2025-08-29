#!/usr/bin/env bash
sudo apt-get install python3 python3-picamera2 python3-pygame python3-pillow
sudo pip3 install rpi_ws281x adafruit-circuitpython-neopixel --break-system-packages
sudo python3 -m pip install --force-reinstall adafruit-blinka --break-system-packages
sudo pip3 install python-escpos
