#!/usr/bin/env python3

#python script to simulate an agent connected to master over MQTT

#-----------------------------------------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------------------------------------

import os, sys, subprocess
import argparse
import ssl
import asyncio
import logging

from contextlib import AsyncExitStack, asynccontextmanager
from asyncio_mqtt import Client, Will, MqttError
from dotenv import load_dotenv
from random import randint

#-----------------------------------------------------------------------------------------------------------
# Functions
#-----------------------------------------------------------------------------------------------------------

def get_args():
    """
        function to get the command line arguments

        returns a namespace of arguments
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("--verbose", "-v", action="count", default=0, help="Increase verbosity level")

    return parser.parse_args()

async def post_to_topic(client, topic, msg, retain=False):
    """
        coroutine to publish messages to topics to an mqtt broker connected to by client

        client is the mqtt client object

        topic is an string of topic to be published to

        msgs is the message to be published to the topic

        retain is a bool to determine if the message should be retained in the topic by the broker defaults to False
    """
    logging.debug("Publishing %s to %s", msg, topic)
    await client.publish(topic, msg, qos=1, retain=retain)
    await asyncio.sleep(2)

async def process_messages(msgs, queue):
    """
        coroutine to process incoming messages and put them in a queue

        msgs is an async constructor of messages

        queue is the queue to put the messages in
    """
    async for msg in msgs:
        topic = msg.topic
        payload = msg.payload.decode()
        logging.debug("%s received from topic %s", payload, topic)
        q_item = f'{topic}:{payload}'
        await queue.put(q_item)

async def process_status(msgs, status_flag):
    """
        coroutine to process incoming status messages and set appropriate flag

        msgs is an async constructor of messages

        status_flag is an Event to be set or cleared
    """
    async for msg in msgs:
        status = msg.payload.decode()
        await asyncio.sleep(3)

        if status:
            status_flag.set()
        elif not status:
            status_flag.clear()

async def get_item(desired_topic, queue):
    """
        coroutine to get an item from a queue with a specific topic

        desired topic is a string of the desired topic

        queue is the queue from which to get the item
    """
    topic = None

    #loop until desired topic is found
    while topic != desired_topic:
        q_item = await queue.get()
        topic = q_item.split(':')[0]
        payload = q_item.split(':')[1]

        #if desired topic then return payload
        if topic == desired_topic:
            return payload
        #else return item to queue for later processing
        else:
            q_item = f'{topic}:{payload}'
            await queue.put(q_item)

async def main_loop(stack, tasks, client, msg_q, status_flag):
    """
        coroutine to simulate main function of agent over MQTT:
            1. get an index
            2. publish init obv
            3. get actions
            4. publish obv, reward and done

        stack is the asyncronous stack that runs the app

        tasks is a set of asyncronous tasks being run

        client is the mqtt client object

        msg_q is a queue for this agents received messages
    """
    start_flag = asyncio.Event()

    await post_to_topic(client, ("/agents/add"), (1))

    #get index from queue
    n = int(await get_item("/agents/index", msg_q))
    logging.info("Agent index: %u", n)

    #unsubscribe from index topic when this agent has an index
    await client.unsubscribe("/agents/index")

    #post to agent n status
    await post_to_topic(client, (f'/agents/{n}/status'), (1), retain=True)
    
    manager = client.filtered_messages((f'/agents/{n}/action'))
    msgs = await stack.enter_async_context(manager)
    task = asyncio.create_task(process_messages(msgs, msg_q))
    tasks.add(task)

    manager = client.filtered_messages((f'/agents/{n}/start'))
    msgs = await stack.enter_async_context(manager)
    task = asyncio.create_task(process_status(msgs, start_flag))
    tasks.add(task)

    await client.subscribe(f'/agents/{n}/action')
    await client.subscribe(f'/agents/{n}/start')

    #wait for master to initialise agent
    logging.info("Waiting for start...")
    await start_flag.wait()

    #post initial (dummy) observation
    await post_to_topic(client, (f'/agents/{n}/obv'), ("[0]"))

    while True:
        #get action
        action = int(await get_item(f'/agents/{n}/action', msg_q)) 
        logging.info("Perform action: %u", action)

        #get (dummy) observation and reward
        obv = randint(0, 100)
        reward = randint(-100, 100)

        #post to relevant topics
        agent_topics = (f'/agents/{n}/obv', f'/agents/{n}/reward', f'/agents/{n}/done')
        agent_msgs = [f'[{obv}]', f'{reward}', "False"]

        logging.info("Observation: [%u]", obv)
        logging.info("Reward: %i", reward)
        logging.info("Done: False")

        for topic, msg in zip(agent_topics, agent_msgs):
            await post_to_topic(client, topic, msg)

async def cancel_tasks(tasks):
    """
        coroutine to cancel all tasks and clean up on exit
    """
    for task in tasks:
        if task.done():
            continue
        
        try:
            task.cancel()
            await task
        except asyncio.CancelledError:
            pass

async def main():
    """
        main coroutine
    """
    #MQTT credentials stored in .env file
    load_dotenv()
    MQTT_HOST = os.getenv("MQTT_HOST")
    MQTT_USERNAME = os.getenv("MQTT_USERNAME")
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

    async with AsyncExitStack() as stack:
        msg_q = asyncio.Queue()
        status_flag = asyncio.Event()
        tasks = set()
        stack.push_async_callback(cancel_tasks, tasks)

        client = Client(MQTT_HOST, port=8883, username=MQTT_USERNAME, password=MQTT_PASSWORD, tls_context=ssl.create_default_context())
        await stack.enter_async_context(client)
        logging.info("MQTT Connected")

        #set up message handler for index topic
        manager = client.filtered_messages(("/agents/index"))
        msgs = await stack.enter_async_context(manager)
        task = asyncio.create_task(process_messages(msgs, msg_q))
        tasks.add(task)

        await client.subscribe("/agents/index")

        #start main task
        task = asyncio.create_task(main_loop(stack, tasks, client, msg_q, status_flag))
        tasks.add(task)

        await asyncio.gather(*tasks)

#-----------------------------------------------------------------------------------------------------------
# main
#-----------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    #init logging
    logging.basicConfig(format="%(asctime)s.%(msecs)03d: %(levelname)s: %(message)s", datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

    if not hasattr(logging, "VDEBUG") and not hasattr(logging, "vdebug") and not hasattr(logging.getLoggerClass(), "vdebug"):
        #add new logging level "vdebug" to logger if not already added
        def logForLevel(self, message, *args, **kwargs):
            if self.isEnabledFor(logging.DEBUG - 5):
                self._log(logging.DEBUG - 5, message, args, **kwargs)

        def logToRoot(message, *args, **kwargs):
            logging.log(logging.DEBUG - 5, message, *args, **kwargs)

        logging.addLevelName(logging.DEBUG - 5, "VDEBUG")
    
        setattr(logging, "VDEBUG", logging.DEBUG - 5)
        setattr(logging.getLoggerClass(), "vdebug", logForLevel)
        setattr(logging, "vdebug", logToRoot)

    #global arguments so that can be accessed by any coroutine
    args = get_args()

    #set more verbose logging level, default is info (verbose == 0)
    if args.verbose == 1:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose == 2:
        logging.getLogger().setLevel(logging.VDEBUG)
    elif args.verbose > 2:
        logging.warning("Maximum verbosity level is 2; logging level set to verbose debug (verbosity level 2).")
        logging.getLogger().setLevel(logging.VDEBUG)

    asyncio.run(main())

    sys.exit(0)
