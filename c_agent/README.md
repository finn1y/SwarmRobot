# C Agent

This directory contains a project designed for use with the [esp-idf (IoT Development Framework)](https://github.com/espressif/esp-idf) toolchain, found in [[1]](#1)
The board used to develop and test this software is the [ESP32-DevKitM-1](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/hw-reference/esp32/user-guide-devkitm-1.html), other boards and microcontrollers can be used but have not be tested

## Installation

To use this code on an esp based board the esp-idf toolchain needs to be installed, a step-by-step guide for windows, linux or macOS can be found [here](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/index.html#get-started-step-by-step).
TO install on linux:

1. Install prerequisites
```
sudo apt-get install git wget flex bison gperf python3 python3-pip python3-setuptools cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
```
2. Clone esp-idf repo
```
mkdir -p ~/esp
cd ~/esp
git clone --recursive https://github.com/espressif/esp-idf.git
```
3. Set up the tools
```
cd ~/esp/esp-idf
./install.sh
```
4. Set up environment
```
. ~/esp/esp-idf/export.sh
```

The project can then be configured and flashed onto your board:

1. Configure project
```
cd <path-to-c_agent>/c_agent
idf.py menuconfig
```
2. Build project
```
idf.py build
```
3. Flash projet to the board
```
idf.py -p <port> flash
```
4. Monitor boards output using serial communication software (e.g. esp monitor contained within idf tool)
```
idf.py -p <port> monitor
```

## References

<a id="1">[1]</a>
Multiple authorts, "esp-idf", *GitHub*, 2022. Available: [link](https://github.com/espressif/esp-idf) [Accessed 7 March 2022]
