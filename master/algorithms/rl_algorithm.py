#!/usr/bin/env python3

from abc import ABC, abstractmethod

class RLAlgorithm(ABC):
    """
        Base class for all rl algorithms

        provides base properties and abstract methods required by all rl algorithms
    """

    #-------------------------------------------------------------------------------------------
    # Properties
    #-------------------------------------------------------------------------------------------

    @property
    def gamma(self) -> float:
        #gamma is the discount factor for calculated future rewards
        return self._gamma

    @gamma.setter
    def gamma(self, val: float):
        if val < 0 or val > 1: 
            raise ValueError("gamma (discount factor) must have a value between 0 and 1 (inclusive).")
        if not isinstance(val, float):
            raise TypeError("gamma (discount factor) must be a float")
        self._gamma = val

    @property
    def lr(self) -> float:
        #lr is the learning rate of the algorithm
        return self._lr

    @lr.setter
    def lr(self, val: float):
        if val < 0 or val > 1:
            raise ValueError("lr (learning rate) must be a float.") 
        if not isinstance(val, float):
            raise TypeError(" lr (learning rate) must have a value between 0 and 1 (inclusive).")
        self._lr = val

    @property
    def decay(self) -> float:
        #decay is the rate of exponential decay for the learning rate (and epsilon if appropriate)
        #if set to 1 then no decay occurs
        return self._decay

    @decay.setter
    def decay(self, val: float):
        if val <= 0 or val > 1:
            raise ValueError("decay (eponential decay rate) must have a value between 0 (exclusive) and 1 (inclusive).")
        if not isinstance(val, float):
            raise TypeError("decay (exponential decay rate) must be a float.")
        self._decay = val

    @property
    def n_actions(self) -> int:
        #n_actions is the number of actions the agent can perform
        return self._n_actions

    @n_actions.setter
    def n_actions(self, val: int):
        if not isinstance(val, int):
            raise TypeError("n_actions (number of actions) must be an integer.")
        self._n_actions = val

    #-------------------------------------------------------------------------------------------
    # Methods
    #-------------------------------------------------------------------------------------------

    @abstractmethod
    def save_model(self, path: str):
        """
            function to save the model (neural net or q-table) to a file

            path is a string of the path to the file where the model will be saved
        """
        raise NotImplementedError("save_model method must be implemented.")

    @abstractmethod
    def get_action(self, obv) -> int:
        """
            function to get the action based on the current observation

            obv is the current observation of the state

            returns the action to take (int for discrete action spaced and float for continuous)
        """
        raise NotImplementedError("get_action method must be implemented.")

    @abstractmethod
    def train(self, obv, action, reward, next_obv) -> float:
        """
            function to train agent by applying the q-value update rule to the q-table

            obv is the observation from the environment

            action is the action taken by the agent

            reward is the reward provided by the environment after taking action in current state

            next_obv is the observation after taking action in the current state
        """
        raise NotImplementedError("train method must be implemented.")

