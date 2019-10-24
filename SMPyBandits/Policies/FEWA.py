# -*- coding: utf-8 -*-
""" The Confidence Bound Filtering on Expanding Window Average policy for rotting bandits.
Reference: [Seznec et al.,  2018].
"""
from __future__ import division, print_function  # Python 2 compatibility

__author__ = "Julien Seznec"
__version__ = "0.1"

from math import sqrt, log
import numpy as np
import pandas as pd
np.seterr(divide='ignore')  # XXX dangerous in general, controlled here!

try:
    from .BasePolicy import BasePolicy
except ImportError:
    from BasePolicy import BasePolicy


class EFF_FEWA(BasePolicy):
    """
    Efficient mechanism as described in [Seznec et al.,  2019a] (m=2) and [Seznec et al.,  2019b] (m<=2)
    Algorithm Filtering on Expanding Window Average [Seznec et al.,  2019a]
    We use the confidence level \delta_t = \frac{1}{t^\alpha}.
     """
    def __init__(self, nbArms, alpha=0.06, subgaussian=1, m=2):
        super(EFF_FEWA, self).__init__(nbArms)
        self.alpha = alpha
        self.nbArms = nbArms
        self.subgaussian = subgaussian
        self.statistics = np.ones(shape=(3, self.nbArms, 2)) * np.nan
        # [0,:,:] : current statistics, [1,:,:]: pending statistics, [3,:,:]: number of sample in the pending statistics
        self.windows = np.array([1, int(np.ceil(m))])
        self.outlogconst = np.sqrt(self.windows * sqrt(8 * self.alpha * self.subgaussian ** 2))
        self.armSet = np.arange(nbArms)
        self.grid = m

    def __str__(self):
        return r"EFF_FEWA($\alpha={:.3g}, \, m={:.3g}$)".format(self.alpha, self.grid)

    def getReward(self, arm, reward):
        super(EFF_FEWA, self).getReward(arm, reward)
        if not np.all(np.isnan(self.statistics[0,:,-1])):
            self.statistics = np.append(self.statistics, np.nan * np.ones([3, self.nbArms, 1]), axis=2)
        while self.statistics.shape[2] > min([len(self.outlogconst), len(self.windows)]):
            self.windows = np.append(self.windows, int(np.ceil(self.windows[-1] * self.grid)))
            self.outlogconst = np.append(self.outlogconst, self._append_thresholds(self.windows[-1]))
        self.statistics[1, arm, 0] = reward
        self.statistics[2, arm, 0] = 1
        self.statistics[1, arm, 1:] += reward
        self.statistics[2, arm, 1:] += 1
        idx = np.where((self.statistics[2, arm, :] == self.windows))[0]
        self.statistics[0, arm, idx] = self.statistics[1, arm, idx]
        idx_nan = np.where(np.isnan(self.statistics[2, arm, :]))[0]
        idx = np.concatenate([idx, np.array([i for i in idx_nan if i - 1 in set(list(idx))]).astype(int)])
        self.statistics[1:, arm, idx[idx != 0]] = self.statistics[1:, arm, idx[idx != 0] - 1]

    def choice(self):
        remainingArms = self.armSet.copy()
        i = 0
        selected = remainingArms[np.isnan(self.statistics[0, :, i])]
        delta_inv = self._confidence_level_inv()
        sqrtlogt = np.sqrt(np.log(delta_inv))
        while len(selected) == 0 :
            thresh = np.max(self.statistics[0, remainingArms, i]) - sqrtlogt * self.outlogconst[i]
            remainingArms = remainingArms[self.statistics[0, remainingArms, i] >= thresh]
            i += 1
            selected = remainingArms[np.isnan(self.statistics[0, remainingArms, i])] if len(
                remainingArms) != 1 else remainingArms
        return selected[np.argmin(self.pulls[selected])]

    def _append_thresholds(self, w):
        return sqrt(8 * self.subgaussian ** 2 * w)

    def _confidence_level_inv(self):
        return self.t ** self.alpha


class FEWA(EFF_FEWA):
    """ Filtering on Expanding Window Average policy for rotting bandits.
    Reference: [Seznec et al.,  2019a].
    FEWA is equivalent to EFF_FEWA for m < 1+1/T.
    This implementation is valid for $T < 10^15$.
    For T>10^15, FEWA will have running time and memory issues as its time and space complexity is O(KT) per round.
    """
    def __init__(self, nbArms, subgaussian=1, alpha = 4):
        super(FEWA, self).__init__(nbArms, subgaussian=subgaussian, alpha=alpha, m = 1 + 10**(-15))

    def __str__(self):
        return r"FEWA($\alpha={:.3g}$)".format(self.alpha)




if __name__ == "__main__":
    # Code for debugging purposes.
    HORIZON = 20000
    sigma = 1
    policy = EFF_FEWA(5, subgaussian=sigma, alpha=0.06, m =1.1)
    reward = {0: 0, 1: 0.2, 2: 0.4, 3: 0.6, 4: 0.8}
    for t in range(HORIZON):
        choice = policy.choice()
        policy.getReward(choice, reward[choice])
    print(policy.statistics[0,:,:])
    print(policy.statistics.shape)
    print(policy.windows)
    print(len(policy.windows))
    print(policy.pulls)