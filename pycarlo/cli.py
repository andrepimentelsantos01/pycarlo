"""Interface de linha de comando para pipelines de forecast."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .contracts import SimulationConfig
from .engine import run_simulation
from .visualization import plot_cash_evolution, plot_final_balance
import matplotlib.pyplot as plt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simula risco de fluxo de caixa projetado")
    parser.add_argument("--flows", required=True, help="Fluxos em Parquet")
    parser.add_argument("--history", help="Histórico de safras em Parquet")
    parser.add_argument("--balances", required=True, help="JSON empresa → saldo inicial, ou caminho de arquivo JSON")
    parser.add_argument("--as-of", required=True, help="Data de corte YYYY-MM-DD")
    parser.add_argument("--output", required=True, help="Diretório de saída")
    parser.add_argument("--weeks", type=int, default=13)
    parser.add_argument("--simulations", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--min-vintages", type=int, default=3)
    parser.add_argument("--bins", type=int, default=40)
    parser.add_argument("--paths", action="store_true", help="Exporta trajetórias completas")
    parser.add_argument("--no-plots", action="store_true", help="Desativa PNG")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        try:
            balances = json.loads(args.balances)
        except json.JSONDecodeError:
            balances = json.loads(Path(args.balances).read_text(encoding="utf-8"))
        config = SimulationConfig(
            weeks=args.weeks, simulations=args.simulations, seed=args.seed,
            confidence=args.confidence, min_vintages=args.min_vintages,
            histogram_bins=args.bins, keep_paths=args.paths,
        )
        result = run_simulation(args.flows, balances, args.as_of, args.history, config)
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        for name in ("metrics", "daily", "histogram", "diagnostics", "path_summary"):
            frame: pd.DataFrame = getattr(result, name)
            if not frame.empty:
                frame.to_parquet(output / f"{name}.parquet", index=False)
        if result.paths is not None:
            result.paths.to_parquet(output / "paths.parquet", index=False)
        (output / "result.json").write_text(
            json.dumps(result.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if not args.no_plots:
            for index, company in enumerate(result.metrics.empresa):
                safe = "".join(char if char.isalnum() or char in "-_" else "_" for char in company)
                fig = plot_final_balance(result, company, output=output / f"{index}_{safe}_saldo_final.png")
                plt.close(fig)
                fig = plot_cash_evolution(result, company, output=output / f"{index}_{safe}_evolucao.png")
                plt.close(fig)
        return 0 if result.status == "ok" else 2
    except (OSError, ValueError, TypeError, KeyError) as exc:
        _parser().exit(1, f"pycarlo: {exc}\n")
