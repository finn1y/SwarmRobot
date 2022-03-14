#!/usr/bin/env python3

#-----------------------------------------------------------------------------------------------    
# Imports
#-----------------------------------------------------------------------------------------------

import asyncio
import logging

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
    def __init__(self, algorithm: str, client: Client, n: int):
        """
            init for agent class

            algorithm is a string with the name of the RL algorithm to use

            client is the MQTT client used to connect to the broker

            n is the index number of this agent
        """
        self.client = client
        self._n = n
        self._queue = asyncio.Queue()
        self._status_flag = asyncio.Event()

        #init algorithm given algorithm name
        if algorithm == "qlearning":
            self.algorithm = QLearning(2, 4)
        elif algorithm == "dqn":
            self.algorithm = DQN(2, 4)
        elif algorithm == "drqn":
            self.algorithm = DQN(2, 4, DRQN=True)
        elif algorithm == "policy_gradient":
            self.algorithm = PolicyGradient(2, 4)
        elif algorihtm == "actor_critic":
            self.algorithm = ActorCritic(2, 4)
        elif algorithm == "ddrqn":
            self.algorithm = DDRQN(2, 4)
        elif algorithm == "ma_actor_critic":
            self.algorithm = MAActorCritic(2, 4)

    #-------------------------------------------------------------------------------------------
    # Properties
    #-------------------------------------------------------------------------------------------

    @property
    def n(self) -> int:
        return self._n

    @property
    def queue(self) -> asyncio.Queue
        return self._queue

    @property
    def status_flag(self) -> asyncioEvent
        return self._status_flag

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
        logging.info("Agent %i initialised", self.n)

        #agent n coroutine initialised agent can start 
        await self.post_to_topic(f'/agents/{self.n}/start', 1, retain=True)

        #wait for agent n status to be true    
        await self.status_flag.wait()

        #get init observation from agent
        obv = await self.queue.get()
        obv = obv.split(':')[1]
        print(f'agent {self.n} obv = {obv}')

        while True:
            action = 3 #algorithm.get_action(obv)

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
                if topic == f'/agents/{self.n}/obv': next_obv = payload
                elif topic == f'/agents/{self.n}/reward': reward = payload
                elif topic == f'/agents/{self.n}/done': done = payload

#            algorithm.train(obv, action, reward, next_obv) 
            print(f'agent {self.n} next_obv = {next_obv}\nagent {self.n} reward = {reward}\nagent {self.n} done = {done}')
            obv = next_obv

