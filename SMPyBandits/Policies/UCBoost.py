# -*- coding: utf-8 -*-
""" The UCBoost policy for one-parameter exponential distributions.

- Reference: [Fang Liu et al, 2018](https://arxiv.org/abs/1804.05929).

.. warning:: The whole goal of their paper is to provide a numerically efficient alternative to kl-UCB, so for my comparison to be fair, I should either use the Python versions of klUCB utility functions (using :mod:`kullback`) or write C or Cython versions of this UCBoost module. TODO!
"""
from __future__ import division, print_function  # Python 2 compatibility

__author__ = "Lilian Besson"
__version__ = "0.9"

import numpy as np
np.seterr(divide='ignore')  # XXX dangerous in general, controlled here!


from .IndexPolicy import IndexPolicy

try:
    from .usenumba import jit  # Import numba.jit or a dummy jit(f)=f
except (ValueError, ImportError, SystemError):
    from usenumba import jit  # Import numba.jit or a dummy jit(f)=f


#: Default value for the constant c used in the computation of the index
# c = 0.  #: Default value for better practical performance.
c = 3.  #: Default value for the theorems to hold.


#: Tolerance when checking (with ``assert``) that the solution(s) of any convex problem are correct.
tolerance_with_upperbound = 1.0001


#: Whether to check that the solution(s) of any convex problem are correct.
CHECK_SOLUTION = True
CHECK_SOLUTION = False  # XXX Faster!

# --- New distance and algorithm: quadratic

# @jit
def squadratic_distance(p, q):
    r"""The *quadratic distance*, :math:`d_{sq}(p, q) := 2 (p - q)^2`."""
    p = np.minimum(np.maximum(p, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    q = np.minimum(np.maximum(q, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    return 2 * (p - q)**2


# @jit
def solution_pb_sq(p, upperbound, check_solution=CHECK_SOLUTION):
    r"""Closed-form solution of the following optimisation problem, for :math:`d = d_{sq}` the :func:`biquadratic_distance` function:

    .. math::

        P_1(d)(p, \delta): & \max_{q \in \Theta} q,\\
        \text{such that }  & d(p, q) \leq \delta.

    .. math::

        q^* = \min(1, p + \sqrt{-\frac{9}{4} + \sqrt{\sqrt{81}{16} + \sqrt{9}{4} \delta}).

    - :math:`\delta` is the ``upperbound`` parameter on the semi-distance between input :math:`p` and solution :math:`q^*`.
    """
    if np.any(upperbound) < 0:
        return np.ones_like(p) * np.nan
    q_star = p + np.sqrt(upperbound / 2.)
    if check_solution and not np.all(squadratic_distance(p, q_star) <= tolerance_with_upperbound * upperbound):
        print("Error: the solution to the optimisation problem P_1(d_sq), with p = {:.3g} and delta = {:.3g} was computed to be q^* = {:.3g} which seem incorrect (sq(p,q^*) = {:.3g} > {:.3g})...".format(p, upperbound, q_star, squadratic_distance(p, q_star), upperbound))  # DEBUG
    return q_star


# --- New distance and algorithm: biquadratic

# @jit
def biquadratic_distance(p, q):
    r"""The *biquadratic distance*, :math:`d_{bq}(p, q) := 2 (p - q)^2 + (4/9) * (p - q)^4`."""
    # return 2 * (p - q)**2 + (4./9) * (p - q)**4
    # XXX about 20% slower than the second less naive solution
    p = np.minimum(np.maximum(p, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    q = np.minimum(np.maximum(q, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    d = 2 * (p - q)**2
    return d + d**2 / 9.


# @jit
def solution_pb_bq(p, upperbound, check_solution=CHECK_SOLUTION):
    r"""Closed-form solution of the following optimisation problem, for :math:`d = d_{bq}` the :func:`biquadratic_distance` function:

    .. math::

        P_1(d_{bq})(p, \delta): & \max_{q \in \Theta} q,\\
        \text{such that }  & d_{bq}(p, q) \leq \delta.

    .. math::

        q^* = \min(1, p + \sqrt{-\frac{9}{4} + \sqrt{\sqrt{81}{16} + \sqrt{9}{4} \delta}).

    - :math:`\delta` is the ``upperbound`` parameter on the semi-distance between input :math:`p` and solution :math:`q^*`.
    """
    if np.any(upperbound) < 0:
        return np.ones_like(p) * np.nan
    p = np.minimum(np.maximum(p, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    # DONE is it faster to precompute the constants ? yes, about 12% faster
    # q_star = np.minimum(1, p + np.sqrt(-9./4 + np.sqrt(81./16 + 9./4 * upperbound)))
    q_star = np.minimum(1, p + np.sqrt(-2.25 + np.sqrt(5.0625 + 2.25 * upperbound)))
    if check_solution and not np.all(biquadratic_distance(p, q_star) <= tolerance_with_upperbound * upperbound):
        print("Error: the solution to the optimisation problem P_1(d_bq), with p = {:.3g} and delta = {:.3g} was computed to be q^* = {:.3g} which seem incorrect (bq(p,q^*) = {:.3g} > {:.3g})...".format(p, upperbound, q_star, biquadratic_distance(p, q_star), upperbound))  # DEBUG
    return q_star


class UCB_bq(IndexPolicy):
    """ The UCB(d_bq) policy for one-parameter exponential distributions.

    - It uses :func:`solution_pb_bq` as a closed-form solution to compute the UCB indexes (using the biquadratic distance).
    - Reference: [Fang Liu et al, 2018](https://arxiv.org/abs/1804.05929).
    """

    def __init__(self, nbArms, c=c, lower=0., amplitude=1.):
        super(UCB_bq, self).__init__(nbArms, lower=lower, amplitude=amplitude)
        self.c = c  #: Parameter c

    def __str__(self):
        return r"${}$($c={:.3g}$)".format(r"\mathrm{UCB}_{bq}", self.c)

    def computeIndex(self, arm):
        r""" Compute the current index, at time t and after :math:`N_k(t)` pulls of arm k:

        .. math::

            \hat{\mu}_k(t) &= \frac{X_k(t)}{N_k(t)}, \\
            I_k(t) &= P_1(d_{bq})(\hat{\mu}_k(t), \frac{\log(t) + c\log(\log(t))}{N_k(t)}).
        """
        if self.pulls[arm] < 1:
            return float('+inf')
        return solution_pb_bq(self.rewards[arm] / self.pulls[arm], (np.log(self.t) + self.c * np.log(max(1, np.log(self.t)))) / self.pulls[arm])

    # TODO make this vectorized function working!
    # def computeAllIndex(self):
    #     """ Compute the current indexes for all arms, in a vectorized manner."""
    #     indexes = solution_pb_bq(self.rewards / self.pulls, (np.log(self.t) + self.c * np.log(max(1, np.log(self.t)))) / self.pulls)
    #     indexes[self.pulls < 1] = float('+inf')
    #     self.index[:] = indexes


# --- New distance and algorithm: Hellinger


# @jit
def hellinger_distance(p, q):
    r"""The *Hellinger distance*, :math:`d_{h}(p, q) := (\sqrt{p} - \sqrt{q})^2 + (\sqrt{1 - p} - \sqrt{1 - q})^2`."""
    p = np.minimum(np.maximum(p, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    q = np.minimum(np.maximum(q, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    return (np.sqrt(p) - np.sqrt(q))**2 + (np.sqrt(1. - p) - np.sqrt(1. - q))**2


# @jit
def solution_pb_hellinger(p, upperbound, check_solution=CHECK_SOLUTION):
    r"""Closed-form solution of the following optimisation problem, for :math:`d = d_{h}` the :func:`hellinger_distance` function:

    .. math::

        P_1(d_h)(p, \delta): & \max_{q \in \Theta} q,\\
        \text{such that }  & d_h(p, q) \leq \delta.

    .. math::

        q^* = \left( (1 - \frac{\delta}{2}) \sqrt{p} + \sqrt{(1 - p) (\delta - \frac{\delta^2}{4})} \right)^{2 \times \boldsymbol{1}(\delta < 2 - 2 \sqrt{p})}.

    - :math:`\delta` is the ``upperbound`` parameter on the semi-distance between input :math:`p` and solution :math:`q^*`.
    """
    if np.any(upperbound < 0):
        return np.ones_like(p) * np.nan
    # DONE is it faster to precompute the constants ? yes, about 12% faster
    p = np.minimum(np.maximum(p, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    sqrt_p = np.sqrt(p)
    if np.any(upperbound < (2 - 2 * sqrt_p)):
        q_star = (1 - upperbound/2.) * sqrt_p + np.sqrt((1 - p) * (upperbound - upperbound**2 / 4.)) ** 2
    else:
        q_star = np.ones_like(p)
    if check_solution and not np.all(hellinger_distance(p, q_star) <= tolerance_with_upperbound * upperbound):
        print("Error: the solution to the optimisation problem P_1(d_h), with p = {:.3g} and delta = {:.3g} was computed to be q^* = {:.3g} which seem incorrect (h(p,q^*) = {:.3g} > {:.3g})...".format(p, upperbound, q_star, hellinger_distance(p, q_star), upperbound))  # DEBUG
    return q_star


class UCB_h(IndexPolicy):
    """ The UCB(d_h) policy for one-parameter exponential distributions.

    - It uses :func:`solution_pb_hellinger` as a closed-form solution to compute the UCB indexes (using the Hellinger distance).
    - Reference: [Fang Liu et al, 2018](https://arxiv.org/abs/1804.05929).
    """

    def __init__(self, nbArms, c=c, lower=0., amplitude=1.):
        super(UCB_h, self).__init__(nbArms, lower=lower, amplitude=amplitude)
        self.c = c  #: Parameter c

    def __str__(self):
        return r"${}$($c={:.3g}$)".format(r"\mathrm{UCB}_{h}", self.c)

    def computeIndex(self, arm):
        r""" Compute the current index, at time t and after :math:`N_k(t)` pulls of arm k:

        .. math::

            \hat{\mu}_k(t) &= \frac{X_k(t)}{N_k(t)}, \\
            I_k(t) &= P_1(d_h)(\hat{\mu}_k(t), \frac{\log(t) + c\log(\log(t))}{N_k(t)}).
        """
        if self.pulls[arm] < 1:
            return float('+inf')
        return solution_pb_hellinger(self.rewards[arm] / self.pulls[arm], (np.log(self.t) + self.c * np.log(max(1, np.log(self.t)))) / self.pulls[arm])

    # TODO make this vectorized function working!
    # def computeAllIndex(self):
    #     """ Compute the current indexes for all arms, in a vectorized manner."""
    #     indexes = solution_pb_hellinger(self.rewards / self.pulls, (np.log(self.t) + self.c * np.log(max(1, np.log(self.t)))) / self.pulls)
    #     indexes[self.pulls < 1] = float('+inf')
    #     self.index[:] = indexes


# --- New distance and algorithm: lower-bound on the Kullback-Leibler distance


eps = 1e-15  #: Threshold value: everything in [0, 1] is truncated to [eps, 1 - eps]


# @jit
def kullback_leibler_distance(p, q):
    r""" Kullback-Leibler divergence for Bernoulli distributions. https://en.wikipedia.org/wiki/Bernoulli_distribution#Kullback.E2.80.93Leibler_divergence

    .. math:: kl(p, q) = \mathrm{KL}(\mathcal{B}(p), \mathcal{B}(q)) = p \log(\frac{p}{q}) + (1-p) \log(\frac{1-p}{1-q}).
    """
    p = np.minimum(np.maximum(p, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    q = np.minimum(np.maximum(q, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    return p * np.log(p / q) + (1 - p) * np.log((1 - p) / (1 - q))


# @jit
def kullback_leibler_distance_lowerbound(p, q):
    r""" Lower-bound on the Kullback-Leibler divergence for Bernoulli distributions. https://en.wikipedia.org/wiki/Bernoulli_distribution#Kullback.E2.80.93Leibler_divergence

    .. math:: d_{lb}(p, q) = p \log(\frac{p}{q}) + (1-p) \log(\frac{1-p}{1-q}).
    """
    p = np.minimum(np.maximum(p, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    q = np.minimum(np.maximum(q, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    return p * np.log(p) + (1 - p) * np.log((1 - p) / (1 - q))


# @jit
def solution_pb_kllb(p, upperbound, check_solution=CHECK_SOLUTION):
    r"""Closed-form solution of the following optimisation problem, for :math:`d = d_{lb}` the proposed lower-bound on the Kullback-Leibler binary distance (:func:`kullback_leibler_distance_lowerbound`) function:

    .. math::

        P_1(d_{lb})(p, \delta): & \max_{q \in \Theta} q,\\
        \text{such that }  & d_{lb}(p, q) \leq \delta.

    .. math::

        q^* = 1 - (1 - p) \exp(\frac{p \log(p) - \delta}{1 - p}).

    - :math:`\delta` is the ``upperbound`` parameter on the semi-distance between input :math:`p` and solution :math:`q^*`.
    """
    if np.any(upperbound < 0):
        return np.ones_like(p) * np.nan
    p = np.minimum(np.maximum(p, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    one_m_p = 1 - p
    q_star = 1 - one_m_p * np.exp((p * np.log(p) - upperbound) / one_m_p)
    if check_solution and not np.all(kullback_leibler_distance_lowerbound(p, q_star) <= tolerance_with_upperbound * upperbound):
        print("Error: the solution to the optimisation problem P_1(d_lb), with p = {:.3g} and delta = {:.3g} was computed to be q^* = {:.3g} which seem incorrect (h(p,q^*) = {:.3g} > {:.3g})...".format(p, upperbound, q_star, kullback_leibler_distance_lowerbound(p, q_star), upperbound))  # DEBUG
    return q_star


class UCB_lb(IndexPolicy):
    """ The UCB(d_lb) policy for one-parameter exponential distributions.

    - It uses :func:`solution_pb_kllb` as a closed-form solution to compute the UCB indexes (using the lower-bound on the Kullback-Leibler distance).
    - Reference: [Fang Liu et al, 2018](https://arxiv.org/abs/1804.05929).
    """

    def __init__(self, nbArms, c=c, lower=0., amplitude=1.):
        super(UCB_lb, self).__init__(nbArms, lower=lower, amplitude=amplitude)
        self.c = c  #: Parameter c

    def __str__(self):
        return r"${}$($c={:.3g}$)".format(r"\mathrm{UCB}_{lb}", self.c)

    def computeIndex(self, arm):
        r""" Compute the current index, at time t and after :math:`N_k(t)` pulls of arm k:

        .. math::

            \hat{\mu}_k(t) &= \frac{X_k(t)}{N_k(t)}, \\
            I_k(t) &= P_1(d_lb)(\hat{\mu}_k(t), \frac{\log(t) + c\log(\log(t))}{N_k(t)}).
        """
        if self.pulls[arm] < 1:
            return float('+inf')
        return solution_pb_kllb(self.rewards[arm] / self.pulls[arm], (np.log(self.t) + self.c * np.log(max(1, np.log(self.t)))) / self.pulls[arm])

    # TODO make this vectorized function working!
    # def computeAllIndex(self):
    #     """ Compute the current indexes for all arms, in a vectorized manner."""
    #     indexes = solution_pb_kllb(self.rewards / self.pulls, (np.log(self.t) + self.c * np.log(max(1, np.log(self.t)))) / self.pulls)
    #     indexes[self.pulls < 1] = float('+inf')
    #     self.index[:] = indexes


# --- New distance and algorithm: a shifted tangent line function of d_kl


# @jit
def distance_t(p, q):
    r""" A shifted tangent line function of :func:`kullback_leibler_distance`.

    .. math:: d_t(p, q) = p \log(\frac{p}{q}) + (1-p) \log(\frac{1-p}{1-q}).
    """
    p = np.minimum(np.maximum(p, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    q = np.minimum(np.maximum(q, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    # XXX this could be optimized!
    return (2 * q) / (p + 1) + p * np.log(p / (p + 1)) + np.log(2 / (p + 1)) - 1.


# @jit
def solution_pb_t(p, upperbound, check_solution=CHECK_SOLUTION):
    r"""Closed-form solution of the following optimisation problem, for :math:`d = d_t` a shifted tangent line function of :func:`kullback_leibler_distance` (:func:`distance_t`) function:

    .. math::

        P_1(d_t)(p, \delta): & \max_{q \in \Theta} q,\\
        \text{such that }  & d_t(p, q) \leq \delta.

    .. math::

        q^* = \min(1, \frac{p + 1}{2} \left( \delta - p \log\left\frac{p}{p + 1}\right) - \log\left(\frac{2}{\mathrm{e} (p + 1)}\right) \right)).

    - :math:`\delta` is the ``upperbound`` parameter on the semi-distance between input :math:`p` and solution :math:`q^*`.
    """
    p = np.minimum(np.maximum(p, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    if np.any(upperbound < 0):
        return np.ones_like(p) * np.nan
    q_star = np.minimum(1, ((p + 1) / 2.) * (upperbound - p * np.log(p / (p + 1)) - np.log(2 / (1 + p)) + 1))
    if check_solution and not np.all(distance_t(p, q_star) <= tolerance_with_upperbound * upperbound):
        print("Error: the solution to the optimisation problem P_1(d_t), with p = {:.3g} and delta = {:.3g} was computed to be q^* = {:.3g} which seem incorrect (h(p,q^*) = {:.3g} > {:.3g})...".format(p, upperbound, q_star, distance_t(p, q_star), upperbound))  # DEBUG
    return q_star


class UCB_t(IndexPolicy):
    """ The UCB(d_t) policy for one-parameter exponential distributions.

    - It uses :func:`solution_pb_t` as a closed-form solution to compute the UCB indexes (using the a shifted tangent line function of :func:`kullback_leibler_distance`).
    - Reference: [Fang Liu et al, 2018](https://arxiv.org/abs/1804.05929).
    """

    def __init__(self, nbArms, c=c, lower=0., amplitude=1.):
        super(UCB_t, self).__init__(nbArms, lower=lower, amplitude=amplitude)
        self.c = c  #: Parameter c

    def __str__(self):
        return r"${}$($c={:.3g}$)".format(r"\mathrm{UCB}_{t}", self.c)

    def computeIndex(self, arm):
        r""" Compute the current index, at time t and after :math:`N_k(t)` pulls of arm k:

        .. math::

            \hat{\mu}_k(t) &= \frac{X_k(t)}{N_k(t)}, \\
            I_k(t) &= P_1(d_t)(\hat{\mu}_k(t), \frac{\log(t) + c\log(\log(t))}{N_k(t)}).
        """
        if self.pulls[arm] < 1:
            return float('+inf')
        return solution_pb_t(self.rewards[arm] / self.pulls[arm], (np.log(self.t) + self.c * np.log(max(1, np.log(self.t)))) / self.pulls[arm])

    # TODO make this vectorized function working!
    # def computeAllIndex(self):
    #     """ Compute the current indexes for all arms, in a vectorized manner."""
    #     indexes = solution_pb_t(self.rewards / self.pulls, (np.log(self.t) + self.c * np.log(max(1, np.log(self.t)))) / self.pulls)
    #     indexes[self.pulls < 1] = float('+inf')
    #     self.index[:] = indexes


# --- Now the generic UCBoost algorithm

try:
    from numbers import Number
    def is_a_true_number(n):
        """Check if n is a number or not (``int``, ``float``, ``complex`` etc, any instance of :py:class:`numbers.Number` class."""
        return isinstance(n, Number)
except ImportError:
    print("Warning: the numbers.Number abstract class should be available for both Python 2 and 3. It is VERY weird that it is not!\nPlease fill an issue here, if you can, https://github.com/SMPyBandits/SMPyBandits/issues/new")
    def is_a_true_number(n):
        """Check if n is a number or not (``int``, ``float``, ``complex`` etc, any instance of :py:class:`numbers.Number` class."""
        try:
            float(n)
            return True
        except:
            return False


# This is a hack, so that we can store a list of functions in the UCBoost algorithm,
# without actually storing functions (which are unhashable).
_distance_of_key = {
    'solution_pb_sq': solution_pb_sq,
    'solution_pb_bq': solution_pb_bq,
    'solution_pb_hellinger': solution_pb_hellinger,
    'solution_pb_kllb': solution_pb_kllb,
    'solution_pb_t': solution_pb_t,
}


class UCBoost(IndexPolicy):
    """ The UCBoost policy for one-parameter exponential distributions.

    - It is quite simple: using a set of kl-dominated and candidate semi-distances D, the UCB index for each arm (at each step) is computed as the *smallest* upper confidence bound given (for this arm at this time t) for each distance d.
    - ``set_D`` should be either a set of *strings* (and NOT functions), or a number (3, 4 or 5). 3 indicate using ``d_bq``, ``d_h``, ``d_lb``, 4 adds ``d_t``, and 5 adds ``d_sq`` (see the article, Corollary 3, p5, for more details).
    - Reference: [Fang Liu et al, 2018](https://arxiv.org/abs/1804.05929).
    """

    def __init__(self, nbArms, set_D=None, c=c, lower=0., amplitude=1.):
        super(UCBoost, self).__init__(nbArms, lower=lower, amplitude=amplitude)

        # FIXED having a set of functions as attribute will make this object unhashable! that's bad for pickling and parallelization!
        # DONE One solution is to store keys, and look up the functions in a fixed (hidden) dictionary
        if set_D is None:
            set_D = 4
        if is_a_true_number(set_D):
            assert set_D in {3, 4, 5}, "Error: if set_D is an integer, it should be 3 or 4 or 5."
            if set_D == 3:
                set_D = ["solution_pb_bq", "solution_pb_hellinger", "solution_pb_kllb"]
            elif set_D == 4:
                set_D = ["solution_pb_bq", "solution_pb_hellinger", "solution_pb_kllb", "solution_pb_t"]
            elif set_D == 5:
                set_D = ["solution_pb_sq", "solution_pb_bq", "solution_pb_hellinger", "solution_pb_kllb", "solution_pb_t"]
        assert all(key in _distance_of_key for key in set_D), "Error: one key in set_D = {} was found to not correspond to a distance (list of possible keys are {}).".format(set_D, list(_distance_of_key.keys()))  # DEBUG

        self.set_D = set_D  #: Set of *strings* that indicate which d functions are in the set of functions D. Warning: do not use real functions here, or the object won't be hashable!
        self.c = c  #: Parameter c

    def __str__(self):
        return r"UCBoost($|D|={}$, $c={:.3g}$)".format(len(self.set_D), self.c)

    def computeIndex(self, arm):
        r""" Compute the current index, at time t and after :math:`N_k(t)` pulls of arm k:

        .. math::

            \hat{\mu}_k(t) &= \frac{X_k(t)}{N_k(t)}, \\
            I_k(t) &= \min_{d\in D} P_1(d)(\hat{\mu}_k(t), \frac{\log(t) + c\log(\log(t))}{N_k(t)}).
        """
        if self.pulls[arm] < 1:
            return float('+inf')
        p = self.rewards[arm] / self.pulls[arm]
        upperbound = (np.log(self.t) + self.c * np.log(max(1, np.log(self.t)))) / self.pulls[arm]
        return min(
            _distance_of_key[key](p, upperbound)
            for key in self.set_D
        )

    # TODO make this vectorized function working!
    # def computeAllIndex(self):
    #     """ Compute the current indexes for all arms, in a vectorized manner."""
    #     indexes = self.klucb(self.rewards / self.pulls, self.c * np.log(self.t) / self.pulls, self.tolerance)
    #     indexes[self.pulls < 1] = float('+inf')
    #     self.index[:] = indexes


# --- New distance and algorithm: epsilon approximation on the Kullback-Leibler distance

def solutions_pb_from_epsilon(p, upperbound, epsilon=0.001, check_solution=CHECK_SOLUTION):
    r"""List of closed-form solutions of the following optimisation problems, for :math:`d = d_s^k` approximation of :math:`d_{kl}` and any :math:`\tau_1(p) \leq k \leq \tau_2(p)`:

    .. math::

        P_1(d_s^k)(p, \delta): & \max_{q \in \Theta} q,\\
        \text{such that }  & d_s^k(p, q) \leq \delta.

    .. math::

        q^* &= q_k^{\boldsymbol{1}(\delta < d_{kl}(p, q_k))},\\
        d_s^k &: (p, q) \mapsto d_{kl}(p, q_k) \boldsymbol{1}(q > q_k),\\
        q_k &:= 1 - (1 - \frac{\varepsilon}{1 + \varepsilon})^k.

    - :math:`\delta` is the ``upperbound`` parameter on the semi-distance between input :math:`p` and solution :math:`q^*`.
    """
    assert 0 < epsilon < 1, "Error: epsilon should be in (0, 1) strictly, but = {:.3g} is not!".format(epsilon)  # DEBUG
    # eta doesn't depend on p
    eta = epsilon / (1.0 + epsilon)
    # tau_1 and tau_2 depend on p
    p = np.minimum(np.maximum(p, eps), 1 - eps)  # XXX project [0,1] to [eps,1-eps]
    tau_1_p = np.ceil((np.log(1 - p)) / (np.log(1 - eta)))
    tau_2_p = np.ceil((np.log(1 - np.exp(- epsilon / p))) / (np.log(1 - eta)))
    # if tau_1_p > tau_2_p:
    #     print("Error: tau_1_p = {:.3g} should be <= tau_2_p = {:.3g}...".format(tau_1_p, tau_2_p))  # DEBUG

    # now construct all the k, and all the step kl functions
    # WARNING yes we could inline all this for speedup, but this would require recomputing for the check_solution...
    list_of_k = np.arange(tau_1_p, tau_2_p + 1)
    list_of_qk = 1 - (1.0 - eta) ** list_of_k

    list_of_solution_pb_step_kl = [  # q_k ** (indic(delta <= kl(p, q_k)))
        qk
        if upperbound < kullback_leibler_distance(p, qk) else 1
        for k, qk in zip(list_of_k, list_of_qk)
    ]
    # XXX yes yes, we could write a generator, or directly return the minimum,
    # but this is not the bottleneck of the efficiency of this code !

    # XXX actually, we don't need to compute the step kl functions! only to check
    if check_solution:
        for k, qk, qk_star in zip(list_of_k, list_of_qk, list_of_solution_pb_step_kl):
            distance_step_kl = lambda p, q: kullback_leibler_distance(p, q) if q >= qk else 0
            if not np.all(distance_step_kl(p, qk_star) <= tolerance_with_upperbound * upperbound):
                print("Error: the solution to the optimisation problem P_1(d_s^k) for k = {} and q_k = {:.3g}, with p = {:.3g} and delta = {:.3g} was computed to be q^* = {:.3g} which seem incorrect (h(p,q^*) = {:.3g} > {:.3g})...".format(k, qk, p, upperbound, qk_star, distance_t(p, qk_star), upperbound))  # DEBUG

    return list_of_solution_pb_step_kl


class UCBoostEpsilon(IndexPolicy):
    """ The UCBoostEpsilon policy for one-parameter exponential distributions.

    - It is quite simple: using a set of kl-dominated and candidate semi-distances D, the UCB index for each arm (at each step) is computed as the *smallest* upper confidence bound given (for this arm at this time t) for each distance d.
    - This variant uses :func:`solutions_pb_from_epsilon` to also compute the :math:`\varepsilon` approximation of the :func:`kullback_leibler_distance` function (see the article for details, Th.3 p6).
    - Reference: [Fang Liu et al, 2018](https://arxiv.org/abs/1804.05929).
    """

    def __init__(self, nbArms, epsilon=0.01, c=c, lower=0., amplitude=1.):
        super(UCBoostEpsilon, self).__init__(nbArms, lower=lower, amplitude=amplitude)

        # FIXED having a set of functions as attribute will make this object unhashable! that's bad for pickling and parallelization!
        # DONE One solution is to store keys, and look up the functions in a fixed (hidden) dictionary
        set_D = ["solution_pb_sq", "solution_pb_kllb"]

        self.set_D = set_D  #: Set of *strings* that indicate which d functions are in the set of functions D. Warning: do not use real functions here, or the object won't be hashable!
        self.c = c  #: Parameter c
        self.epsilon = epsilon  #: Parameter epsilon

    def __str__(self):
        return r"UCBoost($\varpesilon={:.3g}$, $c={:.3g}$)".format(self.epsilon, self.c)

    def computeIndex(self, arm):
        r""" Compute the current index, at time t and after :math:`N_k(t)` pulls of arm k:

        .. math::

            \hat{\mu}_k(t) &= \frac{X_k(t)}{N_k(t)}, \\
            I_k(t) &= \min_{d\in D} P_1(d)(\hat{\mu}_k(t), \frac{\log(t) + c\log(\log(t))}{N_k(t)}).
        """
        if self.pulls[arm] < 1:
            return float('+inf')

        p = self.rewards[arm] / self.pulls[arm]
        upperbound = (np.log(self.t) + self.c * np.log(max(1, np.log(self.t)))) / self.pulls[arm]

        min_solutions_pb_from_epsilon = float('+inf')
        sols = solutions_pb_from_epsilon(p, upperbound, epsilon=self.epsilon)
        if len(sols) > 0:
            min_solutions_pb_from_epsilon = min(sols)
        return min(
            min(
                _distance_of_key[key](p, upperbound)
                for key in self.set_D
            ),
            min_solutions_pb_from_epsilon
        )


    # TODO make this vectorized function working!
    # def computeAllIndex(self):
    #     """ Compute the current indexes for all arms, in a vectorized manner."""
    #     indexes = self.klucb(self.rewards / self.pulls, self.c * np.log(self.t) / self.pulls, self.tolerance)
    #     indexes[self.pulls < 1] = float('+inf')
    #     self.index[:] = indexes