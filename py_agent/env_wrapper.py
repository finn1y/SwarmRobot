#!/usr/bin/env python3

#python script to simulate environment for simulated MQTT agents

#-----------------------------------------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------------------------------------

import os, sys, subprocess
import argparse
import ssl
import asyncio
import logging
import gym
import gym_maze
import numpy as np

from contextlib import AsyncExitStack, asynccontextmanager

from agent import sim_agent

#-----------------------------------------------------------------------------------------------------------
# Functions
#-----------------------------------------------------------------------------------------------------------

def get_args():
    """
        function to get the command line arguments

        returns a namespace of arguments
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("--agents", "-a", type=int, default=1, help="Number of agents to simulate, defaults to 1")
    parser.add_argument("--render", "-r", action="store_true", help="Flag to render the simulated environment")
    parser.add_argument("--verbose", "-v", action="count", default=0, help="Increase verbosity level")

    return parser.parse_args()

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

async def env_loop_multi_agent(env, queues, start_flags, obv_flags, action_flags, reward_flags, done_flags):
    """
        coroutine to run the simulation env

        env is the gym environment to run

        queues is a list of the env queues to send and receive data from agents

        start_flags is a list of flags that are set when the simulation is ready to start

        obv_flags is a list of flags that are set when obv of an agent is in that agent's env queue

        action_flags is a list of flags that are set when action of an agent is in that agent's env queue

        reward_flags is a list of flags that are set when reward of an agent is in that agent's env queue

        done_flags is a list of flags that are set when done of an agent is in that agent's env queue
    """
    #wait for start before starting simulation
    logging.info("Env waiting for start...")
    for start_flag in start_flags:
        await start_flag.wait()
    logging.info("Starting env simulation")

    for e in range(100):
        #render env if option chosen
        if args.render:
            env.render()

        obvs = env.reset()
        done = False
        
        for i in range(args.agents):
            #put obv in env queue
            await queues[i].put(obvs[i])
            #set obv flag to show obv in queue
            obv_flags[i].set()

        total_rewards = np.zeros(args.agents)

        for t in range(10000):
            #render env if option chosen
            if args.render:
                env.render()

            actions = np.zeros(args.agents, dtype=int)
            
            for i in range(args.agents):
                #get action from env queue
                await action_flags[i].wait()
                actions[i] = await queues[i].get()
                action_flags[i].clear()

            #perform action on env
            logging.debug("Perform action: %s", actions)
            obvs, rewards, done, _ = env.step(actions)

            logging.debug("Observation: %s", obvs)
            logging.debug("Reward: %s", rewards)
            logging.debug("Done: %s", done)

            total_rewards += rewards

            for i in range(args.agents):
                #put obv, reward and done in env queue
                await queues[i].put(obvs[i])
                obv_flags[i].set()
                await queues[i].put(rewards[i])
                reward_flags[i].set()
                await queues[i].put(done)
                done_flags[i].set()

            #episode complete if done or reached maximum time steps
            if done:
                logging.info(f'Episode {e} completed with reward: {total_rewards}')
                break

            if t >= 9999:
                logging.info(f'Episode {e} timed out with reward: {total_rewards}')
                break
        
async def env_loop(env, queue, start_flag, obv_flag, action_flag, reward_flag, done_flag):
    """
        coroutine to run the simulation env

        env is the gym environment to run

        queue is the env queue to send and receive data from agents

        start_flag is flag that is set when the simulation is ready to start

        obv_flag is a flag that is set when obv is in env queue

        action_flag is a flag that is set when action is in env queue

        reward_flag is a flag that is set when reward is in env queue

        done_flag is a flag that is set when done is in env queue
    """
    #wait for start before starting simulation
    logging.info("Env waiting for start...")
    await start_flag.wait()
    logging.info("Starting env simulation")

    for e in range(100):
        #render env if option chosen
        if args.render:
            env.render()

        obv = env.reset()
        done = False
        
        #put obv in env queue
        await queue.put(obv)
        #set obv flag to show obv in queue
        obv_flag.set()

        total_reward = 0

        for t in range(10000):
            #render env if option chosen
            if args.render:
                env.render()
            
            #get action from env queue
            await action_flag.wait()
            action = await queue.get()
            action_flag.clear()

            #perform action on env
            logging.debug("Perform action: %u", action)
            obv, reward, done, _ = env.step(action)

            logging.debug("Observation: %s", obv)
            logging.debug("Reward: %i", reward)
            logging.debug("Done: %s", done)

            total_reward += reward

            #put obv, reward and done in env queue
            await queue.put(obv)
            obv_flag.set()
            await queue.put(reward)
            reward_flag.set()
            await queue.put(done)
            done_flag.set()

            #episode complete if done or reached maximum time steps
            if done:
                logging.info(f'Episode {e} completed with reward: {total_reward}')
                break

            if t >= 9999:
                logging.info(f'Episode {e} timed out with reward: {total_reward}')
                break;

async def main():
    #init env
    env = gym.make("maze-sample-5x5-v0", enable_render=args.render, n_robots=args.agents)
    
    async with AsyncExitStack() as stack:
        #init index flag to prevent agents getting same index
        index_flag = asyncio.Event()
        index_flag.set()

        #init queue for data transfer between agent and env
        if args.agents > 1:
            env_q = [asyncio.Queue() for i in range(args.agents)]
        else:
            env_q = asyncio.Queue()

        #init flags for data transfer between agent and env
        if args.agents > 1:
            obv_flag = [asyncio.Event() for i in range(args.agents)]
            action_flag = [asyncio.Event() for i in range(args.agents)]
            reward_flag = [asyncio.Event() for i in range(args.agents)]
            done_flag = [asyncio.Event() for i in range(args.agents)]
        else:
            obv_flag = asyncio.Event()
            action_flag = asyncio.Event()
            reward_flag = asyncio.Event()
            done_flag = asyncio.Event()
        
        tasks = set()
        stack.push_async_callback(cancel_tasks, tasks)

        #init agent
        if args.agents > 1:
            agent = [sim_agent() for i in range(args.agents)]
        else:
            agent = sim_agent()

        #start agent tasks
        if args.agents > 1:
            for i in range(args.agents):
                task = asyncio.create_task(agent[i].run(stack, tasks, index_flag, env_q[i], obv_flag[i], action_flag[i], reward_flag[i], done_flag[i]))
                tasks.add(task)

                #small sleep between starting agent tasks to help prevent agents getting same index
                await asyncio.sleep(3)
            
            #array of start flags of each agent
            start_flag = [a.start_flag for a in agent]

        else:
            task = asyncio.create_task(agent.run(stack, tasks, index_flag, env_q, obv_flag, action_flag, reward_flag, done_flag))
            tasks.add(task)
    
        #start env task
        if args.agents > 1:
            task = asyncio.create_task(env_loop_multi_agent(env, env_q, start_flag, obv_flag, action_flag, reward_flag, done_flag))
            tasks.add(task)
        else:
            task = asyncio.create_task(env_loop(env, env_q, agent.start_flag, obv_flag, action_flag, reward_flag, done_flag))
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
    global args
    args = get_args()

    #check minimum number of agents satisfied
    if args.agents < 1:
        raise ValueError(f'Number of agents must be >= 1.')

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

