"""Exemplo fictício: execute apenas quando desejar experimentar o pacote."""
import pandas as pd

from pycarlo import SimulationConfig, run_simulation
from pycarlo.visualization import plot_cash_evolution, plot_final_balance


as_of = pd.Timestamp("2026-01-01")
flows = pd.DataFrame([
    {"empresa": "Acme", "componente": "recebiveis", "data": as_of + pd.Timedelta(days=day),
     "direcao": "entrada", "valor": 10_000.0, "classificacao": "previsto"}
    for day in range(1, 92, 7)
] + [
    {"empresa": "Acme", "componente": "folha", "data": as_of + pd.Timedelta(days=day),
     "direcao": "saida", "valor": 8_000.0, "classificacao": "conhecido"}
    for day in range(7, 92, 7)
])

history_rows = []
for vintage_index, vintage in enumerate(pd.to_datetime(["2025-01-01", "2025-04-01", "2025-07-01", "2025-09-01"])):
    for week in range(13):
        history_rows.append({
            "empresa": "Acme", "componente": "recebiveis", "direcao": "entrada",
            "data_previsao": vintage, "data_alvo": vintage + pd.Timedelta(days=7 * (week + 1)),
            "valor_previsto": 10_000.0,
            "valor_realizado": 10_000.0 * (0.85 + 0.04 * vintage_index + 0.01 * (week % 3)),
        })
history = pd.DataFrame(history_rows)

result = run_simulation(flows, {"Acme": 25_000.0}, as_of, history,
                        SimulationConfig(seed=7, simulations=1_000))
print(result.metrics.to_string(index=False))
plot_final_balance(result, "Acme", output="saldo_final.png")
plot_cash_evolution(result, "Acme", output="evolucao.png")
