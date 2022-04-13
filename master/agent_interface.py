#!/usr/bin/env python3

#-----------------------------------------------------------------------------------------------    
# Imports
#-----------------------------------------------------------------------------------------------

import asyncio
import logging
import numpy as np
import gym

from asyncio_mqtt import Client
from gym_robot_maze import Maze

from algorithms import *

#-----------------------------------------------------------------------------------------------    
# Classes
#-----------------------------------------------------------------------------------------------

class AgentInterface():
    """
        class to contain agent variables including: RL algorithm object, index, message queue 
        and a status flag for master status and agent coroutines
    """
    def __init__(self, client: Client, n: int, sim: bool=True):
        """
            init for agent class

            algorithm is a string with the name of the RL algorithm to use

            client is the MQTT client used to connect to the broker

            n is the index number of this agent

            sim is True if the agent is simulated, False is the agent is a real robot
        """
        self.client = client
        self.queue = asyncio.Queue()
        self.status_flag = asyncio.Event()
        self._n = n
        self.sim = sim

        self.batch_size = 32

        self.algorithm = DQN(1, 4, batch_size=self.batch_size)

    #-------------------------------------------------------------------------------------------
    # Properties
    #-------------------------------------------------------------------------------------------

    @property
    def n(self) -> int:
        return self._n

    #-------------------------------------------------------------------------------------------
    # Methods
    #-------------------------------------------------------------------------------------------

    async def post_to_topic(self, topic, msg, retain=False):
        """
            coroutine to publish messages to topics to an mqtt broker connected to by client

            client is the mqtt client object
    
            topic is an string of topic to be published to

            msgs is the message to be published to the topic
    
            retain is a bool to determine if the message should be retained in the topic by the broker defaults to False
        """
        logging.debug("Publishing %s to %s", msg, topic)
        await self.client.publish(topic, msg, qos=1, retain=retain)
        await asyncio.sleep(2)

    async def process_status(self, msgs):
        """
            coroutine to process incoming status messages and set appropriate flag
    
            msgs is an async constructor of messages

        """
        async for msg in msgs:
            status = msg.payload.decode()
            await asyncio.sleep(3)

            if status:
                self.status_flag.set()
            elif not status:
                self.status_flag.clear()

    async def process_messages(self, msgs):
        """
            coroutine to process incoming messages and put them in a queue

            msgs is an async constructor of messages
        """
        async for msg in msgs:
            topic = msg.topic
            payload = msg.payload.decode()
            logging.debug("%s received from topic %s", payload, topic)
            q_item = f'{topic}:{payload}'
            await self.queue.put(q_item)

    async def run(self, done_flag, reset_flag):
        """
            coroutine to run the primary functions of this agent:
                1. receive and process init obvservation
                2. Loop forever:
                    3. calculate action and publish it
                    4. receive and process next_observation, reward and done
                    5. train algorithm with observation, next_observation, reward and done
                    6. next_observation become observation for next iteration
        """
        if not self.sim:
            #if real robot use gym env to track robot position in maze
            env = gym.make("gym_robot_maze:RobotMaze-v1", is_render=False, n_agents=1, load_maze_path="./4x4_maze/")

        all_rewards = []

        logging.info("Agent %i initialised", self.n)

        #agent n coroutine initialised agent can start 
        await self.post_to_topic(f'/agents/{self.n}/start', 1, retain=True)

        #wait for agent n status to be true    
        await self.status_flag.wait()

        #get init observation from agent
        obv = await self.queue.get()
        obv = obv.split(':')[1]
        obv = self.msg_to_array(obv)
        logging.debug("Agent %i obv = %s", self.n, obv)

        for e in range(100):
            if not self.sim:
                env.reset()
    
            done = False
            self.total_reward = 0
    
            for t in range(10000):
                action = int(self.algorithm.get_action(obv))

                if not self.sim:
                    _, _, done, _ = env.step(action) 

                #wait for agent n status to be true    
                await self.status_flag.wait()

                #send action to agent
                await self.post_to_topic(f'/agents/{self.n}/action', action)

                #get observation, reward and done from agent
                for i in range(3):
                    q_item = await self.queue.get()
                    topic = q_item.split(':')[0]
                    payload = q_item.split(':')[1]

                    #each may appear in queue in any order so must be processed into correct variable
                    if topic == f'/agents/{self.n}/obv': next_obv = self.msg_to_array(payload)
                    elif topic == f'/agents/{self.n}/reward': reward = float(payload)
                    elif topic == f'/agents/{self.n}/done' and self.sim: done = True if payload == "True" else False 

                self.algorithm.reward_mem.append(reward)
                self.algorithm.next_obv_mem.append(next_obv)

                logging.debug("Agent %i next_obv = %s", self.n, next_obv)
                logging.debug("Agent %i reward = %.4f", self.n, reward)
                logging.debug("Agent %i done = %s", self.n, done)
                
                obv = next_obv
                self.total_reward += reward

                if done:
                    logging.info(f'Agent {self.n } completed episode {e} with total reward: {total_reward}')
                    all_rewards.append(self.total_reward)
                    
                    #if real robot set flag for real env to be reset
                    if not self.sim:
                        done_flag.set()
                        #wait for user input to show real env is reset
                        await reset_flag.wait()
                        reset_flag.clear()
                    
                    break

                if t >= 9999:
                    logging.info(f'Agent {self.n} timed out episode {e} with total reward: {total_reward}')
                    all_rewards.append(self.total_reward)
                    
                    if not self.sim:
                        self.done_flag.set()
                        await reset_flag.wait()
                        reset_flag.clear()
                
                    break

                if np.size(self.algorithm.action_mem) > self.batch_size and t % 4 == 0:
                    loss = self.algorithm.train() 

                    if t % 20 == 0:
                        self.algorithm.update_target_net()

            self.algorithm.update_parameters(e)

        self.save_data("saved_data/dqn", {"reward": all_rewards})

    def save_data(self, path: str, data: dict):
        """
            function to save data in a pickle file gathered during training in the directory at path
            directory has the following structure:

                -path
                    -data.pkl

            path is the path to the directory to store the data in

            data is the data to be saved
        """
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)

        #make directory if not already exists
        if not os.path.isdir(path):
            os.makedirs(path)

        #save parameters to pickle file
        with open(f'{path}/data.pkl', "wb") as handle:
            pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)

    def msg_to_array(self, msg: str) -> np.ndarray:
        """
            function to convert a str (mqtt message) to an array

            msg is the string to be converted to an array, must be a 1-dimensional array

            returns the array
        """
        msg = msg.replace('[', '')
        msg = msg.replace(']', '')

        array = np.array(msg.split(' '), dtype=float)

        return array


