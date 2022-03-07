# Algorithms

Both single agent and multi-agent reinforcement learning algorithms are included
Any single agent algorithm can be used as an independent multi-agent learning algorithm

All algorithms using gradient descent on a neural network use the Adam optimiser, first proposed by Kingma et al in [[1]](#1). This optimiser is implemnted as part of the [tensorflow](https://www.tensorflow.org/overview) library. 

All algorithm implementations also include exploration rate (epsilon) and learning rate (alpha) decay where appropriate;
this can be removed by setting the relevant decay rate to 1.

## [Q-Learning](rl_training_env/algorithms/qlearning.py)

Q-learning is implemented based on the algorithm described by Sutton and Barto in [[2]](#2).

## [Deep Q-Network](rl_training_env/algorithms/dqn.py) (DQN)

Deep Q-network is implemeneted based on the algorithm described by Minh et al in [[3]](#3).
However it does not use CNNs as the environments used in this training are not array based 
(i.e. not an RGB array screen representation) 

## [Deep Recurrent Q-Network](rl_training_env/algorithms/dqn.py) (DRQN)

Deep Recurrent Q-Network is implemented based on the alterations to DQN as suggested by Hausknecht and Stone in [[4]](#4). 
Similarly to DQN CNNs are not used. (Note this algorithm is implemented as DQN with a DRQN flag to change the first neural net layer)

## [Policy Gradient](rl_training_env/algorihms/policy_grad.py) (PG)

Policy Gradient is implemented based on the algorithm suggested by Sutton et al in [[5]](#5) 
and its counterpart in [[6]](#6) by Silver et al.

## [Advantage Actor Critic](rl_training_env/algorithms/actor_critic.py) (A2C)

Advantage Actor Critic is implemented based on one of the actor critic variations suggested by Bhatnagar et al in [[7]](#7).

## [Deep Deterministic Policy Gradient](rl_training_env/algorithms/ddpg.py) (DDPG)

Deep Deterministic Policy Gradient is implemented based on the algorithm as suggested in [[8]](#8) by Lillicrap et al.

## [Multi-Agent Actor Critic](rl_training_env/algorithms/ma_actor_critic.py) (MA Actor Critic)

Multi-Agent Actor Critic is implemented based on a the algorithm described by Lowe et al in [[9]](#9). 
As the multi-agent environments are cooperative there is communication of agent policy so no policy inference is required 
nor are policy ensembles.

## [Distributed Deep Recurrent Q-Network](rl_training_env/algorithms/ddrqn.py) (DDRQN)

Distributed Deep Recurrent Q-Network is implemented based on the changes to Deep Q-Networks suggested by Foerster et al in [[10]](#10) 
for multi-agent environments. Due to the nature of this simulation instead of direct inter-agent weight sharing (i.e. directly tying all network weights) agents share weights via communication each updating the their network parameters in turn and then communicating the updated weights to the next agent until all agents have performed their updates. 

## References

<a id="1">[1]</a> 
D. P. Kingma and J. L. Ba, "Adam: A Method for Stochastic Optimisation", *arXiv:1412.6980 [cs.LG]*, 2015. Available: [link](https://arxiv.org/abs/1412.6980) [Accessed 9 Feb 2022]

<a id="2">[2]</a>
R.S. Sutton and A.G. Barto, *Reinforcement Learning: An Introduction*, 2nd ed. The MIT Press, 2018.

<a id="3">[3]</a>
V. Mnih, K. Kavukcuoglu, D. Silver et al, “Human-level control through deep reinforcement learning”, 
*Nature* **518**, 2015, pp. 529-533. Available: 
[link](https://www.datascienceassn.org/sites/default/files/Human-level%20Control%20Through%20Deep%20Reinforcement%20Learning.pdf) [Accessed 2 Feb 2022]

<a id="4">[4]</a>
M. Hausknecht and P. Stone, “Deep Recurrent Q-Learning for Partially Observable MDPs”, 
*arXiv:1507.06527v4 [cs.LG]*, 2017. Available: [link](https://arxiv.org/abs/1507.06527) [Accessed 2 Feb 2022]

<a id="5">[5]</a>
R.S. Sutton, D.A. McAllester, S.P. Singh, and Y. Mansour, “Policy gradient methods for reinforcement learning with function approximation”, 
*Advances in neural information processing systems* **12**, 1999, pp. 1057–1063.

<a id="6">[6]</a>
D. Silver, G. Lever, N. Heess et al, “Deterministic policy gradient algorithms”, 
*Proceedings of the 31st International Conference on Machine Learning*, 2014, pp. 387–395.

<a id="7">[7]</a>
S. Bhatnagar, R. Sutton, M. Ghavamzadeh and M. Lee, "Natural Actor-Critic Algorithms", 
*Automatica* **45**, 2009, pp. 2471-2482.

<a id="8">[8]</a>
T.P. Lillicrap, J.J. Hunt, A. Pritzel et al, “Continuous Control with Deep Reinforcement Learning”, 
*arXiv:1509.02971v6 [cs.LG]*, 2019. Available: [link](https://arxiv.org/abs/1509.02971) [Accessed 2 Feb 2022]

<a id="9">[9]</a>
R. Lowe, Y. Wu, A. Tamar et al, “Multi-Agent Actor-Critic for Mixed Cooperative-Competitive Environments”, 
*arXiv:1706.02275v4 [cs.LG]*, 2020. Available: [link](https://arxiv.org/abs/1706.02275v4) [Accessed 2 Feb 2022]

<a id="10">[10]</a>
J.N. Foerster, Y.M. Assael, N. de Freitas et al, “Learning to Communicate to Solve Riddles with Deep Distributed Recurrent Q-Networks”, 
*arXiv:1602.02672 [cs.AI]*, 2016. Available: [link](https://arxiv.org/abs/1602.02672) [Accessed 9 Feb 2022]
