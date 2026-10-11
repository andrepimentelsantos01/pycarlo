"""Amostragem empírica das safras de erro, sem distribuição paramétrica."""
from __future__ import annotations

import numpy as np


def sample_vintages(factors: np.ndarray, simulations: int, rng: np.random.Generator) -> np.ndarray:
    """Amostra uma safra inteira por cenário, preservando covariação observada."""
    if factors.ndim != 2 or factors.shape[0] == 0:
        raise ValueError("calibracao: matriz de safras vazia")
    return rng.integers(0, factors.shape[0], size=simulations)
