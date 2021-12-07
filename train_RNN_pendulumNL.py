"""
Original code from John Schulman for CS294 Deep Reinforcement Learning Spring 2017
Adapted for CS294-112 Fall 2017 by Abhishek Gupta and Joshua Achiam
Adapted for CS294-112 Fall 2018 by Michael Chang and Soroush Nasiriany

Modified from answers written by the authors
"""

import numpy as np
# import tensorflow as tf
import tensorflow.compat.v1 as tf

tf.disable_v2_behavior()
import gym
import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import logz
import time
import inspect
from multiprocessing import Process
import scipy
from pendulumNL import Env
from pendulumNL import Obs_Env as Partial_Env
from pendulumNL import Obs_Norm_Env as Partial_Norm_Env



# ============================================================================================#
# Utilities
# ============================================================================================#

# ========================================================================================#
#                           ----------PROBLEM 2----------
# ========================================================================================#
def build_mlp(
        input_placeholder,
        output_size,
        scope,
        n_layers,
        size,
        activation=tf.nn.tanh,
        output_activation=None):
    """
        Builds a feedforward neural network
        arguments:
            input_placeholder: placeholder variable for the state (batch_size, input_size)
            output_size: size of the output layer
            scope: variable scope of the network
            n_layers: number of hidden layers
            size: dimension of the hidden layer
            activation: activation of the hidden layers
            output_activation: activation of the ouput layers

        returns:
            output placeholder of the network (the result of a forward pass)
    """
    # raise NotImplementedError
    with tf.variable_scope(scope):
        sy_input = input_placeholder

        # Hidden layers
        hidden_layer = tf.layers.dense(inputs=sy_input,
                                       units=size,
                                       activation=activation,
                                       kernel_initializer=tf.truncated_normal_initializer(stddev=0.0001,
                                                                                          dtype=tf.float32),
                                       bias_initializer=tf.zeros_initializer())
        for _ in range(n_layers - 1):
            hidden_layer = tf.layers.dense(inputs=hidden_layer,
                                           units=size,
                                           activation=activation,
                                           kernel_initializer=tf.truncated_normal_initializer(stddev=0.0001,
                                                                                              dtype=tf.float32),
                                           bias_initializer=tf.zeros_initializer())

        # Output layer
        output_placeholder = tf.layers.dense(inputs=hidden_layer,
                                             units=output_size,
                                             activation=output_activation,
                                             kernel_initializer=tf.truncated_normal_initializer(stddev=0.0001,
                                                                                                dtype=tf.float32),
                                             bias_initializer=tf.zeros_initializer())
        return output_placeholder


class RNNController(object):

    def __init__(self):
        self.is_bias = None
        self.activation = None

        self.ob_dim = None
        self.ac_dim = None
        self.xi_dim = None
        self.hid_dim = None

        self.ph_input_nto = None
        self.ph_ac_nta = None
        self.ph_adv_nt = None
        self.ph_dn_nt = None
        self.ph_initstate_s = None
        self.sy_output_nta = None

        self.ph1_input_no = None
        self.ph1_initstate_ns = None
        self.sy1_output_na = None
        self.sy1_nextstate_ns = None

        # weights
        self.AK = None
        self.BK1 = None
        self.BK2 = None
        self.CK1 = None
        self.DK1 = None
        self.DK2 = None
        self.CK2 = None
        self.DK3 = None

        self.bxi = None
        self.bu = None
        self.bv = None

    def build_rnn(
            self,
            initstate_placeholder,
            input_size,
            step_num,
            output_size,
            scope,
            hid_nodes_size,
            states_size,
            activation=tf.nn.tanh,
            is_bias=False,
            output_activation=None):
        """
            Builds a feedforward neural network
            arguments:
                input_placeholder: placeholder variable for the state (batch_size, input_size)
                output_size: size of the output layer
                scope: variable scope of the network
                n_layers: number of hidden layers
                hid_nodes_size: dimension of the hidden layer
                activation: activation of the hidden layers
                output_activation: activation of the ouput layers

            returns:
                output placeholder of the network (the result of a forward pass)
        """
        # raise NotImplementedError

        with tf.variable_scope(scope):
            # batch_size = input_placeholder.shape[0]

            if initstate_placeholder is None:  # TODO: if none then 0 else repleat to the match size
                # sy_initstate = tf.zeros(tf.stack([batch_size, states_size]))
                sy_initstate = tf.zeros(tf.stack([1, states_size]))
            else:  # broadcast shape if needed
                # sy_initstate = initstate_placeholder.reshape([1,-1]) + tf.zeros(tf.stack([batch_size, states_size]))
                # sy_initstate = tf.broadcast_to(initstate_placeholder.reshape([1,-1]), tf.stack([batch_size, states_size]))
                sy_initstate = tf.reshape(initstate_placeholder, [1, -1])
                pass

            input_placeholder = tf.placeholder(shape=[None, step_num, input_size], name="obrnn", dtype=tf.float32)
            termination_placeholder = tf.placeholder(shape=[None, step_num], name="dnrnn", dtype=tf.float32)

            sy_input = tf.unstack(input_placeholder, axis=1)  # input: nto
            sy_done = tf.unstack(tf.reshape(termination_placeholder, [-1, step_num, 1]), axis=1)  # input: nt

            #  xi(k+1) = AK  xi(k) + BK1 w(k) + BK2 y(k)
            #  u(k)    = CK1 xi(k) + DK1 w(k) + DK2 y(k)
            #  v(k)    = CK2 xi(k) + DK3 y(k)
            #  w(k)    = phi(v(k))
            #
            #  xi: hidden state
            #  y:  input
            #  v:  after dense
            #  w:  after activation
            #  u:  output
            #  TODO: biased case? 1 in y?

            # xi
            AK = tf.Variable(tf.random.truncated_normal(shape=[states_size, states_size], stddev=0.0001))
            BK1 = tf.Variable(tf.random.truncated_normal(shape=[states_size, hid_nodes_size], stddev=0.0001))
            BK2 = tf.Variable(tf.random.truncated_normal(shape=[states_size, input_size], stddev=0.0001))

            # u
            CK1 = tf.Variable(tf.random.truncated_normal(shape=[output_size, states_size], stddev=0.0001))
            DK1 = tf.Variable(tf.random.truncated_normal(shape=[output_size, hid_nodes_size], stddev=0.0001))
            DK2 = tf.Variable(tf.random.truncated_normal(shape=[output_size, input_size], stddev=0.0001))

            # v
            CK2 = tf.Variable(tf.random.truncated_normal(shape=[hid_nodes_size, states_size], stddev=0.0001))
            DK3 = tf.Variable(tf.random.truncated_normal(shape=[hid_nodes_size, input_size], stddev=0.0001))

            if is_bias:
                bxi = tf.Variable(tf.zeros(shape=[states_size]))
                bu = tf.Variable(tf.zeros(shape=[output_size]))
                bv = tf.Variable(tf.zeros(shape=[hid_nodes_size]))

            # feedford func for 1 step
            def feedforward(y, xi):
                #  v(k)    = CK2 xi(k) + DK3 y(k)
                v = tf.linalg.matmul(xi, CK2, transpose_b=True) + \
                    tf.linalg.matmul(y, DK3, transpose_b=True)
                if is_bias:
                    v += bv

                #  w(k)    = phi(v(k))
                w = activation(v)

                #  u(k)    = CK1 xi(k) + DK1 w(k) + DK2 y(k)
                u = tf.linalg.matmul(xi, CK1, transpose_b=True) + \
                    tf.linalg.matmul(w, DK1, transpose_b=True) + \
                    tf.linalg.matmul(y, DK2, transpose_b=True)
                if is_bias:
                    u += bu

                #  xi(k+1) = AK  xi(k) + BK1 w(k) + BK2 y(k)
                xi = tf.linalg.matmul(xi, AK, transpose_b=True) + \
                     tf.linalg.matmul(w, BK1, transpose_b=True) + \
                     tf.linalg.matmul(y, BK2, transpose_b=True)
                if is_bias:
                    xi += bxi

                return u, xi

            # rnn feedforward
            xi = sy_initstate  # may have to make shape consistent.
            outputs = []
            for i in range(len(sy_input)):  # k steps
                y = sy_input[i]
                d = sy_done[i]

                u, xi = feedforward(y, xi)

                xi = xi * (1 - d) + sy_initstate * d  # if done

                outputs.append(u)

            output_ph = tf.stack(outputs, axis=1)

            # single step case for evaluation
            self.ph1_initstate_ns = tf.placeholder(shape=[None, states_size], name="xi1", dtype=tf.float32)
            self.ph1_input_no = tf.placeholder(shape=[None, input_size], name="ob1", dtype=tf.float32)

            # single step case for evaluation
            xi = self.ph1_initstate_ns
            y = self.ph1_input_no
            u, xi = feedforward(y, xi)

            self.sy1_output_na = u
            self.sy1_nextstate_ns = xi

            # save the attributes
            self.ob_dim = input_size
            self.ac_dim = output_size
            self.xi_dim = states_size
            self.hid_dim = hid_nodes_size

            self.activation = activation
            self.is_bias = is_bias

            self.ph_input_nto = input_placeholder
            self.ph_initstate_s = initstate_placeholder
            self.ph_ac_nta = tf.placeholder(shape=[None, step_num, output_size], name="acrnn", dtype=tf.float32)
            self.ph_adv_nt = tf.placeholder(shape=[None, step_num], name="advrnn", dtype=tf.float32)
            self.ph_dn_nt = termination_placeholder
            self.sy_output_nta = output_ph

            # weights
            self.AK = AK
            self.BK1 = BK1
            self.BK2 = BK2
            self.CK1 = CK1
            self.DK1 = DK1
            self.DK2 = DK2
            self.CK2 = CK2
            self.DK3 = DK3

            if is_bias:
                self.bxi = bxi
                self.bu = bu
                self.bv = bv

            return output_ph

    def get_weights(self, sess):
        ret_var = [
            self.AK,
            self.BK1,
            self.BK2,
            self.CK1,
            self.DK1,
            self.DK2,
            self.CK2,
            self.DK3
        ]
        ret_bias = [
            self.bxi,
            self.bu,
            self.bv
        ]
        op = ret_var + ret_bias if self.is_bias else ret_var
        ret = sess.run(op)
        if not self.is_bias:
            ret += [None, None, None]
        return ret

    def set_weights(self, sess):
        pass


def pathlength(path):
    return len(path["reward"])


def setup_logger(logdir, locals_):
    # Configure output directory for logging
    logz.configure_output_dir(logdir)
    # Log experimental parameters
    args = inspect.getargspec(train_PG)[0]
    params = {k: locals_[k] if k in locals_ else None for k in args}
    logz.save_params(params)


def fancy_slice_2d(X, inds0, inds1):
    """
    Like numpy's X[inds0, inds1]
    """
    inds0 = tf.cast(inds0, tf.int64)
    inds1 = tf.cast(inds1, tf.int64)
    shape = tf.cast(tf.shape(X), tf.int64)
    ncols = shape[1]
    Xflat = tf.reshape(X, [-1])
    return tf.gather(Xflat, inds0 * ncols + inds1)


# ============================================================================================#
# Policy Gradient
# ============================================================================================#

class Agent(object):
    def __init__(self, computation_graph_args, sample_trajectory_args, estimate_return_args):
        super(Agent, self).__init__()
        self.ob_dim = computation_graph_args['ob_dim']
        self.ac_dim = computation_graph_args['ac_dim']
        self.discrete = computation_graph_args['discrete']
        self.size = computation_graph_args['size']
        self.states_size = computation_graph_args['size']
        self.n_layers = computation_graph_args['n_layers']
        self.learning_rate = computation_graph_args['learning_rate']
        self.rnn_bias = computation_graph_args['rnn_bias']

        self.animate = sample_trajectory_args['animate']
        self.max_path_length = sample_trajectory_args['max_path_length']
        self.min_timesteps_per_batch = sample_trajectory_args['min_timesteps_per_batch']
        self.step_num = sample_trajectory_args['step_num']  # RNN steps
        self.rnn_test_nostates = sample_trajectory_args['rnn_test_nostates']

        self.gamma = estimate_return_args['gamma']
        self.reward_to_go = estimate_return_args['reward_to_go']
        self.nn_baseline = estimate_return_args['nn_baseline']
        self.normalize_advantages = estimate_return_args['normalize_advantages']

    def init_tf_sess(self):
        tf_config = tf.ConfigProto(inter_op_parallelism_threads=1, intra_op_parallelism_threads=1)
        tf_config.gpu_options.allow_growth = True
        self.sess = tf.Session(config=tf_config)
        self.sess.__enter__()  # equivalent to `with self.sess:`
        tf.global_variables_initializer().run()  # pylint: disable=E1101
        self.saver = tf.train.Saver()

    def save_variables(self, logdir):
        self.saver.save(self.sess, os.path.join(logdir, 'model.ckpt'))

    # ========================================================================================#
    #                           ----------PROBLEM 2----------
    # ========================================================================================#
    def define_placeholders(self):
        """
            Placeholders for batch batch observations / actions / advantages in policy gradient
            loss function.
            See Agent.build_computation_graph for notation

            returns:
                sy_ob_no: placeholder for observations
                sy_ac_na: placeholder for actions
                sy_adv_n: placeholder for advantages
        """
        # raise NotImplementedError
        sy_ob_no = tf.placeholder(shape=[None, self.ob_dim], name="ob", dtype=tf.float32)
        if self.discrete:
            raise NotImplementedError()
            sy_ac_na = tf.placeholder(shape=[None], name="ac", dtype=tf.int32)
        else:
            sy_ac_na = tf.placeholder(shape=[None, self.ac_dim], name="ac", dtype=tf.float32)
        # YOUR CODE HERE
        sy_adv_n = tf.placeholder(shape=[None], name="adv", dtype=tf.float32)
        sy_dn_n = tf.placeholder(shape=[None], name="done", dtype=tf.float32)
        return sy_ob_no, sy_ac_na, sy_adv_n, sy_dn_n

    # ========================================================================================#
    #                           ----------PROBLEM 2----------
    # ========================================================================================#
    def policy_forward_pass(self, sy_initstate=None, is_bias=False):
        """ Constructs the symbolic operation for the policy network outputs,
            which are the parameters of the policy distribution p(a|s)

            arguments:
                sy_ob_no: (batch_size, self.ob_dim)
                sy_dn_n: (batch_size, )

            returns:
                the parameters of the policy.

                if discrete, the parameters are the logits of a categorical distribution
                    over the actions
                    sy_logits_na: (batch_size, self.ac_dim)

                if continuous, the parameters are a tuple (mean, log_std) of a Gaussian
                    distribution over actions. log_std should just be a trainable
                    variable, not a network output.
                    sy_mean: (batch_size, self.ac_dim)
                    sy_logstd: (self.ac_dim,)

            Hint: use the 'build_mlp' function to output the logits (in the discrete case)
                and the mean (in the continuous case).
                Pass in self.n_layers for the 'n_layers' argument, and
                pass in self.size for the 'size' argument.
        """
        # raise NotImplementedError
        if self.discrete:
            raise NotImplementedError()
            # YOUR_CODE_HERE
            sy_logits_na = build_mlp(
                input_placeholder=sy_ob_nto,
                output_size=self.ac_dim,
                scope="nn_policy",
                n_layers=self.n_layers,
                size=self.size)
            return sy_logits_na
        else:
            # YOUR_CODE_HERE
            # sy_mean = build_mlp(
            #                    input_placeholder=sy_ob_no,
            #                    output_size=self.ac_dim,
            #                    scope="nn_policy",
            #                    n_layers=self.n_layers,
            #                    size=self.size)
            self.rnn = RNNController()
            sy_mean = self.rnn.build_rnn(
                initstate_placeholder=sy_initstate,
                input_size=self.ob_dim,
                step_num=self.step_num,
                output_size=self.ac_dim,
                scope="rnn_policy",
                hid_nodes_size=self.size,
                states_size=self.states_size,
                is_bias=is_bias
            )

            # sy_logstd = tf.get_variable("log_sigma",[self.ac_dim], initializer=tf.zeros_initializer())
            sy_logstd = tf.get_variable("log_sigma", [self.ac_dim], initializer=tf.initializers.constant(np.log(0.2)))
            # sy_logstd = tf.Variable(tf.random_normal([self.ac_dim],mean=-2.5, stddev=0.01, seed=41))

            return (sy_mean, sy_logstd)

    # ========================================================================================#
    #                           ----------PROBLEM 2----------
    # ========================================================================================#
    def sample_action(self, policy_parameters):
        """ Constructs a symbolic operation for stochastically sampling from the policy
            distribution

            arguments:
                policy_parameters
                    if discrete: logits of a categorical distribution over actions
                        sy_logits_na: (batch_size, self.ac_dim)
                    if continuous: (mean, log_std) of a Gaussian distribution over actions
                        sy_mean: (batch_size, self.ac_dim)
                        sy_logstd: (self.ac_dim,)

            returns:
                sy_sampled_ac:
                    if discrete: (batch_size,)
                    if continuous: (batch_size, self.ac_dim)

            Hint: for the continuous case, use the reparameterization trick:
                 The output from a Gaussian distribution with mean 'mu' and std 'sigma' is

                      mu + sigma * z,         z ~ N(0, I)

                 This reduces the problem to just sampling z. (Hint: use tf.random_normal!)
        """
        # raise NotImplementedError
        if self.discrete:
            raise NotImplementedError()
            sy_logits_na = policy_parameters
            # YOUR_CODE_HERE
            sy_sampled_ac = tf.multinomial(sy_logits_na, num_samples=tf.shape(sy_logits_na)[0])
            sy_sampled_ac = tf.reshape(sy_sampled_ac, [-1])
        else:
            sy_mean, sy_logstd = policy_parameters
            # YOUR_CODE_HERE
            # sy_sampled_ac = sy_mean + sy_logstd*tf.random_normal(tf.shape(sy_logits_na)[0], mean=0.0, stddev=1.0)
            EPSILON = 1e-8
            # EPSILON=-np.log(5)
            dist = tf.distributions.Normal(loc=sy_mean, scale=tf.exp(sy_logstd + EPSILON), validate_args=True)
            sy_sampled_ac = dist.sample()
        return sy_sampled_ac

    # ========================================================================================#
    #                           ----------PROBLEM 2----------
    # ========================================================================================#
    def get_log_prob(self, policy_parameters, sy_ac_nta):
        """ Constructs a symbolic operation for computing the log probability of a set of actions
            that were actually taken according to the policy

            arguments:
                policy_parameters
                    if discrete: logits of a categorical distribution over actions
                        sy_logits_na: (batch_size, self.ac_dim)
                    if continuous: (mean, log_std) of a Gaussian distribution over actions
                        sy_mean: (batch_size, self.ac_dim)
                        sy_logstd: (self.ac_dim,)

                sy_ac_na:
                    if discrete: (batch_size,)
                    if continuous: (batch_size, self.ac_dim)

            returns:
                sy_logprob_n: (batch_size)

            Hint:
                For the discrete case, use the log probability under a categorical distribution.
                For the continuous case, use the log probability under a multivariate gaussian.
        """
        # raise NotImplementedError
        if self.discrete:
            raise NotImplementedError()
            sy_logits_na = policy_parameters
            # YOUR_CODE_HERE
            sy_logp_na = tf.nn.log_softmax(sy_logits_na)
            sy_logprob_nt = fancy_slice_2d(sy_logp_na, tf.range(tf.shape(sy_ac_nta)[0]), sy_ac_nta)
        else:
            sy_mean, sy_logstd = policy_parameters
            # YOUR_CODE_HERE
            EPSILON = 1e-8
            dist = tf.distributions.Normal(loc=sy_mean, scale=tf.exp(sy_logstd + EPSILON), validate_args=True)
            sy_logprob_nt = tf.reduce_sum(dist.log_prob(sy_ac_nta), axis=-1)  # log_prob is actually log(pdf)
        return sy_logprob_nt

    def build_computation_graph(self):
        """
            Notes on notation:

            Symbolic variables have the prefix sy_, to distinguish them from the numerical values
            that are computed later in the function

            Prefixes and suffixes:
            ob - observation
            ac - action
            _no - this tensor should have shape (batch self.size /n/, observation dim)
            _na - this tensor should have shape (batch self.size /n/, action dim)
            _n  - this tensor should have shape (batch self.size /n/)

            Note: batch self.size /n/ is defined at runtime, and until then, the shape for that axis
            is None

            ----------------------------------------------------------------------------------
            loss: a function of self.sy_logprob_n and self.sy_adv_n that we will differentiate
                to get the policy gradient.
        """

        #### Baseline only
        self.sy_ob_no, self.sy_ac_na, self.sy_adv_n, self.sy_dn_n = self.define_placeholders()
        ##################

        # The policy takes in an observation and produces a distribution over the action space
        self.policy_parameters = self.policy_forward_pass(is_bias=self.rnn_bias)

        # We can sample actions from this action distribution.
        # This will be called in Agent.sample_trajectory() where we generate a rollout.
        # self.sy_sampled_ac = self.sample_action(self.policy_parameters)
        # 1-step for sampling ac
        self.policy_parameters_1step = [self.rnn.sy1_output_na, self.policy_parameters[-1]]
        self.sy1_sampled_ac = self.sample_action(self.policy_parameters_1step)

        # We can also compute the logprob of the actions that were actually taken by the policy
        # This is used in the loss function.
        self.sy_logprob_nt = self.get_log_prob(self.policy_parameters, self.rnn.ph_ac_nta)

        # ========================================================================================#
        #                           ----------PROBLEM 2----------
        # Loss Function and Training Operation
        # ========================================================================================#
        loss = -tf.reduce_mean(self.rnn.ph_adv_nt * self.sy_logprob_nt)

        # Adding clip gradient... RNN training explodes once every few moments..
        optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate)
        # optimizer = tf.train.GradientDescentOptimizer(learning_rate=self.learning_rate)
        # by value
        gvs = optimizer.compute_gradients(loss)
        capped_gvs = [(tf.clip_by_value(grad, -10., 10.), var) for grad, var in gvs]
        self.update_op = optimizer.apply_gradients(capped_gvs)
        # by norm
        # gradients, variables = zip(*optimizer.compute_gradients(loss))
        # gradients = [
        #    None if gradient is None else tf.clip_by_norm(gradient, 5.0)
        #    for gradient in gradients]
        # self.update_op = optimizer.apply_gradients(zip(gradients, variables))

        # self.update_op = tf.train.AdamOptimizer(self.learning_rate).minimize(loss)

        # ========================================================================================#
        #                           ----------PROBLEM 6----------
        # Optional Baseline
        #
        # Define placeholders for targets, a loss function and an update op for fitting a
        # neural network baseline. These will be used to fit the neural network baseline.
        # ========================================================================================#
        if self.nn_baseline:
            # raise NotImplementedError
            self.baseline_prediction = tf.squeeze(build_mlp(
                self.sy_ob_no,
                1,
                "nn_baseline",
                n_layers=self.n_layers,
                size=self.size))
            # YOUR_CODE_HERE
            self.sy_target_n = tf.placeholder(shape=None, name="target", dtype=tf.float32)
            baseline_loss = tf.nn.l2_loss(self.baseline_prediction - self.sy_target_n, name="loss_target")
            self.baseline_update_op = tf.train.AdamOptimizer(self.learning_rate).minimize(baseline_loss)

    def sample_trajectories(self, itr, env):
        # Collect paths until we have enough timesteps
        timesteps_this_batch = 0
        paths = []
        while True:
            animate_this_episode = (len(paths) == 0 and (itr % 10 == 0) and self.animate)
            path = self.sample_trajectory(env, animate_this_episode)
            paths.append(path)
            timesteps_this_batch += pathlength(path)
            if timesteps_this_batch > self.min_timesteps_per_batch:
                break
        return paths, timesteps_this_batch

    def sample_trajectory(self, env, animate_this_episode):
        ob = env.reset()
        obs, acs, rewards, dones = [], [], [], []
        xi0 = np.zeros(self.states_size, dtype=np.float32)
        xi = xi0
        steps = 0
        while True:
            obs.append(ob)
            # ====================================================================================#
            #                           ----------PROBLEM 3----------
            # ====================================================================================#
            # raise NotImplementedError
            ac, xi = self.sess.run([self.sy1_sampled_ac, self.rnn.sy1_nextstate_ns],
                                   feed_dict={
                                       self.rnn.ph1_input_no: ob[None],
                                       self.rnn.ph1_initstate_ns: xi[None]
                                   })

            ac = ac[0];
            xi = xi[0]
            if self.rnn_test_nostates:
                xi = xi0

            acs.append(ac)
            ob, rew, done, _ = env.step(ac)
            rewards.append(rew)
            dones.append(done)
            steps += 1
            if done or steps > self.max_path_length:
                dones[-1] = True
                break
        path = {"observation": np.array(obs, dtype=np.float32),
                "reward": np.array(rewards, dtype=np.float32),
                "action": np.array(acs, dtype=np.float32),
                "termination": np.array(dones, dtype=np.float32)}
        return path

    # ====================================================================================#
    #                           ----------PROBLEM 3----------
    # ====================================================================================#
    def sum_of_rewards(self, re_n):
        """
            Monte Carlo estimation of the Q function.

            let sum_of_path_lengths be the sum of the lengths of the paths sampled from
                Agent.sample_trajectories
            let num_paths be the number of paths sampled from Agent.sample_trajectories

            arguments:
                re_n: length: num_paths. Each element in re_n is a numpy array
                    containing the rewards for the particular path

            returns:
                q_n: shape: (sum_of_path_lengths). A single vector for the estimated q values
                    whose length is the sum of the lengths of the paths

            ----------------------------------------------------------------------------------

            Your code should construct numpy arrays for Q-values which will be used to compute
            advantages (which will in turn be fed to the placeholder you defined in
            Agent.define_placeholders).

            Recall that the expression for the policy gradient PG is

                  PG = E_{tau} [sum_{t=0}^T grad log pi(a_t|s_t) * (Q_t - b_t )]

            where

                  tau=(s_0, a_0, ...) is a trajectory,
                  Q_t is the Q-value at time t, Q^{pi}(s_t, a_t),
                  and b_t is a baseline which may depend on s_t.

            You will write code for two cases, controlled by the flag 'reward_to_go':

              Case 1: trajectory-based PG

                  (reward_to_go = False)

                  Instead of Q^{pi}(s_t, a_t), we use the total discounted reward summed over
                  entire trajectory (regardless of which time step the Q-value should be for).

                  For this case, the policy gradient estimator is

                      E_{tau} [sum_{t=0}^T grad log pi(a_t|s_t) * Ret(tau)]

                  where

                      Ret(tau) = sum_{t'=0}^T gamma^t' r_{t'}.

                  Thus, you should compute

                      Q_t = Ret(tau)

              Case 2: reward-to-go PG

                  (reward_to_go = True)

                  Here, you estimate Q^{pi}(s_t, a_t) by the discounted sum of rewards starting
                  from time step t. Thus, you should compute

                      Q_t = sum_{t'=t}^T gamma^(t'-t) * r_{t'}


            Store the Q-values for all timesteps and all trajectories in a variable 'q_n',
            like the 'ob_no' and 'ac_na' above.
        """
        # YOUR_CODE_HERE
        q_n = np.zeros(0)
        if self.reward_to_go:
            # raise NotImplementedError
            for _ in range(len(re_n)):
                r = re_n[_]
                T = r.shape[0]
                q_path = np.zeros(T)
                temp = 0
                for t in range(T - 1, -1, -1):
                    q_path[t] = r[t] + self.gamma * temp
                    temp = q_path[t]
                q_n = np.append(q_n, q_path)
        else:
            # raise NotImplementedError
            for _ in range(len(re_n)):
                r = re_n[_]
                T = r.shape[0]
                w = np.power(self.gamma, range(T))
                q_path = np.sum(w * r)
                q_n = np.append(q_n, q_path * np.ones(T))
        return q_n

    def compute_advantage(self, ob_no, q_n):
        """
            Computes advantages by (possibly) subtracting a baseline from the estimated Q values

            let sum_of_path_lengths be the sum of the lengths of the paths sampled from
                Agent.sample_trajectories
            let num_paths be the number of paths sampled from Agent.sample_trajectories

            arguments:
                ob_no: shape: (sum_of_path_lengths, ob_dim)
                q_n: shape: (sum_of_path_lengths). A single vector for the estimated q values
                    whose length is the sum of the lengths of the paths

            returns:
                adv_n: shape: (sum_of_path_lengths). A single vector for the estimated
                    advantages whose length is the sum of the lengths of the paths
        """
        # ====================================================================================#
        #                           ----------PROBLEM 6----------
        # Computing Baselines
        # ====================================================================================#
        if self.nn_baseline:
            # If nn_baseline is True, use your neural network to predict reward-to-go
            # at each timestep for each trajectory, and save the result in a variable 'b_n'
            # like 'ob_no', 'ac_na', and 'q_n'.
            #
            # Hint #bl1: rescale the output from the nn_baseline to match the statistics
            # (mean and std) of the current batch of Q-values. (Goes with Hint
            # #bl2 in Agent.update_parameters.
            # raise NotImplementedError
            b_n = self.sess.run(self.baseline_prediction, feed_dict={self.sy_ob_no: ob_no})  # YOUR CODE HERE
            b_n = b_n * q_n.std() + q_n.mean()
            adv_n = q_n - b_n  # reward - baseline_prediction
        else:
            adv_n = q_n.copy()
        return adv_n

    def estimate_return(self, ob_no, re_n):
        """
            Estimates the returns over a set of trajectories.

            let sum_of_path_lengths be the sum of the lengths of the paths sampled from
                Agent.sample_trajectories
            let num_paths be the number of paths sampled from Agent.sample_trajectories

            arguments:
                ob_no: shape: (sum_of_path_lengths, ob_dim)
                re_n: length: num_paths. Each element in re_n is a numpy array
                    containing the rewards for the particular path

            returns:
                q_n: shape: (sum_of_path_lengths). A single vector for the estimated q values
                    whose length is the sum of the lengths of the paths
                adv_n: shape: (sum_of_path_lengths). A single vector for the estimated
                    advantages whose length is the sum of the lengths of the paths
        """
        q_n = self.sum_of_rewards(re_n)
        adv_n = self.compute_advantage(ob_no, q_n)
        # ====================================================================================#
        #                           ----------PROBLEM 3----------
        # Advantage Normalization
        # ====================================================================================#
        if self.normalize_advantages:
            # On the next line, implement a trick which is known empirically to reduce variance
            # in policy gradient methods: normalize adv_n to have mean zero and std=1.
            # raise NotImplementedError
            adv_n = (adv_n - adv_n.mean()) / (adv_n.std() + 1e-8)
        return q_n, adv_n

    def update_parameters(self, ob_no, ac_na, q_n, adv_n, dn_n):
        """
            Update the parameters of the policy and (possibly) the neural network baseline,
            which is trained to approximate the value function.

            arguments:
                ob_no: shape: (sum_of_path_lengths, ob_dim)
                ac_na: shape: (sum_of_path_lengths).
                q_n: shape: (sum_of_path_lengths). A single vector for the estimated q values
                    whose length is the sum of the lengths of the paths
                adv_n: shape: (sum_of_path_lengths). A single vector for the estimated
                    advantages whose length is the sum of the lengths of the paths

            returns:
                nothing

        """
        # ====================================================================================#
        #                           ----------PROBLEM 6----------
        # Optimizing Neural Network Baseline
        # ====================================================================================#
        if self.nn_baseline:
            # If a neural network baseline is used, set up the targets and the inputs for the
            # baseline.
            #
            # Fit it to the current batch in order to use for the next iteration. Use the
            # baseline_update_op you defined earlier.
            #
            # Hint #bl2: Instead of trying to target raw Q-values directly, rescale the
            # targets to have mean zero and std=1. (Goes with Hint #bl1 in
            # Agent.compute_advantage.)

            # YOUR_CODE_HERE
            # raise NotImplementedError
            target_n = (q_n - q_n.mean()) / (q_n.std() + 1e-8)
            for _ in range(20):
                self.sess.run([self.baseline_update_op], feed_dict={self.sy_ob_no: ob_no, self.sy_target_n: target_n})

        # ====================================================================================#
        #                           ----------PROBLEM 3----------
        # Performing the Policy Update
        # ====================================================================================#

        # Call the update operation necessary to perform the policy gradient update based on
        # the current batch of rollouts.
        #
        # For debug purposes, you may wish to save the value of the loss function before
        # and after an update, and then log them below.

        # YOUR_CODE_HERE
        # raise NotImplementedError
        # Policy update
        # self.sess.run(self.update_op, feed_dict={self.sy_ob_no:ob_no, self.sy_ac_na:ac_na, self.sy_adv_n:adv_n})

        # Now we have to slice the samples into chunks for rnn
        t = self.step_num
        n = len(ob_no) // t  # number of chunks (new n, aka batch size)
        ob_nto = ob_no[:n * t].reshape([n, t, -1])
        ac_nta = ac_na[:n * t].reshape([n, t, -1])
        adv_nt = adv_n[:n * t].reshape([n, t])
        dn_nt = dn_n[:n * t].reshape([n, t])

        self.sess.run(self.update_op, feed_dict={
            self.rnn.ph_input_nto: ob_nto,
            self.rnn.ph_ac_nta: ac_nta,
            self.rnn.ph_adv_nt: adv_nt,
            self.rnn.ph_dn_nt: dn_nt
        })

        pass


def train_PG(
        exp_name,
        n_iter,
        gamma,
        min_timesteps_per_batch,
        step_num,
        max_path_length,
        learning_rate,
        reward_to_go,
        animate,
        logdir,
        normalize_advantages,
        nn_baseline,
        seed,
        n_layers,
        size,
        states_size,
        rnn_bias,
        rnn_test_nostates,
        factor):
    start = time.time()

    # ========================================================================================#
    # Set Up Logger
    # ========================================================================================#
    setup_logger(logdir, locals())

    # ========================================================================================#
    # Set Up Env
    # ========================================================================================#

    # Make the gym environment
    # env = gym.make(env_name)
    if 'partial' in exp_name and 'norm' in exp_name:
        env = Partial_Norm_Env(factor)
    elif 'partial' in exp_name:
        env = Partial_Env(factor)
    else:
        env = Env(factor)


    # Set random seeds
    tf.set_random_seed(seed)
    np.random.seed(seed)
    # env.seed(seed)
    env.seed(seed)

    # Maximum length for episodes
    max_path_length = max_path_length

    # Is this env continuous, or self.discrete?
    discrete = isinstance(env.action_space, gym.spaces.Discrete)

    # Observation and action sizes
    ob_dim = env.observation_space.shape[0]
    ac_dim = env.action_space.n if discrete else env.action_space.shape[0]

    # ========================================================================================#
    # Initialize Agent
    # ========================================================================================#
    computation_graph_args = {
        'n_layers': n_layers,
        'ob_dim': ob_dim,
        'ac_dim': ac_dim,
        'discrete': discrete,
        'size': size,
        'states_size': states_size,
        'learning_rate': learning_rate,
        'rnn_bias': rnn_bias
    }

    sample_trajectory_args = {
        'animate': animate,
        'max_path_length': max_path_length,
        'min_timesteps_per_batch': min_timesteps_per_batch,
        'step_num': step_num,
        'rnn_test_nostates': rnn_test_nostates
    }

    estimate_return_args = {
        'gamma': gamma,
        'reward_to_go': reward_to_go,
        'nn_baseline': nn_baseline,
        'normalize_advantages': normalize_advantages,
    }

    agent = Agent(computation_graph_args, sample_trajectory_args, estimate_return_args)

    # build computation graph
    agent.build_computation_graph()

    # tensorflow: config, session, variable initialization
    agent.init_tf_sess()

    # ========================================================================================#
    # Training Loop
    # ========================================================================================#

    total_timesteps = 0
    for itr in range(n_iter):
        print("********** Iteration %i ************" % itr)
        paths, timesteps_this_batch = agent.sample_trajectories(itr, env)
        total_timesteps += timesteps_this_batch

        # Build arrays for observation, action for the policy gradient update by concatenating
        # across paths
        ob_no = np.concatenate([path["observation"] for path in paths])
        ac_na = np.concatenate([path["action"] for path in paths])
        re_n = [path["reward"] for path in paths]
        dn_n = np.concatenate([path["termination"] for path in paths])

        q_n, adv_n = agent.estimate_return(ob_no, re_n)
        agent.update_parameters(ob_no, ac_na, q_n, adv_n, dn_n)

        # Log diagnostics
        returns = [path["reward"].sum() for path in paths]
        ep_lengths = [pathlength(path) for path in paths]
        logz.log_tabular("Time", time.time() - start)
        logz.log_tabular("Iteration", itr)
        logz.log_tabular("AverageReturn", np.mean(returns))
        logz.log_tabular("StdReturn", np.std(returns))
        logz.log_tabular("MaxReturn", np.max(returns))
        logz.log_tabular("MinReturn", np.min(returns))
        logz.log_tabular("EpLenMean", np.mean(ep_lengths))
        logz.log_tabular("EpLenStd", np.std(ep_lengths))
        logz.log_tabular("TimestepsThisBatch", timesteps_this_batch)
        logz.log_tabular("TimestepsSoFar", total_timesteps)
        logz.dump_tabular()
        logz.pickle_tf_vars()
    agent.save_variables(logdir)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--exp_name', type=str, default='pendulumNL_partial_norm')
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--discount', type=float, default=0.98)
    parser.add_argument('--n_iter', '-n', type=int, default=500)
    parser.add_argument('--batch_size', '-b', type=int, default=6000)
    parser.add_argument('--step_num', '-k', type=int, default=20)
    parser.add_argument('--ep_len', '-ep', type=float, default=200)
    parser.add_argument('--learning_rate', '-lr', type=float, default=1e-3)
    parser.add_argument('--factor', type=float, default=1e-1)
    parser.add_argument('--reward_to_go', '-rtg', action='store_true')
    parser.add_argument('--dont_normalize_advantages', '-dna', action='store_true')
    parser.add_argument('--nn_baseline', '-bl', action='store_true')
    parser.add_argument('--seed', type=int, default=2)
    parser.add_argument('--n_experiments', '-e', type=int, default=1)
    parser.add_argument('--n_layers', '-l', type=int, default=2)
    parser.add_argument('--size', '-s', type=int, default=16)
    parser.add_argument('--states_size', '-ss', type=int, default=16)
    parser.add_argument('--rnn_bias', '-rb', action='store_true')
    parser.add_argument('--rnn_test_nostates', '-rtns', action='store_true')
    args = parser.parse_args()
    args.env_name = 'rnn'


    if not (os.path.exists('data')):
        os.makedirs('data')
    logdir = args.exp_name + '_' + args.env_name + '_' + time.strftime("%d-%m-%Y_%H-%M-%S")
    logdir = os.path.join('data', logdir)
    if not (os.path.exists(logdir)):
        os.makedirs(logdir)

    max_path_length = args.ep_len if args.ep_len > 0 else None

    processes = []

    for e in range(args.n_experiments):
        seed = args.seed + 10 * e
        print('Running experiment with seed %d' % seed)

        def train_func():
            train_PG(
                exp_name=args.exp_name,
                n_iter=args.n_iter,
                gamma=args.discount,
                min_timesteps_per_batch=args.batch_size,
                step_num=args.step_num,
                max_path_length=max_path_length,
                learning_rate=args.learning_rate,
                reward_to_go=args.reward_to_go,
                animate=args.render,
                logdir=os.path.join(logdir, '%d' % seed),
                normalize_advantages=not (args.dont_normalize_advantages),
                nn_baseline=args.nn_baseline,
                seed=seed,
                n_layers=args.n_layers,
                size=args.size,
                states_size=args.states_size,
                rnn_bias=args.rnn_bias,
                rnn_test_nostates=args.rnn_test_nostates,
                factor=args.factor
            )

        # # Awkward hacky process runs, because Tensorflow does not like
        # # repeatedly calling train_PG in the same thread.
        p = Process(target=train_func, args=tuple())
        p.start()
        processes.append(p)
        # if you comment in the line below, then the loop will block
        # until this process finishes
        # p.join()

    for p in processes:
        p.join()


if __name__ == "__main__":
    main()
