from __future__ import division, print_function  # Python 2 compatibility

__author__ = "Julien Seznec"
__version__ = "0.1"

from math import sqrt, log
import numpy as np
import pandas as pd

np.seterr(divide='ignore')  # XXX dangerous in general, controlled here!

try:
    from .BasePolicy import BasePolicy
    from .IndexPolicy import IndexPolicy
    from .FEWA import FEWA, EFF_FEWA
    from .kullback import klucbBern
except ImportError:
    from BasePolicy import BasePolicy
    from FEWA import FEWA, EFF_FEWA
    from kullback import klucbBern
    from IndexPolicy import IndexPolicy


class EFF_RAWUCB(EFF_FEWA):
    """
    Efficient mechanism as described in [Seznec et al.,  2019a] (m=2) and [Seznec et al.,  2019b] (m<=2)
    Algorithm Rotting Adaptive Window Upper Confidence Bound (RAW-UCB) [Seznec et al.,  2019b]
    We use the confidence level \delta_t = \frac{1}{t^\alpha}.
    """

    def choice(self):
        not_selected = np.where(self.pulls == 0)[0]
        if len(not_selected):
            return not_selected[0]
        self.ucb = self._compute_ucb()
        return np.nanmin(self.ucb, axis=1).argmax()

    def _compute_ucb(self):
        delta_t_inv = self._confidence_level_inv()
        return (self.statistics[0, :, :] / self.windows + self.outlogconst * np.sqrt(np.log(delta_t_inv)))

    def _append_thresholds(self, w):
        # FEWA use two confidence bounds. Hence, the outlogconst is twice smaller for RAWUCB
        return sqrt(2 * self.subgaussian ** 2 / w)

    def __str__(self):
        return r"EFF_RAW-UCB($\alpha={:.3g}, \, m={:.3g}$)".format(self.alpha, self.grid)


class EFF_klRAWUCB(EFF_RAWUCB):
    def __init__(self, nbArms, subgaussian=1, alpha=1, klucb=klucbBern, tol=1e-4, m=2):
        super(EFF_klRAWUCB, self).__init__(nbArms=nbArms, subgaussian=subgaussian, alpha=alpha, m=m)
        self.c = alpha
        self.klucb_vec = np.vectorize(klucb, excluded=['precision'])
        self.tolerance = tol

    def choice(self):
        not_selected = np.where(self.pulls == 0)[0]
        if len(not_selected):
            return not_selected[0]
        self.ucb = self.klucb_vec(self.statistics[0, :, :] / self.windows, self.c * log(self.t + 1) / self.windows,
                                  precision=self.tolerance)
        return np.nanmin(self.ucb, axis=1).argmax()

    def __str__(self):
        return r"EFF_RAW-klUCB($c={:.3g}, \, m={:.3g}$)".format(self.alpha, self.grid)


class RAWUCB(EFF_RAWUCB):
    def __init__(self, nbArms, subgaussian=1, alpha=1):
        super(RAWUCB, self).__init__(nbArms=nbArms, subgaussian=subgaussian, alpha=alpha, m=1 + 1e-15)

    def __str__(self):
        return r"RAW-UCB($\alpha={:.3g}$)".format(self.alpha)


class EFF_RAWUCB_asymptotic(EFF_RAWUCB):
    """
    Efficient mechanism as described in [Seznec et al.,  2019a] (m=2) and [Seznec et al.,  2019b] (m<=2)
    Algorithm Rotting Adaptive Window Upper Confidence Bound (RAW-UCB) [Seznec et al.,  2019b]
    We use the confidence level \delta_t = \frac{1}{t(1+log(t)^\Beta)}.
    $\Beta=2$ corresponds to an asymptotic optimal tuning of UCB (Lattimore et Czebesvari's Bandit Book)
    """

    def __init__(self, nbArms, subgaussian=1, beta=2, m =2):
        super(EFF_RAWUCB_asymptotic, self).__init__(nbArms=nbArms, subgaussian=subgaussian, alpha=1, m=m)
        self.beta = beta

    def __str__(self):
        print(self.beta)
        return r"EFF-RAW-UCB($\delta_t=\frac{1}{t(1+log(t)^{:.3g}}$)".format(self.beta)

    def _confidence_level_inv(self):
        return self.t ** self.alpha * (1 + np.log(self.t) ** self.beta)


if __name__ == "__main__":
    # Code for debugging purposes.
    HORIZON = 50000
    sigma = 1
    policy = EFF_RAWUCB(5, subgaussian=sigma, alpha=1., m=1.1)
    reward = {0: 0., 1: 0.2, 2: 0.4, 3: 0.6, 4: 0.8}
    for t in range(HORIZON):
        choice = policy.choice()
        policy.getReward(choice, reward[choice])
    print(policy.statistics[0, :, :])
    print(policy.statistics.shape)
    print(policy.windows)
    print(policy.pulls)
