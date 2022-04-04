# Master

This is the master controller for the swarm robots, written in python

## [master.py](master/master.py)

This file includes all the functionality for the master, controlling the number of agents connected to the system and giving each an index on connection. 

## [agent_interface.py](master/agent_interface.py)

Agent interface contains the algorithm itself, as well as the code to send MQTT messages to each agent. This is the class which should be moved onto the robot should the user wish for the algorithm to be executed on the robot rather than at the master.
