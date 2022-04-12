# Dependency Patches

This directory contains patches for dependencies of the RL training environment

## Applying Patches

To apply a patch to a git repository then:

1. copy the patch into the relevant repo
2. move to that repo
3. apply the patch with `git apply <patch_name>.patch`

taking `gym_maze_multi_agent.patch` as an example:

```
cp ./gym_maze_multi_agent.patch <path_to_installed_repo>/gym-maze/
cd <path_to_installed_repo>/gym-maze/
git apply gym_maze_multi_agent.patch
```

Note: if installed using pip in a virtual env then the repo may be located in the virtual env's directory under "src"

To view what the patch changes either by looking in the `.patch` file or by using the `git diff` command after applying the patch.

## Patch files

### [Gym Maze](https://github.com/MattChanTK/gym-maze)

#### [Multi Agent Patch](gym_maze_multi_agent.patch)

1. Converts the gym-maze environment created by "MattChanTK" into a multi-agent environment by taking in arrays of actions, processing actions for each robot and outputting the rewards and states as arrays.
2. Removes maximum number of steps from the environment
3. Fixes minor issue when int passed as action but error raised during processing

#### [Advanced Multi Agent Patch](gym_maze_advanced_multi_agent.patch)

1. Improves upon previous patch by making env check whether it is used as single agent or multi-agent
2. Will have same functionality as previously for multi-agent use
3. For single agent use does not require or output actions, states etc. inside arrays


