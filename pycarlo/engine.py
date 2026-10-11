"""Motor vetorizado de fluxo diário por empresa."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pandas as pd

from .calibration import calibrate_company
from .contracts import SimulationConfig, SimulationResult, validate_flows, validate_history
from .distributions import sample_vintages
from .metrics import summarize


def _as_of(value: str | pd.Timestamp) -> pd.Timestamp:
    try:
        result = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("as_of: informe uma data válida") from exc
    if pd.isna(result) or result.tz is not None or result != result.normalize():
        raise ValueError("as_of: informe uma data sem horário ou fuso")
    return result


def run_simulation(
    flows: pd.DataFrame | str | Path,
    opening_balances: Mapping[str, float],
    as_of: str | pd.Timestamp,
    history: pd.DataFrame | str | Path | None = None,
    config: SimulationConfig | None = None,
) -> SimulationResult:
    """Simula os dias após ``as_of`` por ``weeks`` semanas.

    O histórico contém valores previstos e realizados semanais por safra. Sem
    safras completas suficientes para uma empresa com previsão, seu resultado
    retorna diagnóstico e nenhuma métrica probabilística para essa empresa.
    """
    cfg = config or SimulationConfig()
    if not isinstance(cfg, SimulationConfig):
        raise TypeError("config: use SimulationConfig")
    cutoff = _as_of(as_of)
    frame = validate_flows(flows)
    if frame.empty:
        raise ValueError("fluxos: ao menos um movimento é necessário")
    dates = pd.date_range(cutoff + pd.Timedelta(days=1), periods=cfg.weeks * 7, freq="D")
    if (~frame.data.isin(dates)).any():
        raise ValueError("fluxos.data: todos os movimentos devem estar no horizonte após as_of")
    companies = sorted(frame.empresa.unique())
    if not isinstance(opening_balances, Mapping):
        raise TypeError("opening_balances: informe mapa empresa → saldo")
    if set(opening_balances) != set(companies):
        raise ValueError("opening_balances: informe exatamente um saldo por empresa dos fluxos")
    for company, balance in opening_balances.items():
        if isinstance(balance, bool) or not isinstance(balance, (int, float, np.number)) or not np.isfinite(balance):
            raise ValueError(f"opening_balances[{company}]: saldo numérico finito obrigatório")
    hist = validate_history(history) if history is not None else pd.DataFrame(columns=[
        "empresa", "componente", "direcao", "data_previsao", "data_alvo",
        "valor_previsto", "valor_realizado",
    ])
    frame["dia"] = (frame.data - dates[0]).dt.days.astype(int)
    frame["semana"] = frame.dia // 7
    frame["sinal"] = np.where(frame.direcao == "entrada", 1.0, -1.0)
    rng = np.random.default_rng(cfg.seed)
    all_metrics: list[pd.DataFrame] = []
    all_daily: list[pd.DataFrame] = []
    all_histograms: list[pd.DataFrame] = []
    all_summaries: list[pd.DataFrame] = []
    all_paths: list[pd.DataFrame] = []
    diagnostics: list[dict] = []
    for company in companies:
        company_flows = frame.loc[frame.empresa == company]
        known = company_flows.loc[company_flows.classificacao == "conhecido"]
        forecast = company_flows.loc[company_flows.classificacao == "previsto"]
        factors, cells, diagnostic = calibrate_company(hist, company, forecast, cutoff, cfg.min_vintages)
        diagnostics.append({"empresa": company, **diagnostic})
        if len(forecast) and factors is None:
            continue
        daily_amount = np.zeros((cfg.simulations, len(dates)), dtype=float)
        if len(known):
            known_daily = np.bincount(
                known.dia.to_numpy(),
                weights=(known.valor * known.sinal).to_numpy(),
                minlength=len(dates),
            )
            daily_amount += known_daily
        if len(forecast):
            chosen = sample_vintages(factors, cfg.simulations, rng)
            cell_index = {cell: index for index, cell in enumerate(cells)}
            grouped = forecast.groupby(["componente", "direcao", "semana", "dia"], sort=False)["valor"].sum()
            for (component, direction, week, day), amount in grouped.items():
                column = cell_index[(component, direction, int(week))]
                sign = 1.0 if direction == "entrada" else -1.0
                daily_amount[:, int(day)] += sign * amount * factors[chosen, column]
        balances = float(opening_balances[company]) + np.cumsum(daily_amount, axis=1)
        metrics, daily, histogram, path_summary = summarize(company, dates, balances, cfg.confidence, cfg.histogram_bins)
        all_metrics.append(metrics)
        all_daily.append(daily)
        all_histograms.append(histogram)
        all_summaries.append(path_summary)
        if cfg.keep_paths:
            all_paths.append(pd.DataFrame({
                "empresa": np.repeat(company, cfg.simulations * len(dates)),
                "simulacao": np.repeat(np.arange(cfg.simulations), len(dates)),
                "data": np.tile(dates.to_numpy(), cfg.simulations),
                "saldo": balances.ravel(),
            }))
    status = "ok" if len(all_metrics) == len(companies) else (
        "historico_insuficiente" if not all_metrics else "parcial"
    )
    return SimulationResult(
        status=status,
        metrics=pd.concat(all_metrics, ignore_index=True) if all_metrics else pd.DataFrame(),
        daily=pd.concat(all_daily, ignore_index=True) if all_daily else pd.DataFrame(),
        histogram=pd.concat(all_histograms, ignore_index=True) if all_histograms else pd.DataFrame(),
        diagnostics=pd.DataFrame(diagnostics),
        path_summary=pd.concat(all_summaries, ignore_index=True) if all_summaries else pd.DataFrame(),
        paths=pd.concat(all_paths, ignore_index=True) if cfg.keep_paths and all_paths else None,
        metadata={"as_of": cutoff.date().isoformat(), "inicio": dates[0].date().isoformat(),
                  "fim": dates[-1].date().isoformat(), "semanas": cfg.weeks,
                  "simulacoes": cfg.simulations, "seed": cfg.seed,
                  "confianca": cfg.confidence},
    )
