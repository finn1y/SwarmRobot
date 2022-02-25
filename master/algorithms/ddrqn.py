#!/usr/bin/env python3

import numpy as np
import tensorflow as tf

from algorithms.dqn import DQN

class DDRQN(DQN):
    """
        Class to contain the QNetwork and all parameters
    """
    def __init__(self, sizes, gamma=0.99, epsilon_max=1.0, epsilon_min=0.01, lr=0.0001, lr_decay=0.9, lr_decay_steps=10000, saved_path=None):
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

            saved_path is a string of the path to the saved Q-network if on is being loaded
        """
        #provide previous action as an input as well as observation
        #calculate the shape of the array to concatenate to observations
        axes = np.size(np.shape(sizes[0])) - 1
        ones_shape = [np.shape(sizes[0])[i] for i in range(axes)]
        ones_shape.append(1)

        #add one to the number of observations for building neural net
        sizes[0] = np.concatenate((sizes[0], np.ones(ones_shape)), axis=axes)

        super(DDRQN, self).__init__(sizes, gamma=gamma, epsilon_max=epsilon_max, epsilon_min=epsilon_min, lr=lr, lr_decay=lr_decay, lr_decay_steps=lr_decay_steps, DRQN=True, saved_path=saved_path)
        #init agent actions to random action
        self.prev_action = np.random.choice(self.n_actions)

    def get_parameters(self):
        """
            function to get the parameters of the algorithm, overwrite function inherited from DQN as not all parameters are relevant to DDRQN

            returns a dict with all the algorithm parameters
        """
        return {"gamma": self.gamma, "epsilon_max": self.epsilon_max, "epsilon_min": self.epsilon_min, 
                "lr": self.lr, "lr_decay": self.lr_decay}

    def get_action(self, obv):
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
            values = self.q_net(np.array([obv]))
            #policy is greedy
            action = np.argmax(values)

        return action

    def store_step(self, obv, action, reward, next_obv):
        """
            replay memory is disabled for DDRQN due to the non-sationary nature of mutli-agent environments
        """
        None

    def train(self, obv, action, reward, next_obv): 
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

        target = self.target_net(np.array([next_obv]))
        #calculate expected reward
        target = reward + self.gamma * np.max(target)

        #one hot encoding of action to apply to Q-values
        action_mask = np.eye(self.n_actions)[np.array(action).reshape(-1)]

        obv = np.array([obv])

        with tf.GradientTape() as tape:
            values = self.q_net(obv)
            #calculate Q-values based on action taken for each step
            value = tf.reduce_sum(values * action_mask)
            loss = self.loss_fn([target], [value])

        grads = tape.gradient(loss, self.q_net.trainable_variables)
        self.opt.apply_gradients(zip(grads, self.q_net.trainable_variables))

        #add action to memory (must be done after training so previous action can be used in training)
        self.prev_action = action

        return loss

    def send_comm(self):
        """
            function to send a communication to another agent

            returns an array of the weights of the q-network
        """
        comm = self.q_net.get_weights()

        return comm

    def receive_comm(self, comm):
        """
            function to receive a communication from another agent

            comm is an array of the weights of the q-network
        """
        self.q_net.set_weights(comm)


