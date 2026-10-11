"""Gráficos executivos independentes do motor de simulação."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Circle, FancyBboxPatch, PathPatch
from matplotlib.path import Path as MplPath
from matplotlib.ticker import FuncFormatter, MaxNLocator
import numpy as np
import pandas as pd

from .contracts import SimulationResult


BACKGROUND = "#080d15"
PANEL = "#111c2b"
TEXT = "#e6edf6"
MUTED = "#97a6ba"
BLUE = "#338cf0"
CYAN = "#74c8ff"
RED = "#ff6a72"


def _brl(value: float, _: int | None = None) -> str:
    return "R$ " + f"{value:,.0f}".replace(",", ".")


def _brl_compact(value: float, _: int | None = None) -> str:
    magnitude = abs(value)
    if magnitude >= 1_000_000:
        amount, unit = magnitude / 1_000_000, "mi"
    elif magnitude >= 1_000:
        amount, unit = magnitude / 1_000, "mil"
    else:
        amount, unit = magnitude, ""
    number = f"{amount:.0f}" if abs(amount - round(amount)) < 0.05 else f"{amount:.1f}"
    sign = "−" if value < 0 else ""
    return f"{sign}R$ {number.replace('.', ',')} {unit}".strip()


def _rounded_bar(axis, left: float, width: float, height: float, radius_y: float) -> None:
    if height <= 0:
        return
    radius_x = min(width * 0.13, width / 2)
    radius_y = min(radius_y, height / 2)
    right = left + width
    vertices = [
        (left, 0), (left, height - radius_y),
        (left, height - radius_y * 0.45), (left + radius_x * 0.45, height),
        (left + radius_x, height), (right - radius_x, height),
        (right - radius_x * 0.45, height), (right, height - radius_y * 0.45),
        (right, height - radius_y), (right, 0), (left, 0),
    ]
    codes = [
        MplPath.MOVETO, MplPath.LINETO, MplPath.CURVE4, MplPath.CURVE4,
        MplPath.CURVE4, MplPath.LINETO, MplPath.CURVE4, MplPath.CURVE4,
        MplPath.CURVE4, MplPath.LINETO, MplPath.CLOSEPOLY,
    ]
    axis.add_patch(PathPatch(MplPath(vertices, codes), facecolor="#285899", edgecolor="none"))


def _style(axis) -> None:
    axis.set_facecolor(PANEL)
    axis.tick_params(colors=MUTED, labelsize=10)
    axis.grid(color="white", alpha=0.09, linewidth=0.7)
    axis.set_axisbelow(True)
    for spine in axis.spines.values():
        spine.set_color("#314157")


def _company_data(result: SimulationResult, company: str):
    metric = result.metrics.loc[result.metrics.empresa == company]
    if metric.empty:
        raise ValueError(f"empresa {company!r}: nenhuma simulação disponível; consulte diagnostics")
    return metric.iloc[0], result.daily.loc[result.daily.empresa == company], result.histogram.loc[result.histogram.empresa == company]


def plot_final_balance(
    result: SimulationResult, company: str, *, title: str | None = None,
    period: str | None = None, output: str | Path | None = None, dpi: int = 180,
) -> Figure:
    """Histograma do saldo final; retorna a Figure e opcionalmente salva PNG."""
    metric, _, histogram = _company_data(result, company)
    histogram = histogram.sort_values("limite_inferior").reset_index(drop=True)
    groups = np.array_split(np.arange(len(histogram)), min(8, len(histogram)))
    bars = [(float(histogram.iloc[group[0]].limite_inferior),
             float(histogram.iloc[group[-1]].limite_superior),
             int(histogram.iloc[group].contagem.sum())) for group in groups]
    fig = plt.figure(figsize=(8.88, 6.75), facecolor="#030303")
    border = FancyBboxPatch((0.014, 0.013), 0.972, 0.974,
                            boxstyle="round,pad=0,rounding_size=0.018",
                            linewidth=0.65, edgecolor="#333333", facecolor="none",
                            transform=fig.transFigure, clip_on=False)
    fig.add_artist(border)
    axis = fig.add_axes((0.09, 0.285, 0.865, 0.61), facecolor="#030303")
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.set_axisbelow(True)
    axis.yaxis.grid(True, color="#2a2a2a", alpha=0.46, linestyle=(0, (2, 5)), linewidth=0.7)
    axis.xaxis.grid(False)
    axis.tick_params(axis="both", colors="#c8c8c8", labelsize=9, length=0, pad=8)
    high = max(count for _, _, count in bars)
    for left, right, count in bars:
        gap = (right - left) * 0.12
        _rounded_bar(axis, left + gap / 2, right - left - gap, count, max(high * 0.028, 1))
    axis.set_xlim(bars[0][0], bars[-1][1])
    axis.set_ylim(0, max(high * 1.065, 1))
    axis.set_xticks([(left + right) / 2 for left, right, _ in bars])
    axis.xaxis.set_major_formatter(FuncFormatter(_brl_compact))
    axis.yaxis.set_major_locator(MaxNLocator(nbins=4, integer=True))
    axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}".replace(",", ".")))
    fig.text(0.03, 0.958, title or f"DISTRIBUIÇÃO — SALDO FINAL PROJETADO · {company.upper()}",
             color="#e8e8e8", fontsize=10, va="top")
    descriptor = period or f"Distribuição empírica de {int(metric.simulacoes):,} simulações".replace(",", ".")
    fig.text(0.03, 0.198, descriptor, color="#a5a5a5", fontsize=9, va="top")
    fig.text(0.045, 0.122, "Cenários simulados", color="#c9c9c9", fontsize=9, va="top")
    fig.text(0.045, 0.084, f"{int(metric.simulacoes):,}".replace(",", "."),
             color="#f0f0f0", fontsize=16, va="top")
    fig.add_artist(Circle((0.50, 0.060), 0.020, transform=fig.transFigure,
                          edgecolor="#343434", facecolor="none", linewidth=0.8))
    fig.text(0.50, 0.060, "↓", ha="center", va="center", color="#e4e4e4", fontsize=15)
    fig.text(0.52, 0.122, "Probabilidade de déficit", color="#c9c9c9", fontsize=9, va="top")
    fig.text(0.52, 0.084, f"{metric.probabilidade_saldo_final_negativo:.0%}",
             color="#f0f0f0", fontsize=16, va="top")
    fig.text(0.03, 0.028, "Estimativa baseada nas simulações e no histórico informado.",
             color="#666666", fontsize=8, va="bottom")
    if output is not None:
        fig.savefig(output, dpi=dpi, facecolor=fig.get_facecolor())
    return fig


def plot_cash_evolution(
    result: SimulationResult, company: str, *, title: str | None = None,
    period: str | None = None, output: str | Path | None = None, dpi: int = 180,
) -> Figure:
    """P5–P95, P50 e dias com risco de saldo negativo."""
    _, daily, _ = _company_data(result, company)
    daily = daily.sort_values("data")
    dates = pd.to_datetime(daily.data).to_numpy()
    p5 = daily.p5.to_numpy(dtype=float)
    p50 = daily.p50.to_numpy(dtype=float)
    p95 = daily.p95.to_numpy(dtype=float)
    risk = daily.probabilidade_saldo_negativo.to_numpy(dtype=float)
    fig, axis = plt.subplots(figsize=(13, 6.5), facecolor=BACKGROUND)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.83, bottom=0.17)
    _style(axis)
    axis.fill_between(dates, p5, p95, color=BLUE, alpha=0.22, label="Faixa P5–P95")
    axis.plot(dates, p50, color=CYAN, linewidth=2.2, label="Mediana P50")
    axis.axhline(0, color=RED, linestyle="--", linewidth=1.2, label="Saldo zero")
    start = None
    for index, exposed in enumerate(risk > 0):
        if exposed and start is None:
            start = index
        if start is not None and (not exposed or index == len(risk) - 1):
            end = index if exposed else index - 1
            axis.axvspan(dates[start], pd.Timestamp(dates[end]) + pd.Timedelta(days=1),
                         color=RED, alpha=0.09)
            start = None
    axis.yaxis.set_major_formatter(FuncFormatter(_brl))
    axis.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    axis.set_xlabel("Data", color=MUTED, labelpad=12)
    axis.set_ylabel("Saldo projetado", color=MUTED)
    axis.legend(loc="upper right", facecolor=PANEL, edgecolor="#314157", labelcolor=TEXT)
    fig.text(0.09, 0.93, title or f"Evolução probabilística do caixa · {company}",
             color=TEXT, fontsize=19, weight="semibold")
    fig.text(0.09, 0.885, period or f"{result.metadata.get('inicio', '')} a {result.metadata.get('fim', '')}",
             color=MUTED, fontsize=10)
    if output is not None:
        fig.savefig(output, dpi=dpi, facecolor=fig.get_facecolor())
    return fig
