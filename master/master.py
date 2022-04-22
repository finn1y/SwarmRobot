#!/usr/bin/env python3

#python script to receive agent observations and rewards through an mqtt client

#-----------------------------------------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------------------------------------

import os, sys, subprocess
import argparse
import ssl
import asyncio
import logging

from dotenv import load_dotenv
from contextlib import AsyncExitStack, asynccontextmanager
from asyncio_mqtt import Client, Will, MqttError
from gym_robot_maze import Maze
from agent_interface import AgentInterface

#-----------------------------------------------------------------------------------------------------------
# Functions
#-----------------------------------------------------------------------------------------------------------

def get_args():
    """
        function to get the command line arguments

        returns a namespace of arguments
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("--simulation", "-s", action="store_true", help="Flag to set if agent is simulated")
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
    #loop through topics and messages
    logging.debug("Publishing %s to %s", msg, topic)
    await client.publish(topic, msg, qos=1, retain=retain)
    await asyncio.sleep(2)

async def n_agents_manager(stack, tasks, client, msgs, done_flag, reset_flag, agents):
    """
        coroutine to manage the number of agents connected to the client

        stack is the asyncronous stack that runs the app

        tasks is a set of asyncronous tasks being run

        client is the mqtt client object

        msgs is an async constructor of messages
    """
    #init agent index to 0
    agents_i = 0

    async for msg in msgs:
        payload = int(msg.payload.decode())
        
        if payload == 1:
            #post to topic preventing agent from starting until coroutine is initialised
            await post_to_topic(client, f'/agents/{agents_i}/start', 0, retain=True)
            #add agent
            await post_to_topic(client, "/agents/index", agents_i)

            #init agent n
            agent = AgentInterface(client, agents_i, "ddrqn", sim=args.simulation)
            agents.append(agent)

            if agents_i == 0:
                agents[agents_i].train_flag.set()
            else:
                agents[agents_i].train_flag.clear()

            receive_topics = (f'/agents/{agents_i}/obv', f'/agents/{agents_i}/reward', f'/agents/{agents_i}/done')
            #start tasks to process messages received from agent n
            for topic in receive_topics:
                manager = client.filtered_messages((topic))
                msgs = await stack.enter_async_context(manager)
                task = asyncio.create_task(agent.process_messages(msgs))
                tasks.add(task)

            manager = client.filtered_messages((f'/agents/{agents_i}/status'))
            msgs = await stack.enter_async_context(manager)
            task = asyncio.create_task(agent.process_status(msgs))
            tasks.add(task)

            #subscribe to agent n's topics
            await client.subscribe(f'/agents/{agents_i}/#')

            task = asyncio.create_task(agent.run(done_flag, reset_flag, agents))
            tasks.add(task)

            agents_i += 1
            logging.info("Agent added, number of agents = %i", agents_i)

        elif payload == -1:
            #remove agent
            agents_i -= 1
            logging.info("Agent removed, number of agents = %i", agents_i)

async def wait_for_reset(done_flag, reset_flag, agents):
    """
        coroutine to pause program while robots are reset in real environment
    """
    while True:
        await done_flag.wait()
        done_flag.clear()
        
        logging.info("Episode done, with rewards = %s reset robots in real env", [agent.total_reward for agent in agents])
        input("Press any key to continue...")
        reset_flag.set()

async def cancel_tasks(tasks):
    """
        coroutine to cancel all tasks and clean upon exit
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
        tasks = set()
        stack.push_async_callback(cancel_tasks, tasks)

        client = Client(MQTT_HOST, port=8883, username=MQTT_USERNAME, password=MQTT_PASSWORD, tls_context=ssl.create_default_context(), will=Will("/master/status", 0, retain=True))
        await stack.enter_async_context(client)

        done_flag = asyncio.Event()
        reset_flag = asyncio.Event()
        agents = []

        #post to init topics
        task = asyncio.create_task(post_to_topic(client, "/master/status", 1, retain=True))
        tasks.add(task)
    
        #start logger for adding/removing agents from system
        manager = client.filtered_messages(("/agents/add"))
        msgs = await stack.enter_async_context(manager)
        task = asyncio.create_task(n_agents_manager(stack, tasks, client, msgs, done_flag, reset_flag, agents))
        tasks.add(task)

        #subscribe to topic for adding/removing agents from system
        await client.subscribe("/agents/add")

        #only require wait for env reset if real env used, i.e. not simulation
        if not args.simulation:
            task = asyncio.create_task(wait_for_reset(done_flag, reset_flag, agents))
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
