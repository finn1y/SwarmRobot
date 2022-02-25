#!/usr/bin/env python3

import numpy as np
import tensorflow as tf

class DQN():
    """
        Class to contain the QNetwork and all parameters
    """
    def __init__(self, sizes, gamma=0.99, epsilon_max=1.0, epsilon_min=0.01, lr=0.0001, lr_decay=0.9, lr_decay_steps=10000, mem_size=10000, DRQN=False, saved_path=None):
        """
            function to initialise the class

            sizes is an array of [observations, hidden_size, actions] where observations is an array of 
            [observations_low, observations_high], hidden_size is the number of neurons in the hidden layer 
            and actions is an array of [actions_low, actions_high] in turn low is an array of low bounds for 
            each observation/action and high is an array of high bounds for each observation/action respectively

            gamma is the discount factor of future rewards

            epsilon max is a float which is the maximum exploration rate of the agent

            epsilon min is a float which is the minimum exploration rate of the agent

            lr is the learning rate of the neural network

            lr_decay is a float which is the rate at which the learning rate will decay exponentially

            lr_decay_steps is an int which is the number of time steps to decay the learning rate

            mem_size is the maximum capacity of the expereince replay memory

            DRQN is a bool to use a long short-term memory (LSTM) in place of the first layer of the neural net if true

            saved_path is a string of the path to the saved Q-network if on is being loaded
        """
        self.gamma = gamma
        self.lr = lr
        self.lr_decay = lr_decay
        self.epsilon_max = epsilon_max
        self.epsilon_min = epsilon_min
        self.epsilon = epsilon_max
        self.n_actions = np.shape(sizes[2])[1]
        self.replay_mem = []
        self.mem_size = mem_size
    
        self.q_net = QNet(sizes) #Q-network instantiation to calculate Q-values
        self.lr_decay_fn = tf.keras.optimizers.schedules.ExponentialDecay(self.lr, decay_steps=lr_decay_steps, decay_rate=self.lr_decay)
        self.opt = tf.keras.optimizers.Adam(learning_rate=self.lr_decay_fn) #Adam optimiser is...
        self.loss_fn = tf.keras.losses.Huber() #Huber loss is...

        #target network to calculate target Q-values
        #back propagation and gardient calculations are not performed on this network intead it 
        #is updated with the weights from the Q-network at set intervals
        self.target_net = QNet(sizes)
        self.target_net.set_weights(self.q_net.get_weights())

        #load a saved model (neural net) if provided
        if saved_path:
            self.q_net = tf.keras.models.load_model(saved_path, custom_objects={"CustomModel": QNet})
            self.target_net = tf.keras.models.load_model(saved_path, custom_objects={"CustomModel": QNet})

    def get_parameters(self):
        """
            function to get the parameters of the algorithm

            returns a dict with all the algorithm parameters
        """
        return {"gamma": self.gamma, "epsilon_max": self.epsilon_max, "epsilon_min": self.epsilon_min, 
                "lr": self.lr, "lr_decay": self.lr_decay,  "mem_size": self.mem_size}

    def save_model(self, path):
        """
            function to save the tensorflow model (neural net) to a file

            path is a string of the path to the file where the model will be saved
        """
        self.q_net.save(path)

    def get_action(self, obv):
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
            values = self.q_net(np.array([obv]))
            #policy is greedy
            action = np.argmax(values)

        return action

    def update_parameters(self, n_t, n_max):
        """
            function to reduce value of epsilon such that it is epsilon max at n_t = 0 and epsilon min at n_t = n_max

            n_t is the current episode number

            n_max is the maximum number of epsiodes
        """
        rate = max((n_max - (n_t + 1)) / n_max, 0) #rate should not be less than zero
        self.epsilon = rate * (self.epsilon_max - self.epsilon_min) + self.epsilon_min

    def store_step(self, obv, action, reward, next_obv):
        """
            function to store a step's tuple of values

            obv is the observation of the current state

            action is an int of the action taken

            reward is the reward returned when the action is applied to the current state

            next obv is the observation of the next state after action has been applied to the current state
        """
        #appends dictionary of step tuple to replay memory
        self.replay_mem.append({"obv": obv, "action": action, "reward": reward, "next_obv": next_obv})

        #if replay memory is greater than maximum size then remove oldest step
        if len(self.replay_mem) > self.mem_size:
            self.replay_mem.pop(0)

    def train(self, batch_size):
        """
            function to train Q-network using experiences from replay memory

            batch size is the number of experiences to train the Q-network with

            returns the loss of the training as a tensor
        """
        indices = np.random.choice(range(len(self.replay_mem)), size=batch_size)

        #samples of each piece of data from a random step in replay memory
        obv_batch = np.array([self.replay_mem[i]["obv"] for i in indices], dtype=np.float32)
        action_batch = np.array([self.replay_mem[i]["action"] for i in indices], dtype=int)
        reward_batch = np.array([self.replay_mem[i]["reward"] for i in indices], dtype=np.float32)
        next_obv_batch = np.array([self.replay_mem[i]["next_obv"] for i in indices], dtype=np.float32)

        targets = self.target_net(next_obv_batch)
        #calculate expected reward for each sample
        targets = reward_batch + self.gamma * np.max(targets, axis=1)

        #one hot encoding of actions to apply to Q-values
        action_masks = np.eye(self.n_actions)[np.array(action_batch).reshape(-1)]

        with tf.GradientTape() as tape:
            values = self.q_net(obv_batch)
            #calculate Q-values based on action taken for each step
            values = tf.reduce_sum(values * action_masks, axis=1)
            loss = self.loss_fn(targets, values)

        grads = tape.gradient(loss, self.q_net.trainable_variables)
        self.opt.apply_gradients(zip(grads, self.q_net.trainable_variables))
            
        return loss

    def update_target_net(self):
        """
            function to update the weights of the target network
        """
        self.target_net.set_weights(self.q_net.get_weights())

class QNet(tf.keras.Model):
    """
        Class to contain the neural network approximating the Q-value function
    """
    def __init__(self, sizes, DRQN=False):
        """
            function to initialise the class

            sizes is an array of [observations, hidden_size, actions] where observations is an array of 
            [observations_low, observations_high], hidden_size is the number of neurons in the hidden layer 
            and actions is an array of [actions_low, actions_high] in turn low is an array of low bounds for 
            each observation/action and high is an array of high bounds for each observation/action respectively

            DRQN is a bool to use a long short-term memory (LSTM) in place of the first layer of the neural net if true
        """
        super(QNet, self).__init__()
        #DRQN uses a long short-term memory as the first layer of the network
        if DRQN:
            self.hidden1 = tf.keras.layers.LSTM(np.shape(sizes[0])[1])
        else:
            self.hidden1 = tf.keras.layers.Dense(np.shape(sizes[0])[1], activation="relu")

        self.hidden2 = tf.keras.layers.Dense(sizes[1], activation="relu")
        self.q_vals = tf.keras.layers.Dense(np.shape(sizes[2])[1], activation="linear")

    def call(self, obv):
        """
            function to define the forward pass of the neural network this function is called 
            when QNet(inputs) is called or QNet.predict(inputs) is called

            obv is the numpy array or tensor of the inputs values to the neural network

            returns a tensor of the values output by the neural network
        """
        obv = self.hidden1(obv)
        obv = self.hidden2(obv)
        values = self.q_vals(obv)

        return values


