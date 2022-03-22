cmake_minimum_required(VERSION 3.5)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(swarm_robot_agent)

#add SSL certificate for connection to MQTT broker as a binary to board
target_add_binary_data(swarm_robot_agent.elf "main/mqtt.pem" TEXT)

