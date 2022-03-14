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

def run_gym_policy_grad_multi_agent(env, n_agents: int=1, render: bool=False, episodes: int=100, time_steps: int=10000):
    """
        function to run independent policy gradient algorithm on a gym env

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

    #get env variables
    n_actions = env.action_space.n #number of actions
    n_obvs = np.squeeze(env.observation_space.shape)

    agents = [PolicyGradient(n_obvs, n_actions) for i in range(n_agents)]

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
                agents[i].rewards_mem.append(rewards[i])

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

        for i in range(n_agents):
            loss = agents[i].train()
            ep_losses.append(loss)
            all_losses.append(ep_losses)

    return all_obvs, all_actions, all_rewards, all_losses

def run_gym_policy_grad_single_agent(env, render: bool=False, episodes: int=100, time_steps: int=10000):
    """
        function to run policy gradient algorithm on a gym env

        env is the gym env object

        n_agents is the number of agents

        render determines whether to render the env

        episodes is the number of episodes to simulate

        time steps is the maximum number of time steps per episode

        returns obvs, actions, rewards and losses of all agents
    """
    #get env variables
    n_actions = env.action_space.n #number of actions
    n_obvs = np.squeeze(env.observation_space.shape)

    agent = PolicyGradient(n_obvs, n_actions)

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
    
            agent.rewards_mem.append(reward)
    
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

        loss = agent.train()
        all_losses.append(loss)

    return all_obvs, all_actions, all_rewards, all_losses

#-----------------------------------------------------------------------------------------------    
# Classes
#-----------------------------------------------------------------------------------------------

class PolicyGradient(RLAlgorithm):
    """
        Class to contain the PolicyNetwork and all parameters with methods to train network and get actions
    """
    def __init__(self, n_obvs: int, n_actions: int, hidden_size: int=128, gamma=0.99, lr=0.001, decay=0.999, lr_decay_steps=10000, saved_path=None):
        """
            function to initialise the class

            sizes is an array of [observations, hidden_size, actions] where observations is an array of 
            [observations_low, observations_high], hidden_size is the number of neurons in the hidden layer 
            and actions is an array of [actions_low, actions_high] in turn low is an array of low bounds for 
            each observation/action and high is an array of high bounds for each observation/action respectively

            gamma is the discount factor of future rewards

            lr is the learning rate of the neural network

            decay is the rate at which the learning rate will decay exponentially

            lr_decay_steps is the number of time steps to decay the learning rate

            saved_path is the path to the saved Actor-Critic network if one is being loaded
        """
        self.gamma = gamma
        self.lr = lr
        self.decay = decay
        self.n_actions = n_actions

        self._eps = np.finfo(np.float32).eps.item()

        self._obv_mem = []
        self._action_mem = []
        self._rewards_mem = []

        inputs = tf.keras.layers.Input(shape=(n_obvs,))
        common = tf.keras.layers.Dense(hidden_size, activation="relu")(inputs)
        action = tf.keras.layers.Dense(n_actions, activation="softmax")(common)
        self.policy_net = tf.keras.Model(inputs=inputs, outputs=action)

        self.lr_decay_fn = tf.keras.optimizers.schedules.ExponentialDecay(self.lr, decay_steps=lr_decay_steps, decay_rate=self.decay)
        self.opt = tf.keras.optimizers.Adam(learning_rate=self.lr_decay_fn) #Adam optimiser is...

        inputs = tf.keras.layers.Input(shape=(n_obvs,))
        common = tf.keras.layers.Dense(hidden_size, activation="relu")(inputs)
        action = tf.keras.layers.Dense(n_actions, activation="softmax")(common)
        self.policy_net = tf.keras.Model(inputs=inputs, outputs=action)

        #load a saved model (neural net) if provided
        if saved_path:
            self.policy_net = tf.keras.models.load_model(saved_path, custom_object={"CustomModel": PolicyNet})

    #-------------------------------------------------------------------------------------------
    # Properties
    #-------------------------------------------------------------------------------------------

    @property
    def eps(self) -> float:
        return self._eps

    @property
    def obv_mem(self) -> list:
        return self._obv_mem

    @property
    def action_mem(self) -> list:
        return self._action_mem

    @property
    def rewards_mem(self) -> list:
        return self._rewards_mem

    #-------------------------------------------------------------------------------------------
    # Methods
    #-------------------------------------------------------------------------------------------

    def save_model(self, path: str):
        """
            function to save the tensorflow model (neural net) to a file

            path is a string of the path to the file where the model will be saved
        """
        self.policy_net.save(path)

    def get_action(self, obv: np.ndarray) -> int:
        """
            function to get the action based on the current observation using the 
            policy generated by the neural net

            obv is the current observation of the state

            returns the action to take
        """
        action_probs = self.policy_net(np.expand_dims(obv, axis=0))
        action = np.random.choice(self.n_actions, p=action_probs.numpy()[0])

        self.obv_mem.append(obv)
        self.action_mem.append(action)

        return action

    def train(self) -> float:
        """
            function to train Policy network using previous episode data from replay memory

            returns the loss of the training as a tensor
        """
        returns = []
        discounted_sum = 0

        #calculate the discounted sum of rewards
        for reward in self.rewards_mem[::-1]:
            discounted_sum = reward + self.gamma * discounted_sum
            #iterated inversly therefore insert at beginning of array
            returns.insert(0, discounted_sum)

        #normalise returns
        returns = (returns - np.mean(returns)) / (np.std(returns) + self.eps)

        with tf.GradientTape() as tape:
            loss = 0
            for i in range(np.shape(self.obv_mem)[0]):
                action_probs = self.policy_net(np.expand_dims(self.obv_mem[i], axis=0))
                action_log_prob = tf.math.log(action_probs[0, self.action_mem[i]])
                #sum loss across episode
                loss += -action_log_prob * returns[i]

        grads = tape.gradient(loss, self.policy_net.trainable_variables)
        self.opt.apply_gradients(zip(grads, self.policy_net.trainable_variables))

        #replay memory only stores a single episode 
        self.obv_mem.clear()
        self.action_mem.clear()
        self.rewards_mem.clear()

        return loss


