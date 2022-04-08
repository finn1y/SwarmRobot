#!/usr/bin/env python3

#python script to simulate an agent connected to master over MQTT

#-----------------------------------------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------------------------------------

import os
import ssl
import asyncio
import logging

from contextlib import AsyncExitStack, asynccontextmanager
from asyncio_mqtt import Client, Will, MqttError
from dotenv import load_dotenv

#-----------------------------------------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------------------------------------

class sim_agent():
    """
        class for simulated agent, contains client and all methods required by MQTT and agent
    """
    def __init__(self):
        """
            function to init simulated agent class
        """
        #MQTT credentials stored in .env file
        load_dotenv()
        MQTT_HOST = os.getenv("MQTT_HOST")
        MQTT_USERNAME = os.getenv("MQTT_USERNAME")
        MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
    
        #init client, message queue and start flag
        self.client = Client(MQTT_HOST, port=8883, username=MQTT_USERNAME, password=MQTT_PASSWORD, tls_context=ssl.create_default_context())
        self.msg_q = asyncio.Queue()
        self.start_flag = asyncio.Event()

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
            await self.msg_q.put(q_item)

    async def process_status(self, msgs):
        """
            coroutine to process incoming status messages and set appropriate flag
    
            msgs is an async constructor of messages
        """
        async for msg in msgs:
            status = msg.payload.decode()
            await asyncio.sleep(3)

            if status:
                self.start_flag.set()
            elif not status:
                self.start_flag.clear()

    async def get_item(self, desired_topic):
        """
            coroutine to get an item from a queue with a specific topic
        
            desired topic is a string of the desired topic
        """
        topic = None

        #loop until desired topic is found
        while topic != desired_topic:
            q_item = await self.msg_q.get()
            topic = q_item.split(':')[0]
            payload = q_item.split(':')[1]
    
            #if desired topic then return payload
            if topic == desired_topic:
                return payload
            #else return item to queue for later processing
            else:
                q_item = f'{topic}:{payload}'
                await self.msg_q.put(q_item)

    async def run(self, stack, tasks, index_flag, env_q, obv_flag, action_flag, reward_flag, done_flag):
        """
            coroutine to simulate main function of agent over MQTT:
                1. get an index
                2. publish init obv
                3. get actions
                4. publish obv, reward and done
    
            stack is the asyncronous stack that runs the app

            tasks is a set of asyncronous tasks being run

            index_flag is a flag that is set when this agent can get an index from the master
            this flag is set by the previous agent such that two agents do not have the same index

            env_q is the queue to send and receive data from the env

            obv_flag is a flag that is set if obv is in env_q

            action_flag is a flag that is set if action is in env_q

            reward_flag is a flag that is set if reward is in env_q

            done_flag is a flag that is set if done is in env_q
        """
        await stack.enter_async_context(self.client)
        logging.info("MQTT Connected")
    
        #set up message handler for index topic
        manager = self.client.filtered_messages(("/agents/index"))
        msgs = await stack.enter_async_context(manager)
        task = asyncio.create_task(self.process_messages(msgs))
        tasks.add(task)
    
        await self.client.subscribe("/agents/index")

        #wait to ensure this agent will get individual index
        await index_flag.wait()

        #clear flag to ensure only this agent gets the next index
        index_flag.clear()
    
        await self.post_to_topic(("/agents/add"), (1))

        #get index from queue
        n = int(await self.get_item("/agents/index"))
        logging.info("Agent index: %u", n)
    
        #unsubscribe from index topic when this agent has an index
        await self.client.unsubscribe("/agents/index")
    
        #post to agent n status
        await self.post_to_topic((f'/agents/{n}/status'), (1), retain=True)
        
        #set index flag as this agent has an index
        index_flag.set()
        
        manager = self.client.filtered_messages((f'/agents/{n}/action'))
        msgs = await stack.enter_async_context(manager)
        task = asyncio.create_task(self.process_messages(msgs))
        tasks.add(task)

        manager = self.client.filtered_messages((f'/agents/{n}/start'))
        msgs = await stack.enter_async_context(manager)
        task = asyncio.create_task(self.process_status(msgs))
        tasks.add(task)

        await self.client.subscribe(f'/agents/{n}/action')
        await self.client.subscribe(f'/agents/{n}/start')
    
        #wait for master to initialise agent
        logging.info("Agent %u waiting for start...", n)
        await self.start_flag.wait()
        logging.info("Starting agent %u simulation", n)

        for e in range(100):
            #wait for obv_flag to be set to show obv in env queue
            await obv_flag.wait()
            #get initial observation
            obv = await env_q.get()
            #clear obv_flag to show obv removed from env queue
            obv_flag.clear()

            done = False
        
            #post initial observation
            await self.post_to_topic((f'/agents/{n}/obv'), (f'{obv}'))
    
            for t in range(10000):
                #get action from mqtt and put into env queue
                action = int(await self.get_item(f'/agents/{n}/action')) 
                await env_q.put(action)
                action_flag.set()
    
                #get obv, reward and done from env queue
                await obv_flag.wait()
                obv = await env_q.get()
                obv_flag.clear()

                await reward_flag.wait()
                reward = await env_q.get()
                reward_flag.clear()

                await done_flag.wait()
                done = await env_q.get()
                done_flag.clear()
    
                #post to relevant topics
                agent_topics = (f'/agents/{n}/obv', f'/agents/{n}/reward', f'/agents/{n}/done')
                agent_msgs = [f'{obv}', f'{reward}', f'{done}']

                for topic, msg in zip(agent_topics, agent_msgs):
                    await self.post_to_topic(topic, msg)
    
                if done:
                    break

                if t >= 9999:
                    break;


