#!/usr/bin/env python3

from algorithms.qlearning import QLearning
from algorithms.qlearning import run_gym_q_learning_single_agent
from algorithms.qlearning import run_gym_q_learning_multi_agent

from algorithms.dqn import DQN
from algorithms.dqn import run_gym_dqn_single_agent
from algorithms.dqn import run_gym_dqn_multi_agent

from algorithms.policy_grad import PolicyGradient
from algorithms.policy_grad import run_gym_policy_grad_single_agent
from algorithms.policy_grad import run_gym_policy_grad_multi_agent

from algorithms.actor_critic import ActorCritic
from algorithms.actor_critic import run_gym_actor_critic_single_agent
from algorithms.actor_critic import run_gym_actor_critic_multi_agent

from algorithms.ddpg import DDPG
from algorithms.ddpg import run_gym_ddpg_single_agent

from algorithms.ma_actor_critic import MAActorCritic
from algorithms.ma_actor_critic import run_gym_ma_actor_critic_multi_agent

from algorithms.ddrqn import DDRQN
from algorithms.ddrqn import run_gym_ddrqn_multi_agent
