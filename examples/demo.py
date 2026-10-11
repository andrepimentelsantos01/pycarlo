"""Demonstração autônoma: dados fictícios e cinco artefatos em output/."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from pycarlo import SimulationConfig, run_simulation
from pycarlo.visualization import plot_cash_evolution, plot_final_balance
import matplotlib.pyplot as plt


def make_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float], pd.Timestamp]:
    as_of = pd.Timestamp("2026-01-01")
    company = "Empresa Exemplo"
    flows: list[dict] = []
    for week in range(13):
        first_day = as_of + pd.Timedelta(days=week * 7 + 1)
        flows.extend([
            {"empresa": company, "componente": "recebiveis", "data": first_day + pd.Timedelta(days=1),
             "direcao": "entrada", "valor": 2_200_000.0, "classificacao": "previsto"},
            {"empresa": company, "componente": "fornecedores", "data": first_day + pd.Timedelta(days=3),
             "direcao": "saida", "valor": 1_200_000.0, "classificacao": "previsto"},
            {"empresa": company, "componente": "folha", "data": first_day + pd.Timedelta(days=5),
             "direcao": "saida", "valor": 800_000.0, "classificacao": "conhecido"},
        ])

    history: list[dict] = []
    for vintage_index in range(60):
        issued_at = pd.Timestamp("2020-01-01") + pd.Timedelta(days=vintage_index * 30)
        revenue_factor = 0.91 + 0.20 * math.sin(vintage_index * 1.73) + 0.08 * math.cos(vintage_index * 0.47)
        supplier_factor = 1.04 - 0.09 * math.sin(vintage_index * 1.73) + 0.04 * math.cos(vintage_index * 0.63)
        for week in range(13):
            target = issued_at + pd.Timedelta(days=(week + 1) * 7)
            for component, direction, forecast, factor in (
                ("recebiveis", "entrada", 2_200_000.0, revenue_factor + 0.015 * (week % 3)),
                ("fornecedores", "saida", 1_200_000.0, supplier_factor + 0.01 * (week % 2)),
            ):
                history.append({
                    "empresa": company, "componente": component, "direcao": direction,
                    "data_previsao": issued_at, "data_alvo": target,
                    "valor_previsto": forecast, "valor_realizado": forecast * factor,
                })
    return pd.DataFrame(flows), pd.DataFrame(history), {company: 3_000_000.0}, as_of


def main() -> None:
    flows, history, balances, as_of = make_data()
    result = run_simulation(
        flows, balances, as_of, history,
        SimulationConfig(weeks=13, simulations=10_000, seed=42),
    )
    if result.status != "ok":
        raise RuntimeError(f"Calibração demonstrativa indisponível: {result.diagnostics.to_dict('records')}")

    output = Path(__file__).resolve().parents[1] / "output"
    output.mkdir(parents=True, exist_ok=True)
    company = next(iter(balances))
    fig = plot_final_balance(result, company, title="EXEMPLO ILUSTRATIVO — SALDO FINAL PROJETADO",
                             output=output / "distribuicao_saldo_final.png")
    plt.close(fig)
    fig = plot_cash_evolution(result, company, output=output / "evolucao_probabilistica.png")
    plt.close(fig)
    (output / "indicadores_risco.json").write_text(
        json.dumps({"status": result.status, "metadata": result.metadata,
                    "indicadores": json.loads(result.metrics.to_json(orient="records", date_format="iso")),
                    "histograma": json.loads(result.histogram.to_json(orient="records"))},
                   ensure_ascii=False, indent=2), encoding="utf-8",
    )
    result.daily.to_parquet(output / "percentis_diarios.parquet", index=False)
    (output / "diagnostico_calibracao.json").write_text(
        json.dumps(json.loads(result.diagnostics.to_json(orient="records")),
                   ensure_ascii=False, indent=2), encoding="utf-8",
    )


if __name__ == "__main__":
    main()
