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
#from algorithms import *

#-----------------------------------------------------------------------------------------------------------
# Functions
#-----------------------------------------------------------------------------------------------------------

def get_args(algoritms):
    """
        function to get the command line arguments

        algorithms is a list of all possible algorithms

        returns a namespace of arguments
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("Algorithm", type=str, choices=algorithms, help="RL Algorithm to train agent with")
    parser.add_argument("-e", "--episodes", type=int, default=None, help="Number of episodes")
    parser.add_argument("-t", "--time-steps", type=int, default=10000, help="Number of time steps per episode")
    parser.add_argument("-b", "--batch-size", type=int, default=32, help="Number of batches sampled from replay memory during training")
    parser.add_argument("-m", "--model-path", default=None, help="Path to the saved model to continue training")
    parser.add_argument("-s", "--hidden-size", type=int, default=128, help="Number of neurons in the hidden layer of neural nets")
    parser.add_argument("-p", "--plot", action="store_true", help="Flag to plot data after completion")
    parser.add_argument("-d", "--directory", type=str, default=None, help="Save the results from the training to the specified directory")
    parser.add_argument("-g", "--gamma", type=float, default=0.99, help="Discount factor to multiply by future expected rewards in the algorithm. Should be greater than 0 and less than 1")
    parser.add_argument("--epsilon-max", type=float, default=1.0, help="Epsilon max is the intial value of epsilon for epsilon-greedy policy. Should be greater than 0 and less than or equal to 1")
    parser.add_argument("--epsilon-min", type=float, default=0.01, help="Epsilon min is the final value of epsilon for epsilon-greedy policy which is decayed to over training from epsilon max. Should be greater than 0 and less then epsilon max")
    parser.add_argument("-l", "--learning-rate", type=float, default=0.0001, help="Learning rate of the algorithm. Should be greater than 0 and less than 1")
    parser.add_argument("--learning-rate-decay", type=float, default=0.95, help="Learning rate decay the base used for exponential decay of the learning rate during training if set to 1 will have no decay. Should be greater than 0 and less than 1")

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
    logging.info("Publishing %s to %s", msg, topic)
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
        logging.info("%s received from topic %s", payload, topic)
        q_item = f'{topic}:{payload}'
        await queue.put(q_item)

async def process_status(msgs, status_flag):
    """
        coroutine to process incoming status messages and set appropriate flag

        msgs is an async constructor of messages

        n the index for the agent

        statu_flag is a flag for agent n's status
    """
    async for msg in msgs:
        status = msg.payload.decode()
        await asyncio.sleep(3)

        if status:
            status_flag.set()
        elif not status:
            status_flag.clear()

async def n_agents_manager(stack, tasks, client, msgs):
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
    status_flags = set()

    async for msg in msgs:
        payload = int(msg.payload.decode())
        
        if payload == 1:
            #post to topic preventing agent from starting until coroutine is initialised
            await post_to_topic(client, f'/agents/{agents_i}/start', 0, retain=True)
            #add agent
            await post_to_topic(client, "/agents/index", agents_i)

            #init agent n's queue and status flag adding each to their respective set 
            queue = asyncio.Queue()
            queues.add(queue)
            status_flag = asyncio.Event()
            status_flags.add(status_flag)

            receive_topics = (f'/agents/{agents_i}/obv', f'/agents/{agents_i}/reward', f'/agents/{agents_i}/done')
            #start tasks to process messages received from agent n
            for topic in receive_topics:
                manager = client.filtered_messages((topic))
                msgs = await stack.enter_async_context(manager)
                task = asyncio.create_task(process_messages(msgs, queue))
                tasks.add(task)

            manager = client.filtered_messages((f'/agents/{agents_i}/status'))
            msgs = await stack.enter_async_context(manager)
            task = asyncio.create_task(process_status(msgs, status_flag))
            tasks.add(task)

            #subscribe to agent n's topics
            await client.subscribe(f'/agents/{agents_i}/#')

            task = asyncio.create_task(agent_run(client, agents_i, queue, status_flag))
            tasks.add(task)

            agents_i += 1
            logging.info("Agent added, number of agents = %i", agents_i)

        elif payload == -1:
            #remove agent
            agents_i -= 1
            logging.info("Agent removed, number of agents = %i", agents_i)

async def agent_run(client, n, queue, status_flag):
    """
        coroutine to run the rl algorithm for agent n

        client is the mqtt client object

        n is the index of the agent

        queue is the Queue for messages received from agent n

        status_flag is a flag for agent n's status
    """
    logging.info("Agent %i initialised", n)

#        algorithm = QLearning([[100], [4, 4]])

    #agent n coroutine initialised agent can start 
    await post_to_topic(client, f'/agents/{n}/start', 1, retain=True)

    #wait for agent n status to be true    
    await status_flag.wait()

    #get init observation from agent
    obv = await queue.get()
    obv = obv.split(':')[1]
    print(f'agent {n} obv = {obv}')

    while True:
        action = 3 #algorithm.get_action(obv)

        #wait for agent n status to be true    
        await status_flag.wait()

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

#        algorithm.train(obv, action, reward, next_obv) 
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

        client = Client(MQTT_HOST, port=8883, username=MQTT_USERNAME, password=MQTT_PASSWORD, tls_context=ssl.create_default_context(), will=Will("/master/status", 0, retain=True))
        await stack.enter_async_context(client)

        #post to init topics
        task = asyncio.create_task(post_to_topic(client, "/master/status", 1, retain=True))
        tasks.add(task)
    
        #start logger for adding/removing agents from system
        manager = client.filtered_messages(("/agents/add"))
        msgs = await stack.enter_async_context(manager)
        task = asyncio.create_task(n_agents_manager(stack, tasks, client, msgs))
        tasks.add(task)

        #subscribe to topic for adding/removing agents from system
        await client.subscribe("/agents/add")

        await asyncio.gather(*tasks)

#-----------------------------------------------------------------------------------------------------------
# main
#-----------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

    #list of all possible algorithms
    algorithms = ["qlearning", "dqn", "drqn", "policy_gradient", "actor_critic", "ddpg", "ddrqn", "ma_actor_critic"]

    global args 
    args = get_args(algorithms)

    asyncio.run(main())

    sys.exit(0)
