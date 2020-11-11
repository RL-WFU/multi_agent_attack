from main import *
from Attack import *
import argparse
from maddpg_implementation.experiments.train import *
from maddpg_implementation.experiments.test import *
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense


if __name__ == '__main__':

    parser = argparse.ArgumentParser()

    parser.add_argument('--training', default=True, type=bool, help='Whether to train or test model specified by --mode')
    parser.add_argument('--mode', default='attack', type=str, help='attack or regular')
    parser.add_argument('--good_weights', default=None, type=str, help='weights of good agents')
    parser.add_argument('--bad_weights', default=None, type=str, help='default MADDPG weights of malicious agent')
    parser.add_argument('--predictor_weights', default=None, type=str, help='Weights of predictor network for attack')

    args = parser.parse_args()



    #run()
    #maddpg_train()
    maddpg_test()

    """
    o = [[[1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3, 4]]]
    a = [[0, -1, -2]]
    t = [5, 8, 10]
    print(*(o+a+[t]))
    """







