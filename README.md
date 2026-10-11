# PyCarlo

Pacote independente para simulação de risco de fluxo de caixa. Usa bootstrap de safras históricas completas com seed reproduzível. Movimentos conhecidos entram com valor exato; só movimentos previstos recebem fatores de erro históricos.

## Instalação futura

```bash
pip install -e .
```

Requer Python 3.10 ou superior. Não requer banco de dados, serviço ou frontend.

## Demonstração local no Windows

Abra o PowerShell na pasta do projeto e execute:

```powershell
.\start --local
```

`start.cmd` cria `.venv` se necessário, instala o pacote e as dependências nesse ambiente e executa `examples/demo.py`. O exemplo usa somente dados fictícios, independentes do forecast corporativo. A execução produz:

```text
output/
├── distribuicao_saldo_final.png
├── evolucao_probabilistica.png
├── indicadores_risco.json
├── percentis_diarios.parquet
└── diagnostico_calibracao.json
```

O histograma ilustrativo agrupa os bins do resultado em até oito barras para seguir o layout de referência; `result.histogram` mantém a resolução configurada. Os valores nos arquivos e nos gráficos vêm da mesma simulação. A pasta `output/` e o ambiente `.venv/` são ignorados pelo Git. O script pode instalar pacotes e executar simulações **quando você o iniciar**; ele não foi executado durante esta implementação.

## Contratos de entrada

`flows`: DataFrame ou Parquet com uma linha por `(empresa, componente, data, direcao)`:

| Coluna | Tipo | Regra |
|---|---|---|
| `empresa` | texto | Identificador não vazio |
| `componente` | texto | Categoria financeira não vazia |
| `data` | data | Dia do movimento, entre `as_of + 1` e o fim do horizonte |
| `direcao` | texto | `entrada` ou `saida` |
| `valor` | número | Magnitude não negativa e finita, sem sinal |
| `classificacao` | texto | `conhecido` ou `previsto` |

Não são aceitas chaves repetidas, inclusive quando uma linha é conhecida e a outra prevista. Agregue movimentos de mesma chave no ETL. Use componentes distintos se duas origens legítimas precisarem coexistir no mesmo dia. `opening_balances` é um dicionário com exatamente uma entrada por empresa de `flows`; saldos iniciais podem ser negativos.

`history`: DataFrame ou Parquet com uma linha por `(empresa, componente, direcao, data_previsao, data_alvo)`:

| Coluna | Tipo | Regra |
|---|---|---|
| `data_previsao` | data | Dia em que aquela previsão histórica foi emitida |
| `data_alvo` | data | Dia da semana alvo, posterior à emissão |
| `valor_previsto` | número | Total semanal previsto, estritamente positivo |
| `valor_realizado` | número | Total semanal realizado, não negativo |

As demais colunas são `empresa`, `componente` e `direcao`, com os mesmos significados de `flows`. O histórico é semanal: a semana de erro é `floor((data_alvo - data_previsao - 1 dia) / 7)`. Assim, os dias 1–7 após a emissão são a semana 0. Entregue uma observação por componente, direção e semana para cada data de emissão. Todas as observações de uma safra devem ter a mesma `data_previsao`. A calibração só usa safras emitidas antes de `as_of` e com realização até `as_of`, evitando vazamento futuro. Dados históricos de outras empresas nunca são usados como substitutos.

Cada safra elegível precisa cobrir todas as células `(componente, direcao, semana)` existentes nos movimentos previstos da empresa. O fator observado é `valor_realizado / valor_previsto`. Cada cenário sorteia uma safra inteira, preservando a dependência entre componentes e semanas. O fator semanal multiplica os valores diários previstos daquela célula; o perfil diário do forecast permanece como informado. A precisão intrassemanal do erro depende, portanto, do próprio forecast. Safras incompletas ou ambíguas não são imputadas. Se houver menos que `min_vintages` safras completas, a empresa recebe `historico_insuficiente` e nenhuma métrica simulada. Histórico ausente é permitido apenas para empresas sem movimentos previstos.

## API Python

```python
from pycarlo import SimulationConfig, run_simulation

result = run_simulation(
    flows=fluxos_df,
    opening_balances={"Acme": 250_000.0},
    as_of="2026-01-01",
    history=historico_df,
    config=SimulationConfig(weeks=13, simulations=10_000, seed=42,
                            confidence=0.95, min_vintages=3),
)

print(result.status)
print(result.metrics)
print(result.diagnostics)
```

`result` contém DataFrames `metrics`, `daily`, `histogram`, `diagnostics` e `path_summary`. `path_summary` contém o saldo final, pior saldo diário e respectiva data de cada trajetória. `daily` traz P5/P50/P95 e probabilidade diária de saldo negativo; P50 é a **mediana**, não a moda ou o resultado mais frequente. `metrics` traz separadamente a probabilidade de saldo final negativo e a probabilidade de ruptura em qualquer dia, as respectivas contagens de cenários, percentis de saldo final e pior saldo, caixa adicional, maior probabilidade diária de déficit, `data_maior_risco` (primeiro dia do pico), `datas_maior_risco` (todos os dias empatados), primeira data com risco e períodos contínuos com risco. Quando não há déficit simulado, as datas críticas ficam vazias. `histogram` traz limites, contagens e proporções. `result.as_dict()` fornece representação JSON. `result.paths` só existe com `keep_paths=True`; contém todos os saldos diários e pode ocupar muito espaço. `status` é `ok`, `parcial` ou `historico_insuficiente`.

O caixa adicional supõe uma reserva integral disponível desde o início do horizonte: `max(0, -quantil(pior_saldo_diario_por_trajetória, 1 - confiança))`. Para 95% de confiança, usa o P5 dos **menores saldos diários de cada trajetória**. Ele pode ser maior que o valor absoluto do P5 final quando uma trajetória se recupera após um déficit intermediário. Todas as probabilidades usam o número de simulações como denominador; os percentis usam os saldos simulados, sem arredondamento intermediário. O intervalo binomial de `probabilidade_ruptura` quantifica apenas o erro de reamostragem dos cenários condicionado às safras disponíveis; não mede a incerteza sobre a qualidade ou representatividade do histórico. Como cenários sorteiam safras com reposição, 10.000 simulações de 60 safras não equivalem a 10.000 observações históricas independentes. Os resultados não garantem cobertura para riscos não observados.

## CLI e exportação

```bash
pycarlo --flows fluxos.parquet --history historico.parquet \
  --balances '{"Acme": 250000}' --as-of 2026-01-01 --output saida
```

`--balances` aceita JSON literal ou caminho para JSON. Opções: `--weeks`, `--simulations`, `--seed`, `--confidence`, `--min-vintages`, `--bins`, `--paths`, `--no-plots`. A CLI grava `result.json` e os DataFrames não vazios em Parquet. Grava PNG por empresa com simulação disponível; `--no-plots` desativa os gráficos. Retorna código 2 quando há empresa sem histórico suficiente e 1 para erro de entrada. Os arquivos preservam resultados parciais e diagnósticos.

Para chamar os gráficos pela API, use `plot_final_balance` e `plot_cash_evolution` de `pycarlo.visualization`. Ambas aceitam `title`, `period`, `output` e `dpi`, e retornam `matplotlib.figure.Figure`.

## Integração a um pipeline

Ao final do ETL/forecast, normalize os movimentos para o contrato de `flows`; exporte as previsões históricas e respectivos realizados semanais para `history`; passe os saldos atuais por empresa e a data de corte. Inspecione `diagnostics` antes de consumir as métricas. A simulação não altera as regras de negócio que produzem o forecast.

O exemplo fictício mínimo em `examples/basic.py` mostra a preparação dos DataFrames. `examples/demo.py` gera a saída de apresentação. Os testes em `tests/` foram escritos para execução posterior.
