# -*- coding: utf-8 -*-
""" Environment module :

- :class:`MAB`, :class:`MarkovianMAB` and :class:`DynamicMAB` objects, used to wrap the problems (list of arms).
- :class:`Result` and :class:`ResultMultiPlayers` objects, used to wrap simulation results (list of decisions and rewards).
- :class:`Evaluator` environment, used to wrap simulation, for the single player case.
- :class:`EvaluatorMultiPlayers` environment, used to wrap simulation, for the multi-players case.
- :mod:`CollisionModels` implements different collision models.

And useful constants and functions for the plotting and stuff:

- :func:`DPI`, :func:`signature`, :func:`maximizeWindow`, :func:`palette`, :func:`makemarkers`, :func:`wraptext`: for plotting
- :func:`notify`: send a notificaiton
- :func:`Parallel`, :func:`delayed`: joblib related
- :func:`tqdm`: pretty range() loops
- :func:`sortedDistance`, :func:`fairnessMeasures`: science related
"""

__author__ = "Lilian Besson"
__version__ = "0.6"

from .MAB import MAB, MarkovianMAB, DynamicMAB

from .Result import Result
from .Evaluator import Evaluator

from .CollisionModels import *
from .ResultMultiPlayers import ResultMultiPlayers
from .EvaluatorMultiPlayers import EvaluatorMultiPlayers

from .plotsettings import DPI, signature, maximizeWindow, palette, makemarkers, wraptext

from .notify import notify

from .usejoblib import *
from .usetqdm import *

from .sortedDistance import *
from .fairnessMeasures import *
