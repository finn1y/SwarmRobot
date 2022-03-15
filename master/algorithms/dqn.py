#!/usr/bin/env python3

#-----------------------------------------------------------------------------------------------    
# Imports
#-----------------------------------------------------------------------------------------------

import numpy as np
import tensorflow as tf
import logging

from algorithms.rl_algorithm import RLAlgorithm

#-----------------------------------------------------------------------------------------------    
# Functions
#-----------------------------------------------------------------------------------------------

def run_gym_dqn_multi_agent(env, n_agents: int=1, render: bool=False, episodes: int=100, time_steps: int=10000, recurrent: bool=False):
    """
        function to run independent dqn algorithm on a gym env

        env is the gym env object

        n_agents is the number of agents

        render determines whether to render the env

        episodes is the number of episodes to simulate

        time steps is the maximum number of time steps per episode

        returns obvs, actions, rewards and losses of all agents
    """
    if n_agents < 1:
        raise ValueError("Cannot have less than 1 agent.")
    elif n_agents < 2:
        logging.error("Running multi-agent function with only 1 agent. Use single agent function for single agent environments")

    batch_size = 32

    #get env variables
    n_actions = env.action_space.n #number of actions
    n_obvs = np.squeeze(env.observation_space.shape)

    agents = [DQN(n_obvs, n_actions, DRQN=recurrent) for i in range(n_agents)]

    #init arrays to collect data
    all_obvs = []
    all_actions = []
    all_rewards = []
    all_losses = []

    #render env if enabled
    if render:
        env.render()

    for e in range(episodes): 
        obvs = env.reset()
        
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
                agents[i].reward_mem.append(rewards[i])
                agents[i].next_obv_mem.append(next_obvs[i])

            ep_obvs.append(actions)
            ep_actions.append(obvs)

            obvs = next_obvs
            total_rewards += rewards

            if done:
                logging.info("Episode %u completed, after %u time steps, with total reward = %s", e, t, str(total_rewards))

                all_obvs.append(ep_obvs)
                all_actions.append(ep_actions)
                all_rewards.append(total_rewards)
                break

            elif t >= (time_steps - 1):
                logging.info("Episode %u timed out, with total reward = %s", e, str(total_rewards))

                all_obvs.append(ep_obvs)
                all_actions.append(ep_actions)
                all_rewards.append(total_rewards)
                break

            if env.unwrapped.spec.id[0:5] == "maze-" and env.is_game_over():
                sys.exit(0)

            if np.size(agents[0].action_mem) > batch_size and t % 4 == 0:
                losses  = []
                for i in range(n_agents):
                    loss = agents[i].train()
                    losses.append(loss)

                    if t % 20 == 0:
                        agents[i].update_target_net()

                ep_losses.append(losses)
                all_losses.append(ep_losses)

        for i in range(n_agents):
            agents[i].update_parameters(e)

    return all_obvs, all_actions, all_rewards, all_losses

def run_gym_dqn_single_agent(env, render: bool=False, episodes: int=100, time_steps: int=10000, recurrent: bool=False):
    """
        function to run dqn algorithm on a gym env

        env is the gym env object

        n_agents is the number of agents

        render determines whether to render the env

        episodes is the number of episodes to simulate

        time steps is the maximum number of time steps per episode

        returns obvs, actions, rewards and losses of all agents
    """
    batch_size = 32
    
    #get env variables
    n_actions = env.action_space.n #number of actions
    n_obvs = np.squeeze(env.observation_space.shape)

    agent = DQN(n_obvs, n_actions, DRQN=recurrent)

    #init arrays to collect data
    all_obvs = []
    all_actions = []
    all_rewards = []
    all_losses = []

    #render env if enabled
    if render:
        env.render()

    for e in range(episodes): 
        obv = env.reset()

        ep_obvs = []
        ep_actions = []
        total_reward = 0
        done = False

        for t in range(time_steps):
            if render:
                env.render()

            action = agent.get_action(obv)
    
            next_obv, reward, done, _ = env.step(action)
    
            agent.reward_mem.append(reward)
            agent.next_obv_mem.append(next_obv)
    
            ep_obvs.append(obv)
            ep_actions.append(action)

            obv = next_obv
            total_reward += reward

            if done:
                logging.info("Episode %u completed, after %u time steps, with total reward = %f", e, t, total_reward)

                all_obvs.append(ep_obvs)
                all_actions.append(ep_actions)
                all_rewards.append(total_reward)
                break

            elif t >= (time_steps - 1):
                logging.info("Episode %u timed out, with total reward = %f", e, total_reward)

                all_obvs.append(ep_obvs)
                all_actions.append(ep_actions)
                all_rewards.append(total_reward)
                break

            if env.unwrapped.spec.id[0:5] == "maze-" and env.is_game_over():
                sys.exit(0)

            if np.size(agent.action_mem) > batch_size and t % 4 == 0:
                loss = agent.train()
                all_losses.append(loss)

                if t % 20 == 0:
                    agent.update_target_net()

        agent.update_parameters(e)

    return all_obvs, all_actions, all_rewards, all_losses

#-----------------------------------------------------------------------------------------------    
# Classes
#-----------------------------------------------------------------------------------------------

class DQN():
    """
        Class to contain the QNetwork and all parameters with methods to train network and get actions
    """
    def __init__(self, n_obvs: int, n_actions: int, hidden_size: int=128, gamma: float=0.99, epsilon_max: float=1.0, epsilon_min: float=0.01, lr: float=0.00025, decay: float=0.999, lr_decay_steps: int=10000, mem_size: int=10000, batch_size: int=32, DRQN: bool=False, saved_path: str=None):
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

            mem_size is the maximum capacity of the expereince replay memory

            DRQN uses a long short-term memory (LSTM) in place of the first layer of the neural net if true

            saved_path is the path to the saved Q-network if one is being loaded
        """
        self.gamma = gamma
        self.lr = lr
        self.decay = decay
        self.n_actions = n_actions
        self.epsilon = epsilon_max

        self._epsilon_max = epsilon_max
        self._epsilon_min = epsilon_min
        self._mem_size = mem_size
        self._action_mem = []
        self._obv_mem = []
        self._reward_mem = []
        self._next_obv_mem = []
        self._batch_size = batch_size
        self._DRQN = DRQN
        
        #init network
        inputs = tf.keras.layers.Input(shape=(None, n_obvs,))
        #DRQN uses LSTM (long short term memory) in place of input layer
        if self.DRQN:
            common = tf.keras.layers.LSTM(hidden_size)(inputs)
        else:
            common = tf.keras.layers.Dense(hidden_size, activation="relu")(inputs)
        q_vals = tf.keras.layers.Dense(n_actions, activation="linear")(common)
        self.q_net = tf.keras.Model(inputs=inputs, outputs=q_vals)
    
        self.lr_decay_fn = tf.keras.optimizers.schedules.ExponentialDecay(self.lr, decay_steps=lr_decay_steps, decay_rate=self.decay)
        self.opt = tf.keras.optimizers.Adam(learning_rate=self.lr_decay_fn) #Adam optimiser is...
        self.loss_fn = tf.keras.losses.Huber() #Huber loss is...

        #target network to calculate target Q-values
        #back propagation and gardient calculations are not performed on this network intead it 
        #is updated with the weights from the Q-network at set intervals
        self.target_net = tf.keras.Model(inputs=inputs, outputs=q_vals)
        self.target_net.set_weights(self.q_net.get_weights())

        #load a saved model (neural net) if provided
        if saved_path:
            self.q_net = tf.keras.models.load_model(saved_path)#, custom_objects={"CustomModel": QNet})
            self.target_net = tf.keras.models.load_model(saved_path)#, custom_objects={"CustomModel": QNet})

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
    def mem_size(self) -> int:
        return self._mem_size

    @property
    def action_mem(self) -> list:
        return self._action_mem

    @property
    def obv_mem(self) -> list:
        return self._obv_mem

    @property
    def reward_mem(self) -> list:
        return self._reward_mem

    @property
    def next_obv_mem(self) -> list:
        return self._next_obv_mem

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @property
    def DRQN(self) -> bool:
        return self._DRQN

    #-------------------------------------------------------------------------------------------
    # Methods
    #-------------------------------------------------------------------------------------------

    def save_model(self, path: str):
        """
            function to save the tensorflow model (neural net) to a file

            path is a string of the path to the file where the model will be saved
        """
        self.q_net.save(path)

    def get_action(self, obv: np.ndarray) -> int:
        """
            function to get the action based on the current observation using an epsilon-greedy policy

            obv is the current observation of the state

            returns the action to take
        """
        #take random action with probability epsilon (explore rate)
        if np.random.uniform(0, 1) < self.epsilon:
            action = np.random.choice(self.n_actions)
        else:
            #calculate Q-values using Q-network
            values = self.q_net(np.expand_dims(obv, axis=(0, 1)), training=False)
            #policy is greedy
            action = np.argmax(values)

        self.obv_mem.append(obv)
        self.action_mem.append(action)

        return action

    def update_parameters(self, n_t: int):
        """
            function to reduce value of epsilon such that it is epsilon max at n_t = 0 and epsilon min at n_t = n_max

            n_t is the current episode number

            n_max is the maximum number of epsiodes
        """
        self.epsilon *= self.decay ** (n_t + 1)

    def train(self) -> tf.Tensor:
        """
            function to train Q-network using experiences from replay memory

            returns the loss of the training as a tensor
        """
        #recurrent network input has different array shape
        axis = (0, 1) if self.DRQN else 2

        indices = np.random.choice(range(np.size(self.action_mem)), size=self.batch_size)

        #samples of each piece of data from a random step in replay memory
        obv_batch = np.array([self.obv_mem[i] for i in indices])
        action_batch = np.array([self.action_mem[i] for i in indices], dtype=int)
        reward_batch = np.array([self.reward_mem[i] for i in indices], dtype=np.float32)
        next_obv_batch = np.array([self.next_obv_mem[i] for i in indices])

        targets = self.target_net(np.expand_dims(next_obv_batch, axis=0))
        #calculate expected reward for each sample
        targets = reward_batch + self.gamma * np.max(targets, axis=axis)

        #one hot encoding of actions to apply to Q-values
        action_masks = np.eye(self.n_actions)[action_batch.reshape(-1)]

        with tf.GradientTape() as tape:
            values = self.q_net(np.expand_dims(obv_batch, axis=0))
            #calculate Q-values based on action taken for each step
            values = tf.reduce_sum(values * action_masks, axis=axis)
            loss = self.loss_fn(targets, values)

        grads = tape.gradient(loss, self.q_net.trainable_variables)
        self.opt.apply_gradients(zip(grads, self.q_net.trainable_variables))

        #ensure memories stay within mem size limit
        if np.size(self.action_mem) > self.mem_size:
            self.action_mem.pop(0)
            self.obv_mem.pop(0)
            self.reward_mem.pop(0)
            self.next_obv_mem.pop(0)
            
        return loss

    def update_target_net(self):
        """
            function to update the weights of the target network
        """
        self.target_net.set_weights(self.q_net.get_weights())



