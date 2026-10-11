"""Indicadores derivados das trajetórias simuladas."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import binomtest


def summarize(
    company: str,
    dates: pd.DatetimeIndex,
    balances: np.ndarray,
    confidence: float,
    bins: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n = balances.shape[0]
    final = balances[:, -1]
    worst = balances.min(axis=1)
    deficit_final = int(np.count_nonzero(final < 0))
    rupture = int(np.count_nonzero(worst < 0))
    bounds = binomtest(rupture, n).proportion_ci(confidence_level=confidence)
    daily_risk = (balances < 0).mean(axis=0)
    quantiles = np.quantile(balances, [0.05, 0.5, 0.95], axis=0)
    final_quantiles = np.quantile(final, [0.05, 0.5, 0.95])
    worst_quantiles = np.quantile(worst, [0.05, 0.5, 0.95])
    # Reserva aportada no início: cobre o menor saldo de cada trajetória.
    reserve = max(0.0, -float(np.quantile(worst, 1.0 - confidence)))
    daily = pd.DataFrame({
        "empresa": company, "data": dates, "p5": quantiles[0],
        "p50": quantiles[1], "p95": quantiles[2],
        "probabilidade_saldo_negativo": daily_risk,
    })
    highest = daily_risk.max()
    dates_highest = ([date.date().isoformat() for date in dates[daily_risk == highest]]
                     if highest > 0 else [])
    periods = []
    start = None
    for index, exposed in enumerate(daily_risk > 0):
        if exposed and start is None:
            start = index
        if start is not None and (not exposed or index == len(dates) - 1):
            end = index if exposed else index - 1
            periods.append(f"{dates[start].date().isoformat()}:{dates[end].date().isoformat()}")
            start = None
    metrics = pd.DataFrame([{
        "empresa": company,
        "probabilidade_saldo_final_negativo": deficit_final / n,
        "probabilidade_ruptura": rupture / n,
        "cenarios_saldo_final_negativo": deficit_final,
        "cenarios_com_ruptura": rupture,
        "ic_probabilidade_ruptura_inferior": bounds.low,
        "ic_probabilidade_ruptura_superior": bounds.high,
        "saldo_final_p5": float(final_quantiles[0]),
        "saldo_final_p50": float(final_quantiles[1]),
        "saldo_final_p95": float(final_quantiles[2]),
        "pior_saldo_p5": float(worst_quantiles[0]),
        "pior_saldo_p50": float(worst_quantiles[1]),
        "pior_saldo_p95": float(worst_quantiles[2]),
        "caixa_adicional": reserve,
        "confianca": confidence,
        "maior_risco_diario": float(highest),
        "data_maior_risco": dates_highest[0] if dates_highest else "",
        "datas_maior_risco": ",".join(dates_highest),
        "periodos_com_risco": ",".join(periods),
        "primeira_data_com_risco": next((d.date().isoformat() for d, p in zip(dates, daily_risk) if p > 0), ""),
        "simulacoes": n,
    }])
    counts, edges = np.histogram(final, bins=bins)
    histogram = pd.DataFrame({
        "empresa": company, "limite_inferior": edges[:-1],
        "limite_superior": edges[1:], "contagem": counts,
        "proporcao": counts / n,
    })
    path_summary = pd.DataFrame({
        "empresa": company, "simulacao": np.arange(n),
        "saldo_final": final, "pior_saldo_diario": worst,
        "data_pior_saldo": dates[balances.argmin(axis=1)],
    })
    return metrics, daily, histogram, path_summary
