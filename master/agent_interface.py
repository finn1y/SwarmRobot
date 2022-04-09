#!/usr/bin/env python3

#-----------------------------------------------------------------------------------------------    
# Imports
#-----------------------------------------------------------------------------------------------

import asyncio
import logging
import numpy as np

from asyncio_mqtt import Client

from algorithms import *

#-----------------------------------------------------------------------------------------------    
# Classes
#-----------------------------------------------------------------------------------------------

class AgentInterface():
    """
        class to contain agent variables including: RL algorithm object, index, message queue 
        and a status flag for master status and agent coroutines
    """
    def __init__(self, client: Client, n: int):
        """
            init for agent class

            client is the MQTT client used to connect to the broker

            n is the index number of this agent
        """
        self.client = client
        self.queue = asyncio.Queue()
        self.status_flag = asyncio.Event()
        self._n = n

        self.algorithm = QLearning(25, 4)

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

    async def run(self):
        """
            coroutine to run the primary functions of this agent:
                1. receive and process init obvservation
                2. Loop forever:
                    3. calculate action and publish it
                    4. receive and process next_observation, reward and done
                    5. train algorithm with observation, next_observation, reward and done
                    6. next_observation become observation for next iteration
        """
        all_rewards = []
        low = np.array([0, 0])
        high = np.array([4, 4])

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
            done = False
            total_reward = 0
    
            for t in range(10000):
                state = self.algorithm.index_obv(obv, low, high)
                action = int(self.algorithm.get_action(state))

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
                    elif topic == f'/agents/{self.n}/done': done = True if payload == "True" else False 

                next_state = self.algorithm.index_obv(next_obv, low, high)
                self.algorithm.train(state, action, reward, next_state) 

                logging.debug("Agent %i next_obv = %s", self.n, next_obv)
                logging.debug("Agent %i reward = %.4f", self.n, reward)
                logging.debug("Agent %i done = %s", self.n, done)
                
                obv = next_obv
                total_reward += reward

                if done:
                    logging.info(f'Agent {self.n}, completed episode {e} with total reward: {total_reward}')
                    all_rewards.append(total_reward)
                    break

                if t >= 9999:
                    logging.info(f'Agent {self.n} timed out episode {e} with total reward: {total_reward}')
                    all_rewards.append(total_reward)
                    break

            self.algorithm.update_parameters(e)

        self.save_data("saved_data/qlearning", {"reward": all_rewards})

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


