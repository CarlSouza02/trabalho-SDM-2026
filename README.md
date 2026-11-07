# Seasonal Score-Driven Models for Electricity Load Forecasting

**A probabilistic study of daily electricity load in the Brazilian Interconnected Power System (SIN), 2016–2026.**

[![Status](https://img.shields.io/badge/status-in%20development-2563eb)](https://github.com/CarlSouza02/trabalho-SDM-2026/issues)
[![Python](https://img.shields.io/badge/Python-Jupyter-3776AB?logo=python&logoColor=white)](https://jupyter.org/)
[![Data](https://img.shields.io/badge/data-ONS%20Open%20Data-15803d)](https://dados.ons.org.br/dataset/carga-energia)
[![Institution](https://img.shields.io/badge/institution-PUC--Rio-17365D)](https://www.puc-rio.br/)

> **PUC-Rio · Department of Electrical Engineering (DEE)**  
> **Course:** Score-Driven Models (2026)  
> **Professor:** Cristiano Augusto Coelho Fernandes  
> **Students:** Carlos Souza & Gabriel Matz

---

## Overview

Electricity load presents strong calendar effects, persistence, changes in level, and occasional extreme observations. Reliable forecasts matter for power-system planning and operation, particularly when uncertainty must be quantified.

This project investigates whether a **seasonal Generalized Autoregressive Score (GAS)** model can capture these features and deliver accurate daily load forecasts for the Brazilian SIN. The proposed specification includes weekly and annual seasonal effects and a conditional level updated through the score of the predictive density.

**Research question:** *How well does a seasonal score-driven model describe the conditional distribution of daily SIN electricity load, and how does its out-of-sample forecasting performance compare with seasonal benchmarks?*

## Data

**Official source:** [ONS Open Data — Carga de Energia Diária](https://dados.ons.org.br/dataset/carga-energia)

| Property | Description |
|---|---|
| Frequency | Daily |
| Measurement | Average power, **MWmed** |
| Geographic scope | Brazilian Interconnected Power System (SIN) |
| Regional subsystems | Southeast/Central-West (SE), South (S), Northeast (NE), North (N) |
| Study period | **2016-01-01 onward** (Excel snapshot ends 2026-11-04) |
| Full history via script | 2000-01-01 to the latest ONS release (9,806 days as of 2026-11-05) |
| Source files | ONS annual Parquet releases (`CARGA_ENERGIA_<year>.parquet`) |

The SIN series was constructed as the sum of the four regional subsystems for each date:

$$
Y_t^{\mathrm{SIN}}=Y_t^{SE}+Y_t^{S}+Y_t^{NE}+Y_t^{N}.
$$

If any subsystem is missing on a given date, the SIN value for that date is left as missing (no partial sums). In the current release this affects 3 days, the same dates on which the subsystems themselves are missing.

### Download pipeline

[`baixar_carga_ons.py`](baixar_carga_ons.py) queries the ONS CKAN API, downloads the annual Parquet files, and consolidates them:

| Output | Content |
|---|---|
| `dados/raw/CARGA_ENERGIA_<year>.parquet` | Original annual files (current year is always re-downloaded) |
| `dados/carga_<N\|NE\|S\|SE>.parquet` | One daily series per subsystem |
| `dados/carga_SIN.parquet` | SIN series, sum of the four subsystems |
| `dados/carga_todos_submercados.parquet` | All subsystems stacked, for convenience |

All files share the columns `id_subsistema`, `nom_subsistema`, `din_instante` (date) and `val_cargaenergiamwmed` (MWmed). During consolidation, timestamps are truncated to the day and duplicated dates keep the non-missing value.

Downloaded and generated Parquet files are not versioned (see [`.gitignore`](.gitignore)); run the script to rebuild them.

### Available dataset

📊 **[dados/ONS_CARGA_ENERGIA_2016_2026.xlsx](dados/ONS_CARGA_ENERGIA_2016_2026.xlsx)** (static snapshot, 2016-01-01 to 2026-11-04)

| Worksheet | Content |
|---|---|
| `Serie_SIN` | Daily aggregated load and calendar variables |
| `Dados_Diarios` | Consolidated original observations by subsystem |
| `Controle` | Annual coverage and record counts |
| `Estatisticas` | Initial descriptive statistics |

**Important comparability caveat.** The ONS definition/composition of reported load changed over time. In particular, the source describes changes in **March 2021** and the inclusion of estimated distributed micro-/minigeneration beginning **29 April 2023**. These revisions must be considered in diagnostics, interpretation, and forecasts. The ONS may also revise published observations retrospectively. See the [source documentation](https://dados.ons.org.br/dataset/carga-energia).

📋 **Data audit:** [docs/auditoria_base_ons.md](docs/auditoria_base_ons.md) documents the source, license (CC-BY), data dictionary, coverage, the SIN = SE + S + NE + N check, extreme values, and the estimated size of the 2021 and 2023 definition breaks (about +4% to +6% in level each).

## Methodology

### 1. Exploratory and seasonal analysis

We will inspect the raw series, annual summaries, day-of-week profiles, annual profiles, autocorrelation, and the periodogram. The working hypotheses are:

- **Weekly seasonality:** period 7 days;
- **Annual seasonality:** approximately 365.25 days, with Fourier harmonics;
- **Dynamic level:** conditional adaptation to forecast surprises.

These are **hypotheses to be evaluated**, not conclusions already established.

### 2. Baseline seasonal GAS specification

The initial conditional model is

$$
Y_t\mid\mathcal F_{t-1}\sim\mathcal N(m_t,\sigma^2),
\qquad
m_t=\mu_t+S_t^{(7)}+S_t^{(a)}.
$$

The annual component may be represented by

$$
S_t^{(a)}=\sum_{k=1}^{K}\left[
a_k\cos\left(\frac{2\pi kt}{365.25}\right)+
b_k\sin\left(\frac{2\pi kt}{365.25}\right)
\right].
$$

With inverse-Fisher-information scaling for the Gaussian location score,

$$
s_t=Y_t-m_t,
\qquad
\mu_{t+1}=\omega+B\mu_t+As_t.
$$

The weekly component will use identifiable day-of-week effects. Model constraints, initialization, optimization, and the choice of harmonic order `K` will be documented when implemented. Extensions may include dynamic volatility or alternative conditional distributions if diagnostics warrant them.

### 3. Model diagnostics

Planned checks:

- Standardized innovations: time plot, histogram, and Q–Q plot;
- Jarque–Bera and Anderson–Darling normality tests;
- Residual and squared-residual ACF, with Ljung–Box tests;
- Probability integral transform (PIT): histogram, uniformity, and serial dependence;
- Outlier sensitivity and potential intervention variables.

### 4. SARIMA benchmark

[`sarima_carga.py`](sarima_carga.py) fits a seasonal ARIMA benchmark to each series (N, NE, S, SE and SIN):

- Model: SARIMA(1,1,1)×(1,1,1)<sub>7</sub> on log load;
- Missing days are filled by linear interpolation;
- The last `--horizonte` days (default 365) are held out for testing;
- Reported metrics: MAPE, RMSE, MAE, AIC and the Ljung–Box p-value at lag 14.

Outputs go to `resultados/`: `sarima_<series>.png` (forecast and residuals), `sarima_<series>_previsao.csv` (forecast with 95% interval), `sarima_<series>_resumo.txt` (model summary and Ljung–Box) and `sarima_metricas.csv` (all series). This is a preliminary benchmark; it does not yet follow the two-test design below.

### 5. Out-of-sample forecasting

| Stage | Period | Purpose |
|---|---|---|
| Training | 2016–2022 | Initial parameter estimation |
| Test 1 | 2023–2024 | First out-of-sample evaluation |
| Expanded estimation | Through 2024 | Reestimate before Test 2 |
| Test 2 | 2025–2026 (available dates) | Second evaluation |

We plan to examine multiple forecast horizons, produce predictive means and medians (via simulation when needed), and compare the GAS model against naive and seasonal-naive benchmarks on **identical forecast origins**.

**Candidate metrics:** MAE, RMSE, MASE, WAPE; for probabilistic forecasts, CRPS and/or interval scores. Final horizons and model variants will be fixed before evaluating held-out results.

## Progress and roadmap

| Workstream | Status | Tracking |
|---|---|---|
| Data consolidation | Done: download pipeline, SIN series and [audit report](docs/auditoria_base_ons.md) | [#1](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/1) |
| Seasonality and exploratory analysis | Planned | [#2](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/2) |
| GAS formulation and estimation | Planned | [#3](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/3) |
| Diagnostics and outliers | Planned | [#4](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/4) |
| Two out-of-sample tests | Planned | [#5](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/5) |
| Benchmarks and comparison | Preliminary SARIMA benchmark implemented | [#6](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/6) |
| Report, slides, reproducibility | Planned | [#7](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/7) |

➡️ **[View all open Issues](https://github.com/CarlSouza02/trabalho-SDM-2026/issues)**

## Getting started

### Repository structure

```
.
├── baixar_carga_ons.py   # downloads ONS data and builds the daily series
├── auditoria_carga.py    # data audit (coverage, SIN check, extremes, definition breaks)
├── sarima_carga.py       # SARIMA benchmark per subsystem and SIN
├── requirements.txt      # pinned Python dependencies
├── docs/
│   └── auditoria_base_ons.md   # data audit and documentation report (issue #1)
├── dados/                # data (Parquet files are generated, not versioned)
│   └── ONS_CARGA_ENERGIA_2016_2026.xlsx
└── resultados/           # outputs (benchmark; audit tables and figures in auditoria/)
```

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
```

### Reproducing

```bash
python baixar_carga_ons.py              # download only what is missing (+ current year)
python baixar_carga_ons.py --forcar     # re-download everything
python auditoria_carga.py               # data audit -> resultados/auditoria/
python sarima_carga.py                  # all series, 365-day test
python sarima_carga.py --submercados SIN --inicio 2016-01-01 --horizonte 365
```

### Loading the data

```python
import pandas as pd

sin = pd.read_parquet("dados/carga_SIN.parquet")
y = sin.set_index("din_instante")["val_cargaenergiamwmed"].asfreq("D")
y = y["2016-01-01":]
print(y.describe())
```

The Excel snapshot can still be read directly:

```python
df = pd.read_excel(
    "dados/ONS_CARGA_ENERGIA_2016_2026.xlsx",
    sheet_name="Serie_SIN",
    parse_dates=["data"],
)
y = df.sort_values("data").set_index("data")["carga_sin_mwmed"].asfreq("D")
```

## References

1. Creal, D., Koopman, S. J., & Lucas, A. (2013). Generalized autoregressive score models with applications. *Journal of Applied Econometrics, 28*(5), 777–795. [DOI](https://doi.org/10.1002/jae.1279).
2. Harvey, A. C. (2013). *Dynamic Models for Volatility and Heavy Tails: With Applications to Financial and Economic Time Series*. Cambridge University Press.
3. Operador Nacional do Sistema Elétrico (ONS). [Carga de Energia Diária — Dados Abertos](https://dados.ons.org.br/dataset/carga-energia).

---

*Academic project in progress. Empirical findings and performance figures will only be reported after estimation and validation.*
