#!/usr/bin/env python3

#python script to receive agent observations and rewards through an mqtt client

#-----------------------------------------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------------------------------------

import os, sys, subprocess
import ssl
import asyncio

from dotenv import load_dotenv
from contextlib import AsyncExitStack, asynccontextmanager
from asyncio_mqtt import Client, Will, MqttError
#from algorithms import *

#-----------------------------------------------------------------------------------------------------------
# Functions
#-----------------------------------------------------------------------------------------------------------

async def post_to_topic(client, topic, msg, retain=False):
    """
        coroutine to publish messages to topics to an mqtt broker connected to by client

        client is the mqtt client object

        topic is an string of topic to be published to

        msgs is the message to be published to the topic

        retain is a bool to determine if the message should be retained in the topic by the broker defaults to False
    """
    #loop through topics and messages
    print(f'Publishing {msg} to {topic}')
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
        print(f'{payload} received from topic {topic}')
        q_item = f'{topic}:{payload}'
        await queue.put(q_item)

async def n_agents_log(stack, tasks, client, msgs):
    """
        coroutine to manage the number of agents connected to the client

        stack is the asyncronous stack that runs the app

        tasks is a set of asyncronous tasks being run

        client is the mqtt client object

        msgs is an async constructor of messages
    """
    #init agent index to 0
    agents_i = 0
    queues = set()

    async for msg in msgs:
        payload = int(msg.payload.decode())
        
        if payload == 1:
            #post to topic preventing agent from starting until coroutine is initialised
            await post_to_topic(client, f'/agents/{agents_i}/start', 0, retain=True)
            #add agent
            await post_to_topic(client, "/agents/index", agents_i)

            queue = asyncio.Queue()
            queues.add(queue)

            receive_topics = (f'/agents/{agents_i}/obv', f'/agents/{agents_i}/reward', f'/agents/{agents_i}/done')
            #start tasks to process messages received from agent n
            for topic in receive_topics:
                manager = client.filtered_messages((topic))
                msgs = await stack.enter_async_context(manager)
                task = asyncio.create_task(process_messages(msgs, queue))
                tasks.add(task)

            #subscribe to agent n's topics
            await client.subscribe(f'/agents/{agents_i}/#')

            task = asyncio.create_task(agent_run(client, agents_i, queue))
            tasks.add(task)

            agents_i += 1
            print(f'\nadd agent now n_agents = {agents_i}\n')

        elif payload == -1:
            #remove agent
            agents_i -= 1
            print(f'remove agent now n_agents = {agents_i}')

async def agent_run(client, n, queue):
    """
        coroutine to run the rl algorithm for agent n

        client is the mqtt client object

        n is the index of the agent

        queue is the Queue for messages received from agent n
    """
    print(f'init agent {n}')
#    qlearning = QLearning([[100], [4, 4]])

    #agent n coroutine initialised agent can start 
    await post_to_topic(client, f'/agents/{n}/start', 1, retain=True)

    #get init observation from agent
    obv = await queue.get()
    obv = obv.split(':')[1]
    print(f'agent {n} obv = {obv}')

    while True:
#        action = qlearning.get_action(obv)
        action = 3
        
        #send action to agent
        await post_to_topic(client, f'/agents/{n}/action', action)

        #get observation, reward and done from agent
        for i in range(3):
            q_item = await queue.get()
            topic = q_item.split(':')[0]
            payload = q_item.split(':')[1]

            #each may appear in queue in any order so must be processed into correct variable
            if topic == f'/agents/{n}/obv': next_obv = payload
            elif topic == f'/agents/{n}/reward': reward = payload
            elif topic == f'/agents/{n}/done': done = payload

#        qlearning.train(obv, action, reward, next_obv) 
        print(f'agent {n} next_obv = {next_obv}\nagent {n} reward = {reward}\nagent {n} done = {done}')
        obv = next_obv

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
        tasks = set()
        stack.push_async_callback(cancel_tasks, tasks)

        client = Client(MQTT_HOST, port=8883, username=MQTT_USERNAME, password=MQTT_PASSWORD, tls_context=ssl.create_default_context(), will=Will("/master/status", "0", retain=True))
        await stack.enter_async_context(client)

        #post to init topics
        task = asyncio.create_task(post_to_topic(client, "/master/status", 1, retain=True))
        tasks.add(task)
    
        #start logger for adding/removing agents from system
        n_agents_manager = client.filtered_messages(("/agents/add"))
        n_agents_msgs = await stack.enter_async_context(n_agents_manager)
        task = asyncio.create_task(n_agents_log(stack, tasks, client, n_agents_msgs))
        tasks.add(task)

        #subscribe to topic for adding/removing agents from system
        await client.subscribe("/agents/add")

        await asyncio.gather(*tasks)

#-----------------------------------------------------------------------------------------------------------
# main
#-----------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())

    sys.exit(0)
