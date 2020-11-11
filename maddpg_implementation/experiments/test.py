import argparse
import numpy as np
import tensorflow as tf
import time
import pickle
import os
import matplotlib.pyplot as plt
import maddpg_implementation.maddpg.common.tf_util as U
from maddpg_implementation.maddpg.trainer.maddpg import MADDPGAgentTrainer
import tensorflow.contrib.layers as layers

def parse_args():
    parser = argparse.ArgumentParser("Reinforcement Learning experiments for multiagent environments")
    # Environment
    parser.add_argument("--scenario", type=str, default="simple_spread", help="name of the scenario script")
    parser.add_argument("--max-episode-len", type=int, default=25, help="maximum episode length")
    parser.add_argument("--num-episodes", type=int, default=10000, help="number of episodes")
    parser.add_argument("--num-adversaries", type=int, default=0, help="number of adversaries")
    parser.add_argument("--good-policy", type=str, default="maddpg", help="policy for good agents")
    parser.add_argument("--adv-policy", type=str, default="maddpg", help="policy of adversaries")
    # Core training parameters
    parser.add_argument("--lr", type=float, default=1e-2, help="learning rate for Adam optimizer")
    parser.add_argument("--gamma", type=float, default=0.95, help="discount factor")
    parser.add_argument("--batch-size", type=int, default=1024, help="number of episodes to optimize at the same time")
    parser.add_argument("--num-units", type=int, default=64, help="number of units in the mlp")
    # Checkpointing
    parser.add_argument("--exp-name", type=str, default="coop_nav", help="name of the experiment")
    parser.add_argument("--save-dir", type=str, default="./weights_new/", help="directory in which training state and model should be saved")
    parser.add_argument("--save-rate", type=int, default=100, help="save model once every time this many episodes are completed")
    parser.add_argument("--load-dir", type=str, default="./Weights_final/", help="directory in which training state and model are loaded")
    # Evaluation
    parser.add_argument("--restore", action="store_true", default=False)
    parser.add_argument("--display", action="store_true", default=False)
    parser.add_argument("--benchmark", action="store_true", default=True)
    parser.add_argument("--benchmark-iters", type=int, default=-1, help="number of iterations run for benchmarking")
    parser.add_argument("--benchmark-dir", type=str, default="./benchmark_files/", help="directory where benchmark data is saved")
    parser.add_argument("--plots-dir", type=str, default="./testing_plots/", help="directory where plot data is saved")
    return parser.parse_args()

def mlp_model(input, num_outputs, scope, reuse=False, num_units=64, rnn_cell=None):
    # This model takes as input an observation and returns values of all actions
    with tf.variable_scope(scope, reuse=reuse):
        out = input
        out = layers.fully_connected(out, num_outputs=num_units, activation_fn=tf.nn.relu)
        out = layers.fully_connected(out, num_outputs=num_units, activation_fn=tf.nn.relu)
        out = layers.fully_connected(out, num_outputs=num_outputs, activation_fn=None)
        return out

def make_env(scenario_name, arglist, benchmark=False):
    from multiagent.environment import MultiAgentEnv
    import multiagent.scenarios as scenarios

    # load scenario from script
    scenario = scenarios.load(scenario_name + ".py").Scenario()
    # create world
    world = scenario.make_world()
    # create multiagent environment
    if benchmark:
        env = MultiAgentEnv(world, scenario.reset_world, scenario.reward, scenario.observation, scenario.benchmark_data)
    else:
        env = MultiAgentEnv(world, scenario.reset_world, scenario.reward, scenario.observation)
    return env

def get_trainers(env, num_adversaries, obs_shape_n, arglist):
    trainers = []
    model = mlp_model
    trainer = MADDPGAgentTrainer
    for i in range(num_adversaries):
        trainers.append(trainer(
            "agent_%d" % i, model, obs_shape_n, env.action_space, i, arglist,
            local_q_func=(arglist.adv_policy=='ddpg')))
    for i in range(num_adversaries, env.n):
        trainers.append(trainer(
            "agent_%d" % i, model, obs_shape_n, env.action_space, i, arglist,
            local_q_func=(arglist.good_policy=='ddpg')))
    return trainers


def test(arglist):
    with U.single_threaded_session():
        # Create environment
        env = make_env(arglist.scenario, arglist, arglist.benchmark)
        # Create agent trainers
        obs_shape_n = [env.observation_space[i].shape for i in range(env.n)]
        num_adversaries = min(env.n, arglist.num_adversaries)
        trainers = get_trainers(env, num_adversaries, obs_shape_n, arglist)
        print('Using good policy {} and adv policy {}'.format(arglist.good_policy, arglist.adv_policy))

        # Initialize
        U.initialize()

        # Load previous results, if necessary
        if arglist.load_dir == "":
            arglist.load_dir = arglist.save_dir

        print('Loading previous state...')
        #MAKE SURE LOAD_DIR IS WHERE WEIGHTS ARE
        U.load_state(arglist.load_dir+ "policy")

        episode_rewards = [0.0]  # sum of rewards for all agents
        agent_rewards = [[0.0] for _ in range(env.n)]  # individual agent reward
        final_ep_rewards = []  # sum of rewards for training curve
        final_ep_ag_rewards = []  # agent rewards for training curve
        agent_info = [[[]]]  # placeholder for benchmarking info

        t_collisions = []
        collisions = []
        min_dist = []
        obs_covered = []

        final_collisions = []
        final_dist = []
        final_obs_cov = []


        transition = []


        obs_n = env.reset()
        episode_step = 0
        train_step = 0
        t_start = time.time()

        print('Starting iterations...')
        while True:
            # get action
            action_n = [agent.action(obs) for agent, obs in zip(trainers,obs_n)]
            # environment step



            a_n = []

            for i in range(len(trainers)):
                a_n.append(np.random.choice(np.arange(len(action_n[0])), p=action_n[i]))



            #new_obs_n, rew_n, done_n, info_n = env.step(action_n)
            new_obs_n, rew_n, done_n, info_n = env.step(a_n)
            episode_step += 1
            done = all(done_n)
            terminal = (episode_step >= arglist.max_episode_len)
            # collect experience

            o = np.asarray(obs_n)
            o_next = np.asarray(new_obs_n)
            o = np.reshape(o, [1, 54])
            o_next = np.reshape(o_next, [1, 54])

            transition.append((o, a_n[0], a_n[1], a_n[2], o_next))

            obs_n = new_obs_n

            for i, rew in enumerate(rew_n):
                episode_rewards[-1] += rew
                agent_rewards[i][-1] += rew

            if done or terminal:
                obs_n = env.reset()
                episode_step = 0
                episode_rewards.append(0)
                for a in agent_rewards:
                    a.append(0)
                agent_info.append([[]])

            # increment global step counter
            train_step += 1

            # for benchmarking learned policies
            # COMMENT OUT FOR NON-MADDPG ENVS
            if arglist.benchmark:
                collisions.append(max([info_n['n'][0][1], info_n['n'][1][1], info_n['n'][2][1]]) - 1)

                if train_step > arglist.benchmark_iters and (done or terminal):
                    os.makedirs(os.path.dirname(arglist.benchmark_dir), exist_ok=True)
                    min_dist.append(min([info_n['n'][0][2], info_n['n'][1][2], info_n['n'][1][2]]))
                    obs_covered.append(info_n['n'][0][3])
                    t_collisions.append(sum(collisions))
                    collisions = []



            # for displaying learned policies
            if arglist.display:
                time.sleep(0.1)
                env.render()
                continue

            # save model, display training output
            if terminal and (len(episode_rewards) % arglist.save_rate == 0):


                # print statement depends on whether or not there are adversaries
                if num_adversaries == 0:
                    print("steps: {}, episodes: {}, mean episode reward: {}, time: {}".format(
                        train_step, len(episode_rewards), np.mean(episode_rewards[-arglist.save_rate:]), round(time.time()-t_start, 3)))
                else:
                    print("steps: {}, episodes: {}, mean episode reward: {}, agent episode reward: {}, time: {}".format(
                        train_step, len(episode_rewards), np.mean(episode_rewards[-arglist.save_rate:]),
                        [np.mean(rew[-arglist.save_rate:]) for rew in agent_rewards], round(time.time()-t_start, 3)))
                t_start = time.time()
                # Keep track of final episode reward
                final_ep_rewards.append(np.mean(episode_rewards[-arglist.save_rate:]))
                for rew in agent_rewards:
                    final_ep_ag_rewards.append(np.mean(rew[-arglist.save_rate:]))

                final_collisions.append(np.mean(t_collisions[-arglist.save_rate:]))
                final_dist.append(np.mean(min_dist[-arglist.save_rate:]))
                final_obs_cov.append(np.mean(obs_covered[-arglist.save_rate:]))



                os.makedirs(os.path.dirname(arglist.plots_dir), exist_ok=True)
                plt.plot(final_ep_rewards)
                plt.savefig(arglist.plots_dir + arglist.exp_name + '_rewards.png')
                plt.clf()

                plt.plot(final_dist)
                plt.savefig(arglist.plots_dir + arglist.exp_name + '_min_dist.png')
                plt.clf()

                plt.plot(final_obs_cov)
                plt.savefig(arglist.plots_dir + arglist.exp_name + '_obstacles_covered.png')
                plt.clf()

                plt.plot(final_collisions)
                plt.savefig(arglist.plots_dir + arglist.exp_name + '_total_collisions.png')
                plt.clf()

            # saves final episode reward for plotting training curve later
            if len(episode_rewards) > arglist.num_episodes:
                rew_file_name = arglist.plots_dir + arglist.exp_name + '_rewards.pkl'

                with open(rew_file_name, 'wb') as fp:
                    pickle.dump(final_ep_rewards, fp)
                agrew_file_name = arglist.plots_dir + arglist.exp_name + '_agrewards.pkl'
                with open(agrew_file_name, 'wb') as fp:
                    pickle.dump(final_ep_ag_rewards, fp)



                print('...Finished total of {} episodes.'.format(len(episode_rewards)))
                print()
                print("Average min dist: {}".format(np.mean(final_dist)))
                print("Average number of collisions: {}".format(np.mean(final_collisions)))
                break

        print("Saving Transition...")
        transition = np.asarray(transition)
        print(transition.shape)
        np.save('Transition_new', transition)
        print(transition[-1])

def maddpg_test():
    arglist = parse_args()
    test(arglist)

