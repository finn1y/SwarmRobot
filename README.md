# Swarm Robot

A simple swarm robot system using [MQTT](https://mqtt.org/) protocol for messaging and [HiveMQ Cloud](https://www.hivemq.com/mqtt-cloud-broker/) as the online broker.
Contains simulated agent written in python and real agent written in C, designd for the [ESP32-DevKitM-1](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/hw-reference/esp32/user-guide-devkitm-1.html) board. 

## Install

1. Clone the repo
```
git clone https://github.com/finn1y/RLTraingingEnv
```
2. Install python dependencies in repo
```
cd SwarmRobot
pip install -r requirements.txt
```
3. Follow instructions to install on [robot](c_agent)
4. Run master on this machine
```
./master.py
```
5. Run robot in physical maze
