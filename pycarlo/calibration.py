"""Calibração por bootstrap de safras completas de erros históricos."""
from __future__ import annotations

import numpy as np
import pandas as pd


def calibrate_company(
    history: pd.DataFrame,
    company: str,
    forecast: pd.DataFrame,
    as_of: pd.Timestamp,
    min_vintages: int,
) -> tuple[np.ndarray | None, list[tuple[str, str, int]], dict]:
    """Retorna matriz safra × (componente, direção, semana) de fatores realizados/previstos.

    Uma safra só entra se cobrir todas as células previstas da empresa. Assim uma
    linha amostrada mantém a dependência entre semanas e componentes observada
    na mesma data de previsão, sem preencher lacunas com parâmetros artificiais.
    """
    cells = sorted(set(zip(forecast.componente, forecast.direcao, forecast.semana)))
    if not cells:
        return None, cells, {"status": "sem_previsoes", "safras_elegiveis": 0,
                             "safras_completas": 0, "safras_minimas": min_vintages}
    subset = history.loc[
        (history.empresa == company)
        & (history.data_previsao < as_of)
        & (history.data_alvo <= as_of)
    ].copy()
    if subset.empty:
        return None, cells, {"status": "historico_insuficiente", "safras_elegiveis": 0,
                             "safras_completas": 0, "safras_minimas": min_vintages,
                             "motivo": "Nenhuma safra realizada antes da data de corte"}
    subset["semana"] = ((subset.data_alvo - subset.data_previsao).dt.days - 1) // 7
    subset = subset.loc[subset.semana >= 0]
    subset["fator"] = subset.valor_realizado / subset.valor_previsto
    needed = set(cells)
    matrices: list[list[float]] = []
    for _, vintage in subset.groupby("data_previsao", sort=True):
        if vintage.duplicated(["componente", "direcao", "semana"]).any():
            continue
        lookup = {
            (row.componente, row.direcao, int(row.semana)): float(row.fator)
            for row in vintage.itertuples(index=False)
        }
        if needed.issubset(lookup):
            matrices.append([lookup[cell] for cell in cells])
    diagnostic = {
        "status": "ok" if len(matrices) >= min_vintages else "historico_insuficiente",
        "safras_elegiveis": int(subset.data_previsao.nunique()),
        "safras_completas": len(matrices), "safras_minimas": min_vintages,
        "celulas_necessarias": len(cells),
        "motivo": "" if len(matrices) >= min_vintages else
        "Safras completas insuficientes para todas as semanas e componentes previstos",
    }
    return (np.asarray(matrices, dtype=float) if len(matrices) >= min_vintages else None), cells, diagnostic
