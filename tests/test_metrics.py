import numpy as np
import pandas as pd
import pytest

from pycarlo.metrics import summarize


def test_intermediate_deficit_requires_cash_even_with_positive_final_balance():
    dates = pd.date_range("2026-01-02", periods=2, freq="D")
    balances = np.array([
        [-10.0, 20.0],
        [-4.0, 5.0],
        [1.0, 2.0],
        [2.0, 3.0],
    ])
    metrics, daily, _, paths = summarize("A", dates, balances, confidence=0.75, bins=4)
    row = metrics.iloc[0]
    assert row.probabilidade_saldo_final_negativo == 0.0
    assert row.probabilidade_ruptura == 0.5
    assert row.cenarios_saldo_final_negativo == 0
    assert row.cenarios_com_ruptura == 2
    assert row.saldo_final_p5 == pytest.approx(2.15)
    assert row.saldo_final_p50 == pytest.approx(4.0)
    assert row.saldo_final_p95 == pytest.approx(17.75)
    assert daily.iloc[0].p50 == pytest.approx(-1.5)
    assert row.caixa_adicional == pytest.approx(5.5)
    assert row.caixa_adicional > max(0.0, -row.saldo_final_p5)
    assert row.data_maior_risco == "2026-01-02"
    assert row.primeira_data_com_risco == "2026-01-02"
    assert daily.probabilidade_saldo_negativo.tolist() == [0.5, 0.0]
    assert paths.pior_saldo_diario.tolist() == [-10.0, -4.0, 1.0, 2.0]


def test_no_deficit_has_no_critical_date():
    dates = pd.date_range("2026-01-02", periods=2, freq="D")
    balances = np.array([[1.0, 3.0], [2.0, 4.0]])
    metrics, _, _, _ = summarize("A", dates, balances, confidence=0.95, bins=2)
    row = metrics.iloc[0]
    assert row.maior_risco_diario == 0.0
    assert row.data_maior_risco == ""
    assert row.datas_maior_risco == ""
    assert row.primeira_data_com_risco == ""
    assert row.caixa_adicional == 0.0
