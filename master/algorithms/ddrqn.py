#!/usr/bin/env python3

#-----------------------------------------------------------------------------------------------    
# Imports
#-----------------------------------------------------------------------------------------------

import numpy as np
import tensorflow as tf
import logging
import time

from algorithms.dqn import DQN

#-----------------------------------------------------------------------------------------------    
# Functions
#-----------------------------------------------------------------------------------------------

def run_gym_ddrqn_multi_agent(env, n_agents: int=1, render: bool=False, episodes: int=100, time_steps: int=10000, hidden_size: int=128, gamma: float=0.99, epsilon_max: float=1.0, epsilon_min: float=0.01, lr: float=0.00025, decay: float=0.999, lr_decay_steps: int=10000, saved_path: str=None):
    """
        function to run ddrqn algorithm on a gym env

        env is the gym env object

        n_agents is the number of agents

        render determines whether to render the env

        episodes is the number of episodes to simulate

        time steps is the maximum number of time steps per episode

        returns obvs, actions, rewards and losses of all agents and time of each epsiode in seconds
    """
    if n_agents < 1:
        raise ValueError("Cannot have less than 1 agent.")
    elif n_agents < 2:
        logging.error("Running multi-agent function with only 1 agent. Use single agent function for single agent environments")

    #get env variables
    n_actions = env.action_space.n #number of actions
    n_obvs = np.squeeze(env.observation_space.shape)

    agents = [DDRQN(n_obvs, n_actions, hidden_size=hidden_size, gamma=gamma, epsilon_max=epsilon_max, epsilon_min=epsilon_min, lr=lr, decay=decay, lr_decay_steps=lr_decay_steps, saved_path=saved_path) for i in range(n_agents)]

    #init arrays to collect data
    all_times = []
    all_obvs = []
    all_actions = []
    all_rewards = []
    all_losses = []

    #robot-maze env can save the path taken by the agents each episode
    robot_paths = []

    #render env if enabled
    if render:
        env.render()

    for e in range(episodes): 
        obvs = env.reset()
        
        start_time = time.time()
        ep_obvs = []
        ep_actions = []
        ep_losses = []
        total_rewards = np.zeros(n_agents)
        done = False

        for t in range(time_steps):
            if render:
                env.render()

            actions = np.zeros(n_agents, dtype=int)

            for i in range(n_agents):
                actions[i] = agents[i].get_action(obvs[i])

            next_obvs, rewards, done, _ = env.step(actions)

            for i in range(n_agents):
                loss = agents[i].train(obvs[i], actions[i], rewards[i], next_obvs[i])
                ep_losses.append(loss)

                #each agent sends their updated weights to the next agent for the next update
                j = (i + 1) % (n_agents - 1)
                agents[j].receive_comm(agents[i].send_comm())

            for i in range(n_agents):
                #agent 0 has the most up to date network and should update all other agents networks
                agents[i].receive_comm(agents[0].send_comm())

            ep_obvs.append(actions)
            ep_actions.append(obvs)

            obvs = next_obvs
            total_rewards += rewards

            if done:
                logging.info("Episode %u completed, after %u time steps, with total reward = %s", e, t, str(total_rewards))

                ep_time = round((time.time() - start_time), 3)
                all_times.append(ep_time)
                all_obvs.append(ep_obvs)
                all_actions.append(ep_actions)
                all_rewards.append(total_rewards)
                all_losses.append(ep_losses)

                if env.unwrapped.spec.id[0:13] == "gym_robot_maze":
                    robot_paths.append(info["robot_path"])

                break

            elif t >= (time_steps - 1):
                logging.info("Episode %u timed out, with total reward = %s", e, str(total_rewards))

                ep_time = round((time.time() - start_time), 3)
                all_times.append(ep_time)
                all_obvs.append(ep_obvs)
                all_actions.append(ep_actions)
                all_rewards.append(total_rewards)
                all_losses.append(ep_losses)

                if env.unwrapped.spec.id[0:13] == "gym_robot_maze":
                    robot_paths.append(info["robot_path"])

                break

            if env.unwrapped.spec.id[0:5] == "maze-" and env.is_game_over():
                sys.exit(0)

        for i in range(n_agents):
            agents[i].update_parameters(e)

    return all_obvs, all_actions, all_rewards, all_losses, robot_paths, all_times

#-----------------------------------------------------------------------------------------------    
# Classes
#-----------------------------------------------------------------------------------------------

class DDRQN(DQN):
    """
        Class to contain the QNetwork and all parameters with methods to train network and get actions
    """
    def __init__(self, n_obvs: int, n_actions: int, hidden_size: int=128, gamma: float=0.99, epsilon_max: float=1.0, epsilon_min: float=0.01, lr: float=0.00025, decay: float=0.999, lr_decay_steps: int=10000, saved_path: str=None):
        """
            function to initialise the class

            sizes is an array of [observations, hidden_size, actions] where observations is an array of 
            [observations_low, observations_high], hidden_size is the number of neurons in the hidden layer 
            and actions is an array of [actions_low, actions_high] in turn low is an array of low bounds for 
            each observation/action and high is an array of high bounds for each observation/action respectively

            gamma is the discount factor of future rewards

            epsilon max is the maximum exploration rate of the agent

            epsilon min is the minimum exploration rate of the agent

            lr is the learning rate of the neural network

            decay is the rate at which the learning rate will decay exponentially

            lr_decay_steps is the number of time steps to decay the learning rate

            saved_path is the path to the saved Q-network if on is being loaded
        """
        #provide previous action as an input as well as observation
        n_inputs = n_obvs + 1

        super(DDRQN, self).__init__(n_inputs, n_actions, hidden_size=hidden_size, gamma=gamma, epsilon_max=epsilon_max, epsilon_min=epsilon_min, lr=lr, decay=decay, lr_decay_steps=lr_decay_steps, batch_size=1, DRQN=True, saved_path=saved_path)
        #init agent actions to random action
        self.prev_action = np.random.choice(self.n_actions)

    #-------------------------------------------------------------------------------------------
    # Properties
    #-------------------------------------------------------------------------------------------

    @property
    def prev_action(self) -> int:
        return self._prev_action

    @prev_action.setter
    def prev_action(self, val: int):
        if not isinstance(val, int):
            raise TypeError("Previous action must be an integer.")
        self._prev_action = val

    #-------------------------------------------------------------------------------------------
    # Methods
    #-------------------------------------------------------------------------------------------

    def get_action(self, obv: np.ndarray) -> int:
        """
            function to get the action based on the current observation using an epsilon-greedy policy

            obv is the current observation of the state

            returns the action to take
        """
        #feed previous action to the q-net alongside observations
        obv = np.concatenate((obv, [self.prev_action]), axis=0)

        #take random action with probability epsilon (explore rate)
        if np.random.uniform(0, 1) < self.epsilon:
            action = np.random.choice(self.n_actions)
        else:
            #calculate Q-values using Q-network
            values = self.q_net(np.expand_dims(obv, axis=(0, 1)))
            #policy is greedy
            action = np.argmax(values)

        return action

    def train(self, obv: np.ndarray, action: int, reward: float, next_obv: np.ndarray) -> float: 
        """
            function to train agent by applying gradient descent to the net

            obv is the observation from the environment

            action is the action taken by the agent

            reward is the reward provided by the environment after taking action in current state

            next_obv is the observation after taking action in the current state
        """
        #feed other agent actions to the q-net alongside observations
        obv = np.concatenate((obv, [self.prev_action]), axis=0)
        #previous action is current action for next observation
        next_obv = np.concatenate((next_obv, [action]), axis=0)

        target = self.target_net(np.expand_dims(next_obv, axis=(0, 1)))
        #calculate expected reward
        target = reward + self.gamma * np.max(target)

        with tf.GradientTape() as tape:
            values = self.q_net(np.expand_dims(obv, axis=(0, 1)))
            #calculate Q-values based on action taken for each step
            value = tf.reduce_sum(values[0, action])
            loss = self.loss_fn([target], [value])

        grads = tape.gradient(loss, self.q_net.trainable_variables)
        self.opt.apply_gradients(zip(grads, self.q_net.trainable_variables))

        #add action to memory (must be done after training so previous action can be used in training)
        self.prev_action = int(action)

        return loss

    def send_comm(self) -> tf.Tensor:
        """
            function to send a communication to another agent

            returns an array of the weights of the q-network
        """
        comm = self.q_net.get_weights()

        return comm

    def receive_comm(self, comm: tf.Tensor):
        """
            function to receive a communication from another agent

            comm is an array of the weights of the q-network
        """
        self.q_net.set_weights(comm)


