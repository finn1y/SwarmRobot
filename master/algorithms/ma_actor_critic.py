#!/usr/bin/env python3

#-----------------------------------------------------------------------------------------------    
# Imports
#-----------------------------------------------------------------------------------------------

import numpy as np
import tensorflow as tf
import logging
import time

from algorithms.rl_algorithm import RLAlgorithm

#-----------------------------------------------------------------------------------------------    
# Functions
#-----------------------------------------------------------------------------------------------

def run_gym_ma_actor_critic_multi_agent(env, n_agents: int=1, render: bool=False, episodes: int=100, time_steps: int=10000, hidden_size: int=128, gamma: float=0.99, decay: float=0.9, lr: float=0.0001, lr_decay_steps: int=10000, saved_path: str=None):
    """
        function to run multi-agent actor critic algorithm on a gym env

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

    agents = [MAActorCritic(n_obvs, n_actions, hidden_size=hidden_size, gamma=gamma, decay=decay, lr=lr, lr_decay_steps=lr_decay_steps, n_agents=n_agents, master=True, saved_path=saved_path)]
    agents.extend([MAActorCritic(n_obvs, n_actions, hidden_size=hidden_size, gamma=gamma, decay=decay, lr=lr, lr_decay_steps=lr_decay_steps, n_agents=n_agents, saved_path=saved_path) for i in range(n_agents - 1)])

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
                #master stores items in an array ready to be inserted with other agents items during communication
                if agents[i].master:
                    agents[i].obv_mem.append([obvs[i]])
                    agents[i].reward_mem.append([rewards[i]])
                    agents[i].next_obv_mem.append([next_obvs[i]])
                #other agents only store their own items
                else:
                    agents[i].obv_mem.append(obvs[i])
                    agents[i].reward_mem.append(rewards[i])
                    agents[i].next_obv_mem.append(next_obvs[i])

            #communication between agents
            for i in range(1, n_agents - 1):
                agents[0].receive_comm(agents[i].send_comm())

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

                if env.unwrapped.spec.id[0:13] == "gym_robot_maze":
                    robot_paths.append(info["robot_path"])

                break

            if env.unwrapped.spec.id[0:5] == "maze-" and env.is_game_over():
                sys.exit(0)


        #master trains actor and critic network first
        loss = agents[0].train()
        ep_losses.append(loss)
        for i in range(1, n_agents - 1):
            #slaves receive critic network values from master
            agents[i].receive_comm(agents[0].send_comm())
            
            #slaves train their actor networks using master critic value
            loss = agents[i].train()
            ep_losses.append(loss)

        all_losses.append(ep_losses)

    return all_obvs, all_actions, all_rewards, all_losses, robot_paths, all_times

#-----------------------------------------------------------------------------------------------    
# Classes
#-----------------------------------------------------------------------------------------------

class MAActorCritic(RLAlgorithm):
    """
        Class to contain the ACNetwork and all parameters with methods to train network and get actions
    """
    def __init__(self, n_obvs: int, n_actions: int, hidden_size: int=128, gamma: float=0.99, decay: float=0.9, lr: float=0.0001, lr_decay_steps: int=10000, n_agents: int=2, master: bool=False, saved_path: str=None):
        """
            function to initialise the class

            sizes is an array of [observations, hidden_size, actions] where observations is an array of 
            [observations_low, observations_high], hidden_size is the number of neurons in the hidden layer 
            and actions is an array of [actions_low, actions_high] in turn low is an array of low bounds for 
            each observation/action and high is an array of high bounds for each observation/action respectively

            gamma is the discount factor of future rewards

            lr is the learning rate of the neural network

            decay is a float which is the rate at which the learning rate will decay exponentially

            lr_decay_steps is an int which is the number of time steps to decay the learning rate

            n_agents is the number of agents in the environment

            master is a bool to determine if this agent should be a master (contain the global critic net)

            saved_path is a string of the path to the saved Actor-Critic network if one is being loaded
        """
        self.gamma = gamma
        self.lr = lr
        self.decay = decay
        self.n_actions = n_actions

        self._eps = np.finfo(np.float32).eps.item()
        self._n_agents = n_agents
        self._master = master
        self._action_mem = []
        self._obv_mem = []
        self._reward_mem = []
        self._next_obv_mem = []

        #init neural net
        inputs = tf.keras.layers.Input(shape=(n_obvs,))
        common = tf.keras.layers.Dense(hidden_size, activation="relu")(inputs)
        actor = tf.keras.layers.Dense(n_actions, activation="softmax")(common)
        self.actor_net = tf.keras.Model(inputs=inputs, outputs=actor)

        self.lr_decay_fn = tf.keras.optimizers.schedules.ExponentialDecay(self.lr, decay_steps=lr_decay_steps, decay_rate=self.decay)
        self.a_opt = tf.keras.optimizers.Adam(learning_rate=self.lr_decay_fn)

        if self.master:
            #only master contains the global critic net
            critic = tf.keras.layers.Dense(1, activation="linear")(common)
            self.critic_net = tf.keras.Model(inputs=inputs, outputs=critic)

            self.c_opt = tf.keras.optimizers.Adam(learning_rate=self.lr_decay_fn)
            self.loss_fn = tf.keras.losses.Huber()

        #load a saved model (neural net) if provided
        if saved_path:
            self.actor_net = tf.keras.models.load_model(f'{saved_path}/actor')

            if self.master:
                self.critic_net = tf.keras.models.load_model(f'{saved_path}/critic')

    #-------------------------------------------------------------------------------------------
    # Properties
    #-------------------------------------------------------------------------------------------

    @property
    def eps(self) -> float:
        return self._eps

    @property
    def n_agents(self) -> int:
        return self._n_agents

    @property
    def master(self) -> bool:
        return self._master

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

    #-------------------------------------------------------------------------------------------
    # Methods
    #-------------------------------------------------------------------------------------------

    def save_model(self, path: str):
        """
            function to save the tensorflow model (neural net) to a file

            path is a string of the path to the file where the model will be saved
        """
        self.actor_net.save(f'{path}/actor')

        if self.master:
            self.critic_net.save(f'{path}/critic')

    def get_action(self, obv: np.ndarray) -> int:
        """
            function to get the action based on the current observation using the 
            policy generated by the neural net

            obv is the current observation of the state

            returns the action to take
        """
        action_probs = self.actor_net(np.expand_dims(obv, axis=0))
        action = np.random.choice(self.n_actions, p=action_probs.numpy()[0])

        if self.master:
            self.action_mem.append([action])
        else:
            self.action_mem.append(action)

        return action

    def train(self):
        """
            function to train Actor-Critic network using previous episode data from replay memory

            returns the loss of the training as a tensor
        """
        returns = []
        discounted_sum = 0

        #master agent has a different replay memory structure as it must hold data for all agents not only itself
        if self.master:
            #samples of each piece of data of this agent
            obv_batch = np.array([self.obv_mem[i][0] for i in range(np.shape(self.obv_mem)[0])])
            action_batch = np.array([self.action_mem[i][0] for i in range(np.shape(self.action_mem)[0])])

            #samples of obvs and actions of all agents flattened for input to critic array
            all_obv_batches = np.array([np.concatenate(self.obv_mem[i], axis=0) for i in range(np.shape(self.obv_mem)[0])])
            all_action_batches = np.array([self.action_mem[i] for i in range(np.shape(self.action_mem)[0])])

            c_returns = []
            avg_discounted_sum = 0

            #calculate the discounted sum of rewards
            for reward in self.reward_mem[::-1]:
                avg_reward = np.average(reward)
                avg_discounted_sum = avg_reward + self.gamma * avg_discounted_sum
                discounted_sum = reward[0] + self.gamma * discounted_sum
                #iterated inversly therefore insert at beginning of array
                c_returns.insert(0, avg_discounted_sum)
                returns.insert(0, discounted_sum)

            #normalise returns
            c_returns = (returns - np.mean(returns)) / (np.std(returns) + self.eps)
            
            #backpropagation for critic network
            #only the master agent need calculate the update for the critic net as all updates would be the same
            with tf.GradientTape() as tape:
                self.values = self.critic_net(all_obv_batches, all_action_batches)
                critic_loss = self.loss_fn(self.values, returns)

            c_grads = tape.gradient(critic_loss, self.critic_net.trainable_variables)
            self.c_opt.apply_gradients(zip(c_grads, self.critic_net.trainable_variables))

        else:
            #samples of each piece of data of this agent
            obv_batch = np.array([self.obv_mem[i] for i in range(np.shape(self.obv_mem)[0])])
            action_batch = np.array([self.action_mem[i] for i in range(np.shape(self.action_mem)[0])])

            #calculate the discounted sum of rewards
            for reward in self.reward_mem[::-1]:
                discounted_sum = reward + self.gamma * discounted_sum
                #iterated inversly therefore insert at beginning of array
                returns.insert(0, discounted_sum)

        #normalise returns
        returns = (returns - np.mean(returns)) / (np.std(returns) + self.eps)

        #backpropagation for actor network
        with tf.GradientTape() as tape:
            #actor networks should be updated using the updated critic net
            action_probs = self.actor_net(obv_batch)

            actor_loss = 0
            for i in range(np.shape(action_probs)[0]):
                #log probability of the action taken
                action_log_prob = tf.math.log(action_probs[i, action_batch[i]])
                advantage = returns[i] - self.values[i]
                #sum losses for both actor and critic across episode
                actor_loss += -action_log_prob * advantage

        a_grads = tape.gradient(actor_loss, self.actor_net.trainable_variables)
        self.a_opt.apply_gradients(zip(a_grads, self.actor_net.trainable_variables))

        #replay memory only stores a single episode 
        self.obv_mem.clear()
        self.action_mem.clear()
        self.reward_mem.clear()
        self.next_obv_mem.clear()

        return actor_loss

    def send_comm(self):
        """
            function to send a communication to another agent

            returns a tuple (critic_net_weights, latest_replay_mem_entry) where critic_net_weights are 
            the weights of the critic net if the agent is the master and 0 (a placeholder) otherwise and
            latest_replay_mem_entry is a dict of {"obvs", "actions", "rewards"} containing the data from
            the most recent time step
        """
        if self.master:
            #master sends the values output from the global critic net
            data = self.values
        else:
            #slave sends the most recent tuple from the replay memory
            data = {"action": self.action_mem[-1], "obv": self.obv_mem[-1], "reward": self.reward_mem[-1]}

        return data

    def receive_comm(self, data):
        """
            function to receive a communication from another agent

            comm is either values output from the global critic net or a dict of {"obvs", "actions", "rewards"} 
            containing the data from the most recent time step for that agent
        """
        if self.master:
            #master receives a tuple from another agents replay memory
            #append tuple contents to replay mem in appropriate place 
            self.action_mem[-1].append(data["action"])
            self.obv_mem[-1].append(data["obv"])
            self.reward_mem[-1].append(data["reward"])
        else:
            #slave receives the values output from the global critic net
            self.values = data



