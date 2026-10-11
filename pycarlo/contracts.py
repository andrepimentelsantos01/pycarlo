"""Contratos públicos e validação das tabelas de entrada."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


FLOW_COLUMNS = ("empresa", "componente", "data", "direcao", "valor", "classificacao")
HISTORY_COLUMNS = (
    "empresa", "componente", "direcao", "data_previsao", "data_alvo",
    "valor_previsto", "valor_realizado",
)


def read_table(source: pd.DataFrame | str | Path, name: str) -> pd.DataFrame:
    if isinstance(source, pd.DataFrame):
        return source.copy()
    path = Path(source)
    if path.suffix.lower() != ".parquet":
        raise ValueError(f"{name}: informe um DataFrame ou arquivo .parquet")
    return pd.read_parquet(path)


def _date_column(frame: pd.DataFrame, column: str, name: str) -> None:
    try:
        dates = pd.to_datetime(frame[column], errors="raise")
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name}.{column}: data inválida") from exc
    if dates.isna().any():
        raise ValueError(f"{name}.{column}: datas nulas não são permitidas")
    if getattr(dates.dt, "tz", None) is not None:
        raise ValueError(f"{name}.{column}: use datas sem fuso horário")
    if (dates != dates.dt.normalize()).any():
        raise ValueError(f"{name}.{column}: use datas sem horário")
    frame[column] = dates.dt.normalize()


def _amount_column(frame: pd.DataFrame, column: str, name: str, *, positive: bool = False) -> None:
    if not pd.api.types.is_numeric_dtype(frame[column]):
        raise ValueError(f"{name}.{column}: valores devem ser numéricos")
    values = frame[column].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (positive and (values <= 0).any()) or (values < 0).any():
        qualifier = "positivos e finitos" if positive else "não negativos e finitos"
        raise ValueError(f"{name}.{column}: valores devem ser {qualifier}")
    frame[column] = values


def _labels(frame: pd.DataFrame, columns: tuple[str, ...], name: str) -> None:
    for column in columns:
        if frame[column].isna().any() or not frame[column].map(lambda x: isinstance(x, str) and bool(x.strip())).all():
            raise ValueError(f"{name}.{column}: texto não vazio obrigatório")
        frame[column] = frame[column].str.strip()


def validate_flows(source: pd.DataFrame | str | Path) -> pd.DataFrame:
    frame = read_table(source, "fluxos")
    missing = sorted(set(FLOW_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"fluxos: colunas ausentes: {', '.join(missing)}")
    frame = frame.loc[:, list(FLOW_COLUMNS)].copy()
    _labels(frame, ("empresa", "componente", "direcao", "classificacao"), "fluxos")
    _date_column(frame, "data", "fluxos")
    _amount_column(frame, "valor", "fluxos")
    if not frame.direcao.isin(["entrada", "saida"]).all():
        raise ValueError("fluxos.direcao: use 'entrada' ou 'saida'")
    if not frame.classificacao.isin(["conhecido", "previsto"]).all():
        raise ValueError("fluxos.classificacao: use 'conhecido' ou 'previsto'")
    key = ["empresa", "componente", "data", "direcao"]
    if frame.duplicated(key).any():
        raise ValueError("fluxos: chave empresa/componente/data/direcao duplicada ou sobreposta")
    return frame


def validate_history(source: pd.DataFrame | str | Path) -> pd.DataFrame:
    frame = read_table(source, "historico")
    missing = sorted(set(HISTORY_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"historico: colunas ausentes: {', '.join(missing)}")
    frame = frame.loc[:, list(HISTORY_COLUMNS)].copy()
    _labels(frame, ("empresa", "componente", "direcao"), "historico")
    for column in ("data_previsao", "data_alvo"):
        _date_column(frame, column, "historico")
    _amount_column(frame, "valor_previsto", "historico", positive=True)
    _amount_column(frame, "valor_realizado", "historico")
    if not frame.direcao.isin(["entrada", "saida"]).all():
        raise ValueError("historico.direcao: use 'entrada' ou 'saida'")
    if (frame.data_alvo <= frame.data_previsao).any():
        raise ValueError("historico: data_alvo deve ser posterior à data_previsao")
    if frame.duplicated(["empresa", "componente", "direcao", "data_previsao", "data_alvo"]).any():
        raise ValueError("historico: chave de safra/semana/componente duplicada")
    return frame


@dataclass(frozen=True)
class SimulationConfig:
    weeks: int = 13
    simulations: int = 10_000
    seed: int = 42
    confidence: float = 0.95
    min_vintages: int = 3
    histogram_bins: int = 40
    keep_paths: bool = False

    def __post_init__(self) -> None:
        for name in ("weeks", "simulations", "min_vintages", "histogram_bins"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name}: use inteiro positivo")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError("seed: use inteiro não negativo")
        if not 0 < self.confidence < 1:
            raise ValueError("confidence: use valor entre 0 e 1")


@dataclass
class SimulationResult:
    status: str
    metrics: pd.DataFrame = field(default_factory=pd.DataFrame)
    daily: pd.DataFrame = field(default_factory=pd.DataFrame)
    histogram: pd.DataFrame = field(default_factory=pd.DataFrame)
    diagnostics: pd.DataFrame = field(default_factory=pd.DataFrame)
    path_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    paths: pd.DataFrame | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Representação compatível com JSON, com trajetórias apenas se solicitadas."""
        import json

        def records(frame: pd.DataFrame | None) -> list[dict[str, Any]] | None:
            return None if frame is None else json.loads(frame.to_json(orient="records", date_format="iso"))

        return {
            "status": self.status, "metadata": self.metadata,
            "metrics": records(self.metrics), "daily": records(self.daily),
            "histogram": records(self.histogram), "diagnostics": records(self.diagnostics),
            "path_summary": records(self.path_summary),
            "paths": records(self.paths),
        }
