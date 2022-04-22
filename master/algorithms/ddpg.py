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

def run_gym_ddpg_single_agent(env, render: bool=False, episodes: int=100, time_steps: int=10000, hidden_size: int=256, gamma: float=0.99, lr: float=0.001, decay: float=0.9, lr_decay_steps: int=10000, mem_size: int=10000, batch_size: int=32, saved_path: str=None):
    """
        function to run ddpg algorithm on a gym env

        env is the gym env object

        n_agents is the number of agents

        render determines whether to render the env

        episodes is the number of episodes to simulate

        time steps is the maximum number of time steps per episode

        returns obvs, actions, rewards and losses of all agents and time of each epsiode in seconds
    """
    #get env variables
    n_actions = int(np.squeeze(env.action_space.shape)) #number of actions
    n_obvs = np.squeeze(env.observation_space.shape)

    agent = DDPG(n_obvs, n_actions, env.action_space.high, env.action_space.low, hidden_size=hidden_size, gamma=gamma, lr=lr, decay=decay, lr_decay_steps=lr_decay_steps, mem_size=mem_size, batch_size=batch_size, saved_path=saved_path)

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
        obv = env.reset()

        start_time = time.time()
        ep_obvs = []
        ep_actions = []
        total_reward = 0
        done = False

        for t in range(time_steps):
            if render:
                env.render()

            action = agent.get_action(obv)
    
            next_obv, reward, done, _ = env.step(action)
    
            agent.obv_mem.append(obv)
            agent.rewards_mem.append(reward)
            agent.next_obv_mem.append(next_obv)
    
            ep_obvs.append(obv)
            ep_actions.append(action)

            obv = next_obv
            total_reward += reward

            if done:
                logging.info("Episode %u completed, after %u time steps, with total reward = %f", e, t, total_reward)

                ep_time = round((time.time() - start_time), 3)
                all_times.append(ep_time)
                all_obvs.append(ep_obvs)
                all_actions.append(ep_actions)
                all_rewards.append(total_reward)

                if env.unwrapped.spec.id[0:13] == "gym_robot_maze":
                    robot_paths.append(info["robot_path"])

                break

            elif t >= (time_steps - 1):
                logging.info("Episode %u timed out, with total reward = %f", e, total_reward)

                ep_time = round((time.time() - start_time), 3)
                all_times.append(ep_time)
                all_obvs.append(ep_obvs)
                all_actions.append(ep_actions)
                all_rewards.append(total_reward)

                if env.unwrapped.spec.id[0:13] == "gym_robot_maze":
                    robot_paths.append(info["robot_path"])

                break

            if env.unwrapped.spec.id[0:5] == "maze-" and env.is_game_over():
                sys.exit(0)

            if np.size(agent.action_mem) > batch_size:
                loss = agent.train()
                all_losses.append(loss)

                if t % 10 == 0:
                    agent.update_target_net()

    return all_obvs, all_actions, all_rewards, all_losses, robot_paths, all_times

#-----------------------------------------------------------------------------------------------    
# Classes
#-----------------------------------------------------------------------------------------------

class DDPG(RLAlgorithm):
    """
        Class to contain the PolicyNetwork and all parameters
    """
    def __init__(self, n_obvs: int, n_actions: int, action_high: np.ndarray, action_low: np.ndarray, hidden_size: int=256, gamma: float=0.99, lr: float=0.001, decay: float=0.9, lr_decay_steps: int=10000, mem_size: int=10000, batch_size: int=32, saved_path: str=None):
        """
            function to initialise the class

            sizes is an array of [observations, hidden_size, actions] where observations is an array of 
            [observations_low, observations_high], hidden_size is the number of neurons in the hidden layer 
            and actions is an array of [actions_low, actions_high] in turn low is an array of low bounds for 
            each observation/action and high is an array of high bounds for each observation/action respectively

            gamma is the discount factor of future rewards

            lr is the learning rate of the neural network

            lr_decay is a float which is the rate at which the learning rate will decay exponentially

            lr_decay_steps is an int which is the number of time steps to decay the learning rate

            saved_path is a string of the path to the saved Actor-Critic network if one is being loaded
        """
        self.gamma = gamma
        self.lr = lr
        self.decay = decay
        self.n_actions = n_actions
        #Ornstein-Uhlenbeck noise generator
        self.noise = OrnsteinUhlenbeckNoise(mean=np.zeros(1), std_deviation=0.2 * np.ones(1))

        self._batch_size = batch_size
        self._mem_size = mem_size
        self._obv_mem = []
        self._action_mem = []
        self._rewards_mem = []
        self._next_obv_mem = []

        k_init = tf.random_uniform_initializer(minval=-0.003, maxval=0.003)

        #init actor network
        actor_inputs = tf.keras.layers.Input(shape=(n_obvs,))
        actor_common = tf.keras.layers.Dense(hidden_size, activation="relu")(actor_inputs)
        actor = tf.keras.layers.Dense(n_actions, activation="tanh", kernel_initializer=k_init)(actor_common)
        #multiply by action space limit to keep within bounds
        actor *= (action_high - action_low)
        self.actor_net = tf.keras.Model(inputs=actor_inputs, outputs=actor)

        #init critic network
        obv_input = tf.keras.layers.Input(shape=(n_obvs,))
        critic_common1 = tf.keras.layers.Dense(32, activation="relu")(obv_input)
        action_input = tf.keras.layers.Input(shape=(n_actions,))
        critic_common2 = tf.keras.layers.Dense(32, activation="relu")(action_input)
        concat = tf.keras.layers.Concatenate()([critic_common1, critic_common2])
        out = tf.keras.layers.Dense(hidden_size, activation="relu")(concat)
        critic = tf.keras.layers.Dense(1)(out)
        self.critic_net = tf.keras.Model(inputs=[obv_input, action_input], outputs=critic)

        self.lr_decay_fn = tf.keras.optimizers.schedules.ExponentialDecay(self.lr, decay_steps=lr_decay_steps, decay_rate=self.decay)
        self.actor_opt = tf.keras.optimizers.Adam(learning_rate=self.lr_decay_fn)
        self.critic_opt = tf.keras.optimizers.Adam(learning_rate=self.lr_decay_fn)

        #init target nets
        self.actor_target = tf.keras.Model(inputs=actor_inputs, outputs=actor)
        self.actor_target.set_weights(self.actor_net.get_weights())
        self.critic_target = tf.keras.Model(inputs=[obv_input, action_input], outputs=critic)
        self.critic_target.set_weights(self.critic_net.get_weights())

        #load a saved model (neural net) if provided
        if saved_path:
            self.actor_net = tf.keras.models.load_model(f'{saved_path}/actor_net')
            self.actor_target = tf.keras.models.load_model(f'{saved_path}/actor_net')

            self.critic_net = tf.keras.models.load_model(f'{saved_path}/critic_net')
            self.critic_target = tf.keras.models.load_model(f'{saved_path}/critic_net')
    
    #-------------------------------------------------------------------------------------------
    # Properties
    #-------------------------------------------------------------------------------------------

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @property
    def mem_size(self) -> int:
        return self._mem_size

    @property
    def obv_mem(self) -> list:
        return self._obv_mem

    @property
    def action_mem(self) -> list:
        return self._action_mem

    @property
    def rewards_mem(self) -> list:
        return self._rewards_mem

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
        self.actor_net.save(f'{path}/actor_net')
        self.critic_net.save(f'{path}/critic_net')

    def get_action(self, obv: np.ndarray) -> float:
        """
            function to get the action based on the current observation using the 
            policy generated by the neural net

            obv is the current observation of the state

            returns the action to take
        """
        action = self.actor_net(np.expand_dims(obv, axis=0)).numpy()[0]            
        #add noise for exploration
        action += self.noise()

        self.action_mem.append(action)

        return action

    def train(self) -> tf.Tensor:
        """
            function to train Policy network using previous episode data from replay memory

            batch size is the number of experiences to train the Q-network with

            returns the loss of the training as a tensor
        """
        indices = np.random.choice(range(np.size(self.action_mem)), size=self.batch_size)

        #samples of each piece of data from a random step in replay memory
        obv_batch = np.array([self.obv_mem[i] for i in indices])
        action_batch = np.array([[self.action_mem[i]] for i in indices], dtype=np.float32)
        reward_batch = np.array([self.rewards_mem[i] for i in indices], dtype=np.float32)
        next_obv_batch = np.array([self.next_obv_mem[i] for i in indices])

        actor_targets = self.actor_target(next_obv_batch)
        critic_targets = self.critic_target([next_obv_batch, actor_targets])
        #calculate expected reward for each sample
        critic_targets = reward_batch + self.gamma * critic_targets

        #backpropagation for critic network
        with tf.GradientTape() as tape:
            values = self.critic_net([obv_batch, action_batch])
            critic_loss = tf.reduce_mean(tf.square(critic_targets - values)) 
        
        critic_grads = tape.gradient(critic_loss, self.critic_net.trainable_variables)
        self.critic_opt.apply_gradients(zip(critic_grads, self.critic_net.trainable_variables))

        #backpropagation for actor network using updated critic network
        with tf.GradientTape() as tape:
            actions = self.actor_net(obv_batch)
            values = self.critic_net([obv_batch, actions])
            actor_loss = -tf.reduce_mean(values)

        actor_grads = tape.gradient(actor_loss, self.actor_net.trainable_variables)
        self.actor_opt.apply_gradients(zip(actor_grads, self.actor_net.trainable_variables))

        if np.size(self.action_mem) > self.mem_size:
            self.action_mem.pop(0)
            self.obv_mem.pop(0)
            self.rewards_mem.pop(0)
            self.next_obv_mem.pop(0)

        return actor_loss + critic_loss

    def update_target_net(self):
        """
            function to update the weights of the target network
        """
        self.actor_target.set_weights(self.actor_net.get_weights())
        self.critic_target.set_weights(self.critic_net.get_weights())

class OrnsteinUhlenbeckNoise():
    """
        Class to generate Ornstein-Uhlenbeck noise
    """
    def __init__(self, mean: np.ndarray, std_deviation: np.ndarray, theta: float=0.15, dt: float=1e-2, x_initial: float=None):
        """
            function to init class

            mean is the mean average of the noise

            std_deviation is the standard deviation of the noise

            theta is a constant parameter

            dt is a constant parameter

            x_initial is the init value of noise, when None initial is 0
        """
        self.theta = theta
        self.mean = mean
        self.std_dev = std_deviation
        self.dt = dt
        self.x_initial = x_initial
        self.reset()

    def __call__(self) -> float:
        """
            function run when object is called
        """
        #formula taken from https://www.wikipedia.org/wiki/Ornstein-Uhlenbeck_process.
        x = (self.x_prev + self.theta * (self.mean - self.x_prev) * self.dt  + self.std_dev * np.sqrt(self.dt) * np.random.normal(size=self.mean.shape))
        #store x into x_prev, makes next noise dependent on current one
        self.x_prev = x

        return x

    def reset(self):
        """
            function to reset noise to init value
        """
        if self.x_initial is not None:
            self.x_prev = self.x_initial
        else:
            self.x_prev = np.zeros_like(self.mean)


