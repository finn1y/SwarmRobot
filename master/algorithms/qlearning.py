#!/usr/bin/env python3

#-----------------------------------------------------------------------------------------------    
# Imports
#-----------------------------------------------------------------------------------------------

import sys, os, pickle
import logging
import numpy as np

from algorithms.rl_algorithm import RLAlgorithm

#-----------------------------------------------------------------------------------------------    
# Functions
#-----------------------------------------------------------------------------------------------

def run_gym_q_learning_multi_agent(env, n_agents: int=1, render: bool=False, episodes: int=100, time_steps: int=10000):
    """
        function to run independent q-learning algorithm on a gym env

        env is the gym env object

        n_agents is the number of agents

        render determines whether to render the env

        episodes is the number of episodes to simulate

        time steps is the maximum number of time steps per episode

        returns obvs, actions, rewards and losses of all agents
    """
    if n_agents < 1:
        raise ValueError("Cannot have less than 1 agent")
    elif n_agents < 2:
        logging.error("Running multi-agent function with only 1 agent. Use single agent function for single agent environments")

    #get env variables
    n_actions = env.action_space.n #number of actions
    low = env.observation_space.low #minimum values of observation space
    high = env.observation_space.high #maximum values of observation space
    n_states = np.prod(high - low + 1) #number of discretised states

    agents = [QLearning(n_states, n_actions) for i in range(n_agents)]

    #init arrays to collect data
    all_obvs = []
    all_actions = []
    all_rewards = []

    #robot-maze env can save the path taken by the agents each episode
    robot_paths = []

    #render env if enabled
    if render:
        env.render()

    for e in range(episodes): 
        obvs = env.reset()
        
        states = np.zeros(n_agents, dtype=int)
        next_states = np.zeros(n_agents, dtype=int)

        for i in range(n_agents):
            states[i] = agents[i].index_obv(obvs[i], low, high)

        ep_obvs = []
        ep_actions = []
        total_rewards = np.zeros(n_agents)
        done = False

        for t in range(time_steps):
            if render:
                env.render()

            actions = np.zeros(n_agents, dtype=int)

            for i in range(n_agents):
                actions[i] = agents[i].get_action(states[i])

            next_obvs, rewards, done, info = env.step(actions)

            for i in range(n_agents):
                next_states[i] = agents[i].index_obv(next_obvs[i], low, high)

                agents[i].train(states[i], actions[i], rewards[i], next_states[i])

            ep_obvs.append(actions)
            ep_actions.append(obvs)

            obvs = next_obvs
            states = next_states
            total_rewards += rewards

            if done:
                logging.info("Episode %u completed, after %u time steps, with total reward = %s", e, t, str(total_rewards))

                all_obvs.append(ep_obvs)
                all_actions.append(ep_actions)
                all_rewards.append(total_rewards)

                if env.unwrapped.spec.id[0:13] == "gym_robot_maze":
                    robot_paths.append(info["robot_path"])

                break

            elif t >= (time_steps - 1):
                logging.info("Episode %u timed out, with total reward = %s", e, str(total_rewards))

                all_obvs.append(ep_obvs)
                all_actions.append(ep_actions)
                all_rewards.append(total_rewards)

                if env.unwrapped.spec.id[0:13] == "gym_robot_maze":
                    robot_paths.append(info["robot_path"])

                break

            if env.unwrapped.spec.id[0:5] == "maze-" and env.is_game_over():
                sys.exit(0)

        for i in range(n_agents):
            agents[i].update_parameters(e)

    return all_obvs, all_actions, all_rewards, robot_paths

def run_gym_q_learning_single_agent(env, render: bool=False, episodes: int=100, time_steps: int=10000):
    """
        function to run independent q-learning algorithm on a gym env

        env is the gym env object

        n_agents is the number of agents

        render determines whether to render the env

        episodes is the number of episodes to simulate

        time steps is the maximum number of time steps per episode

        returns obvs, actions, rewards and losses of all agents
    """
    #get env variables
    n_actions = env.action_space.n #number of actions
    low = env.observation_space.low #minimum values of observation space
    high = env.observation_space.high #maximum values of observation space
    n_states = round(np.prod(high - low + 1)) #number of discretised states

    agent = QLearning(n_states, n_actions)

    #init arrays to collect data
    all_obvs = []
    all_actions = []
    all_rewards = []

    #robot-maze env can save the path taken by the agents each episode
    robot_paths = []

    #render env if enabled
    if render:
        env.render()

    for e in range(episodes): 
        obv = env.reset()
        state = agent.index_obv(obv, low, high)

        ep_obvs = []
        ep_actions = []
        total_reward = 0
        done = False

        for t in range(time_steps):
            if render:
                env.render()

            action = agent.get_action(state)

            next_obv, reward, done, _ = env.step(action)
            next_state = agent.index_obv(next_obv, low, high)

            agent.train(state, action, reward, next_state)

            ep_obvs.append(obv)
            ep_actions.append(action)

            obv = next_obv
            state = next_state
            total_reward += reward

            if done:
                logging.info("Episode %u completed, after %u time steps, with total reward = %f", e, t, total_reward)

                all_obvs.append(ep_obvs)
                all_actions.append(ep_actions)
                all_rewards.append(total_reward)

                if env.unwrapped.spec.id[0:13] == "gym_robot_maze":
                    robot_paths.append(info["robot_path"])

                break

            elif t >= (time_steps - 1):
                logging.info("Episode %u timed out, with total reward = %f", e, total_reward)

                all_obvs.append(ep_obvs)
                all_actions.append(ep_actions)
                all_rewards.append(total_reward)

                if env.unwrapped.spec.id[0:13] == "gym_robot_maze":
                    robot_paths.append(info["robot_path"])

                break

            if env.unwrapped.spec.id[0:5] == "maze-" and env.is_game_over():
                sys.exit(0)

        agent.update_parameters(e)

    return all_obvs, all_actions, all_rewards, robot_paths

#-----------------------------------------------------------------------------------------------    
# Classes
#-----------------------------------------------------------------------------------------------

class QLearning(RLAlgorithm):
    """
        Class to contain Q-table and all parameters with methods to update Q-table and get actions
    """
    def __init__(self, n_states: int, n_actions: int, gamma: float=0.99, epsilon_max: float=1.0, epsilon_min: float=0.01, lr: float=0.7, decay: float=0.999, saved_path: str=None):
        """
            function to initalise the QLearning class

            n_states is the number of discrete (discretised if continuous) states in the environment

            n_actions is the number of discrete actions (q learning will only perform with discrete action space)

            gamma is a float which is the discount factor of future rewards

            epsilon max is the maximum exploration rate of the agent

            epsilon min is the minimum exploration rate of the agent

            lr is the learning rate of the agent

            lr_decay is the rate at which the learning rate will decay exponentially

            saved_path 
        """
        self.gamma = gamma
        self.lr = lr
        self.decay = decay
        self.n_actions = n_actions
        self.epsilon = epsilon_max

        self._epsilon_max = epsilon_max 
        self._epsilon_min = epsilon_min
        self._q_table = np.zeros((n_states, self.n_actions))

        #load a saved model (q-table) if provided
        if saved_path:
            if os.path.isfile(saved_path):
                with open(saved_path, "rb") as handle:
                    self._q_table = pickle.load(handle)
            else:
                raise FileNotFoundError

    #-------------------------------------------------------------------------------------------
    # Properties
    #-------------------------------------------------------------------------------------------

    @property
    def epsilon(self) -> float:
        return self._epsilon

    @epsilon.setter
    def epsilon(self, val: float):
        if val < 0 or val > 1: 
            raise ValueError("epsilon (exploration probability) must have a value between 0 and 1 (inclusive).")
        
        if not isinstance(val, float):
            raise TypeError("epsilon (exploration probability) must be a float")

        self._epsilon = val
    
    @property
    def epsilon_max(self) -> float:
        return self._epsilon_max

    @property
    def epsilon_min(self) -> float:
        return self._epsilon_min

    @property
    def q_table(self):
        return self._q_table

    #-------------------------------------------------------------------------------------------
    # Methods
    #-------------------------------------------------------------------------------------------

    def save_model(self, path: str):
        """
            function to save the model (q-table) to a file

            path is a string of the path to the file where the model will be saved
        """
        with open(path, "wb") as handle:
            pickle.dump(self.q_table, handle, protocol=pickle.HIGHEST_PROTOCOL)

    def get_action(self, obv_i: int):
        """
            function to get the action based on the current observation using an epsilon-greedy policy

            obv_i is the current observation of the state indexed for the q_table (done using index_obv function)

            returns the action to take as an int

            Note: index_obv function should be done outside of this class to prevent performance issues
        """
        #take random action with probability epsilon (explore rate)
        if np.random.uniform(0, 1) < self.epsilon:
            action = np.random.choice(self.n_actions)
        else:
            #policy is greedy
            action = np.argmax(self.q_table[obv_i])

        return action

    def update_parameters(self, n_t: int):
        """
            function to reduce value of learning parameters decaying exponentially at the rate of the decay property

            n_t is the current episode number
        """
        self.epsilon *= self.decay ** (n_t + 1)
        self.lr *= self.decay ** (n_t + 1)

    def train(self, obv_i: int, action: int, reward: int, next_obv_i: int):
        """
            function to train agent by applying the q-value update rule to the q-table

            obv_i is the observation from the environment indexed for the q_table (done using index_obv function)

            action is the action taken by the agent

            reward is the reward provided by the environment after taking action in current state

            next_obv_i is the observation after taking action in the current state indexed for the q_table (done using the index_obv function)

            Note: index_obv function should be done outside of this class to prevent performance issues
        """
        #ensure action is an int for indexing q-table
        action = int(action)

        self.q_table[obv_i, action] += self.lr * (reward + (self.gamma * np.max(self.q_table[next_obv_i])) - self.q_table[obv_i, action])

    def index_obv(self, obv: np.ndarray, low: np.ndarray, high: np.ndarray) -> int:
        """
            function to turn the observations from the environment into an index for the q-table (int)
    
            obv is the observation to be indexed

            low is an array of the lowest values for each observation dimension (e.g. for 4 dimensions 
            with the lowest value of each being 0 an array of [0, 0, 0, 0] should be passed to this 
            function. If using openai gym env this array is equivalent to env.observation_space.low)

            high is an array of the highest values for each observation dimension (same as for low, 
            except the highest values should be included. If using openai gym env this array is 
            equivalent to env.observation_space.high)

            returns the index as an int

            Note: this function should not be called inside of the QLearning class for performance
        """
        index = 0

        #loop through observation array inversly
        for i in range((np.size(obv) - 1), -1, -1):
            #scale so that each array element's value is increased exponentially
            scaler = (high[i + 1] + 1 - low[i + 1]) if i != (np.size(obv) - 1) else 1
            index += (obv[i] - low[i]) * scaler

        return int(index)


