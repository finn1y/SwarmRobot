# Master

This is the master controller for the swarm robots, written in python

### [Master](master.py)

This file includes all the functionality for the master, controlling the number of agents connected to the system and giving each an index on connection.

### [Agent Interface](agent_interface.py)

Agent interface contains the algorithm itself, as well as the code to send MQTT messages to each agent. This is the class which should be moved onto the robot should the user wish for the algorithm to be executed on the robot rather than at the master.
Also contains a Gym environment to map the real robot's position within the maze, this is done to test for the agent completing the maze (i.e. for done variable) - this can be changed to use a component on the real robot and the done variable sent over MQTT, for example using an RFID tag.
