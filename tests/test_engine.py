import numpy as np
import pandas as pd
import pytest

from pycarlo import SimulationConfig, run_simulation


AS_OF = pd.Timestamp("2026-01-01")


def _flows():
    return pd.DataFrame([
        {"empresa": "A", "componente": "vendas", "data": AS_OF + pd.Timedelta(days=day),
         "direcao": "entrada", "valor": 100.0, "classificacao": "previsto"}
        for day in (1, 8)
    ] + [{"empresa": "A", "componente": "folha", "data": AS_OF + pd.Timedelta(days=1),
          "direcao": "saida", "valor": 20.0, "classificacao": "conhecido"}])


def _history():
    rows = []
    for issued, factor in [("2025-06-01", 0.5), ("2025-07-01", 1.0), ("2025-08-01", 1.5)]:
        vintage = pd.Timestamp(issued)
        for week in (0, 1):
            rows.append({"empresa": "A", "componente": "vendas", "direcao": "entrada",
                         "data_previsao": vintage,
                         "data_alvo": vintage + pd.Timedelta(days=(week + 1) * 7),
                         "valor_previsto": 100.0, "valor_realizado": 100.0 * factor})
    return pd.DataFrame(rows)


def test_reproducible_and_known_flow_exact():
    config = SimulationConfig(weeks=2, simulations=50, seed=17, keep_paths=True)
    a = run_simulation(_flows(), {"A": 0.0}, AS_OF, _history(), config)
    b = run_simulation(_flows(), {"A": 0.0}, AS_OF, _history(), config)
    pd.testing.assert_frame_equal(a.paths, b.paths)
    first_day = a.paths.loc[a.paths.data == AS_OF + pd.Timedelta(days=1), "saldo"].to_numpy()
    assert set(first_day).issubset({30.0, 80.0, 130.0})
    assert len(a.path_summary) == 50
    assert a.status == "ok"


def test_incomplete_history_returns_diagnostic_without_metrics():
    history = _history().iloc[:-1]
    result = run_simulation(_flows(), {"A": 0.0}, AS_OF, history,
                            SimulationConfig(weeks=2, simulations=20))
    assert result.status == "historico_insuficiente"
    assert result.metrics.empty
    assert result.diagnostics.iloc[0].safras_completas == 2


def test_future_realizations_are_excluded():
    history = _history()
    history.loc[history.data_previsao == pd.Timestamp("2025-08-01"), "data_alvo"] += pd.Timedelta(days=200)
    result = run_simulation(_flows(), {"A": 0.0}, AS_OF, history,
                            SimulationConfig(weeks=2, simulations=20))
    assert result.status == "historico_insuficiente"


def test_known_only_is_deterministic_without_history():
    flows = _flows().loc[lambda df: df.classificacao == "conhecido"]
    result = run_simulation(flows, {"A": 30.0}, AS_OF, config=SimulationConfig(weeks=2, simulations=10))
    assert result.status == "ok"
    assert result.metrics.iloc[0].probabilidade_ruptura == 0.0
    assert np.allclose(result.path_summary.saldo_final, 10.0)


def test_overlap_is_rejected():
    flows = _flows()
    overlap = flows.iloc[[0]].copy()
    overlap["classificacao"] = "conhecido"
    with pytest.raises(ValueError, match="duplicada ou sobreposta"):
        run_simulation(pd.concat([flows, overlap]), {"A": 0.0}, AS_OF)


def test_companies_are_isolated():
    flows = _flows()
    other = flows.copy()
    other["empresa"] = "B"
    history = _history()
    result = run_simulation(pd.concat([flows, other]), {"A": 0.0, "B": 0.0}, AS_OF,
                            history, SimulationConfig(weeks=2, simulations=20))
    assert result.status == "parcial"
    assert result.metrics.empresa.tolist() == ["A"]
    assert result.diagnostics.set_index("empresa").loc["B", "status"] == "historico_insuficiente"
