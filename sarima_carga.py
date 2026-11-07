import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.statespace.sarimax import SARIMAX

RAIZ = Path(__file__).parent
DADOS = RAIZ / "dados"
SAIDA = RAIZ / "resultados" / "benchmark"
SUBMERCADOS = ["N", "NE", "S", "SE", "SIN"]

ORDEM = (1, 1, 1)
ORDEM_SAZONAL = (1, 1, 1, 7)
PERIODO_ANUAL = 365.25


def carregar(sub: str, inicio: str | None) -> pd.Series:
    df = pd.read_parquet(DADOS / f"carga_{sub}.parquet")
    print(df)
    y = df.set_index("din_instante")["val_cargaenergiamwmed"].asfreq("D")
    if inicio:
        y = y[inicio:]
    # Poucos dias faltantes na fonte: interpolação linear
    return y.interpolate(limit_direction="both")


def ajustar(y_log: pd.Series):
    modelo = SARIMAX(
        y_log,
        order=ORDEM,
        seasonal_order=ORDEM_SAZONAL,
    )
    return modelo.fit(disp=False, maxiter=200)


def metricas(real: pd.Series, prev: pd.Series) -> dict:
    erro = real - prev
    return {
        "MAPE_%": float(np.mean(np.abs(erro / real)) * 100),
        "RMSE_MW": float(np.sqrt(np.mean(erro**2))),
        "MAE_MW": float(np.mean(np.abs(erro))),
    }


def grafico(sub, y, teste, prev, ic, res, caminho):
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))

    ax = axes[0]
    janela = y[teste.index[0] - pd.Timedelta(days=2 * 365):]
    ax.plot(janela.index, janela, color="0.5", lw=0.8, label="Observado")
    ax.plot(prev.index, prev, color="C3", lw=1, label="Previsão SARIMA")
    ax.fill_between(ic.index, ic.iloc[:, 0], ic.iloc[:, 1], color="C3", alpha=0.15, label="IC 95%")
    ax.axvline(teste.index[0], color="k", ls="--", lw=0.8)
    ax.set_title(f"Submercado {sub}: SARIMA{ORDEM}x{ORDEM_SAZONAL}")
    ax.set_ylabel("Carga (MWmed)")
    ax.legend(loc="upper left")

    ax = axes[1]
    ax.plot(res.index, res, lw=0.5, color="C0")
    ax.set_title("Resíduos no treino (escala log)")
    fig.tight_layout()
    fig.savefig(caminho, dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inicio", default="2016-01-01", help="data inicial do treino (ex.: 2010-01-01)")
    parser.add_argument("--horizonte", type=int, default=365, help="dias de teste/previsão")
    parser.add_argument("--submercados", nargs="+", default=SUBMERCADOS)
    args = parser.parse_args()

    SAIDA.mkdir(exist_ok=True)
    linhas = []

    for sub in args.submercados:
        print(f"\n=== {sub} ===")
        y = carregar(sub, args.inicio)
        treino, teste = y.iloc[: -args.horizonte], y.iloc[-args.horizonte :]

        fit = ajustar(np.log(treino))

        fc = fit.get_forecast(steps=len(teste))
        prev = np.exp(fc.predicted_mean)
        ic = np.exp(fc.conf_int(alpha=0.05))

        res = fit.resid.iloc[14:]  # descarta início afetado pela diferenciação
        lb = acorr_ljungbox(res, lags=[7, 14, 28], return_df=True)

        m = metricas(teste, prev)
        m.update(
            submercado=sub,
            n_treino=len(treino),
            AIC=fit.aic,
            LjungBox_p_lag14=float(lb.loc[14, "lb_pvalue"]),
        )
        linhas.append(m)
        print(f"MAPE {m['MAPE_%']:.2f}% | RMSE {m['RMSE_MW']:.0f} MW | AIC {fit.aic:.0f}")

        (SAIDA / f"sarima_{sub}_resumo.txt").write_text(
            str(fit.summary()) + "\n\nLjung-Box:\n" + lb.to_string(), encoding="utf-8"
        )
        pd.DataFrame({"real": teste, "previsto": prev, "li95": ic.iloc[:, 0], "ls95": ic.iloc[:, 1]}).to_csv(
            SAIDA / f"sarima_{sub}_previsao.csv", index_label="data"
        )
        grafico(sub, y, teste, prev, ic, res, SAIDA / f"sarima_{sub}.png")

    tab = pd.DataFrame(linhas).set_index("submercado")
    tab.to_csv(SAIDA / "sarima_metricas.csv")
    print("\n", tab.round(3).to_string())


if __name__ == "__main__":
    main()
