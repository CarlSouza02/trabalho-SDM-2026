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
| Compiled interval | **2016-01-01 to 2026-11-04** |
| SIN observations | **3,961 daily observations** |
| Regional records | **15,844 observations** |
| Source files | ONS annual CSV releases, 2016–2026 |

The SIN series was constructed as the sum of the four regional subsystems for each date:

$$
Y_t^{\mathrm{SIN}}=Y_t^{SE}+Y_t^{S}+Y_t^{NE}+Y_t^{N}.
$$

### Available dataset

📊 **[ONS_CARGA_ENERGIA_2016_2026.xlsx](ONS_CARGA_ENERGIA_2016_2026.xlsx)**

| Worksheet | Content |
|---|---|
| `Serie_SIN` | Daily aggregated load and calendar variables |
| `Dados_Diarios` | Consolidated original observations by subsystem |
| `Controle` | Annual coverage and record counts |
| `Estatisticas` | Initial descriptive statistics |

**Important comparability caveat.** The ONS definition/composition of reported load changed over time. In particular, the source describes changes in **March 2021** and the inclusion of estimated distributed micro-/minigeneration beginning **29 April 2023**. These revisions must be considered in diagnostics, interpretation, and forecasts. The ONS may also revise published observations retrospectively. See the [source documentation](https://dados.ons.org.br/dataset/carga-energia).

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

### 4. Out-of-sample forecasting

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
| Data consolidation | Dataset uploaded; further audit pending | [#1](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/1) |
| Seasonality and exploratory analysis | Planned | [#2](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/2) |
| GAS formulation and estimation | Planned | [#3](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/3) |
| Diagnostics and outliers | Planned | [#4](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/4) |
| Two out-of-sample tests | Planned | [#5](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/5) |
| Benchmarks and comparison | Planned | [#6](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/6) |
| Report, slides, reproducibility | Planned | [#7](https://github.com/CarlSouza02/trabalho-SDM-2026/issues/7) |

➡️ **[View all open Issues](https://github.com/CarlSouza02/trabalho-SDM-2026/issues)**

## Getting started

The **dataset is available now**. The modeling notebook and executable estimation pipeline will be added in later commits.

To explore the Excel file locally:

```python
import pandas as pd

df = pd.read_excel(
    "ONS_CARGA_ENERGIA_2016_2026.xlsx",
    sheet_name="Serie_SIN",
    parse_dates=["data"],
)
df = df.sort_values("data").set_index("data")
y = df["carga_sin_mwmed"].asfreq("D")
assert y.notna().all()
print(y.describe())
```

Once code is committed, this section will document the exact environment, dependencies, random seeds, and commands needed to reproduce the results.

## References

1. Creal, D., Koopman, S. J., & Lucas, A. (2013). Generalized autoregressive score models with applications. *Journal of Applied Econometrics, 28*(5), 777–795. [DOI](https://doi.org/10.1002/jae.1279).
2. Harvey, A. C. (2013). *Dynamic Models for Volatility and Heavy Tails: With Applications to Financial and Economic Time Series*. Cambridge University Press.
3. Operador Nacional do Sistema Elétrico (ONS). [Carga de Energia Diária — Dados Abertos](https://dados.ons.org.br/dataset/carga-energia).

---

*Academic project in progress. Empirical findings and performance figures will only be reported after estimation and validation.*
