"""
Auditoria da base de carga diária da ONS (issue #1).

Lê os arquivos anuais brutos em dados/raw/ (baixados por baixar_carga_ons.py)
e as séries consolidadas em dados/, e gera em resultados/auditoria/:

    cobertura.csv              datas esperadas x observadas, por subsistema e período
    problemas_brutos.csv       duplicações, horários espúrios e valores ausentes na fonte
    checagem_sin.csv           verificação de que SIN = SE + S + NE + N
    extremos.csv               dias com resíduo robusto |z| > LIMIAR_Z
    quebras_definicao.csv      níveis e crescimento anual em torno de mar/2021 e abr/2023
    contagens_anuais.csv       contagens e estatísticas descritivas por ano e série
    estatisticas_periodo.csv   estatísticas descritivas no período de estudo
    serie_sin_quebras.png      SIN com médias móveis e marcação das mudanças de definição
    participacao_subsistemas.png  participação de cada subsistema no SIN ao longo do tempo

Uso:
    python auditoria_carga.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dateutil.easter import easter

RAIZ = Path(__file__).parent
DADOS = RAIZ / "dados"
SAIDA = RAIZ / "resultados" / "auditoria"

SUBS = ["N", "NE", "S", "SE"]
SERIES = SUBS + ["SIN"]
INICIO_ESTUDO = "2016-01-01"
LIMIAR_Z = 4.0
QUEBRAS = {
    "mar/2021: + geração não despachada": pd.Timestamp("2021-03-01"),
    "29/04/2023: + MMGD estimada": pd.Timestamp("2023-04-29"),
}
JANELAS_QUEBRA = (28, 91)  # dias antes/depois para comparar níveis

# Eventos conhecidos usados para anotar os extremos (intervalos inclusivos)
EVENTOS = [
    ("2018-03-21", "2018-03-21", "Apagão N/NE (desligamento da interligação Norte-Sul)"),
    ("2018-05-21", "2018-05-31", "Greve dos caminhoneiros"),
    ("2018-08-25", "2018-08-25", "Queda abrupta no NE (-60%) e no S: causa não identificada, possível erro na fonte"),
    ("2020-03-11", "2020-04-30", "Início da pandemia de COVID-19 (a referência de ±3 semanas mistura antes/depois)"),
    ("2021-03-01", "2021-03-01", "Data da mudança de definição da carga (mar/2021)"),
    ("2023-08-15", "2023-08-15", "Apagão nacional"),
]


def feriados(anos) -> dict:
    """Feriados nacionais (fixos e móveis), Carnaval, Corpus Christi e vésperas de Natal/Ano Novo."""
    out = {}
    for a in anos:
        fixos = {
            "01-01": "Confraternização Universal", "04-21": "Tiradentes", "05-01": "Dia do Trabalho",
            "09-07": "Independência", "10-12": "N. Sra. Aparecida", "11-02": "Finados",
            "11-15": "Proclamação da República", "12-24": "Véspera de Natal", "12-25": "Natal",
            "12-31": "Véspera de Ano Novo",
        }
        if a >= 2024:
            fixos["11-20"] = "Consciência Negra"
        for md, nome in fixos.items():
            out[pd.Timestamp(f"{a}-{md}")] = nome
        p = pd.Timestamp(easter(a))
        for dias, nome in [(-48, "Carnaval (segunda)"), (-47, "Carnaval (terça)"), (-46, "Quarta de Cinzas"),
                           (-2, "Sexta-feira Santa"), (60, "Corpus Christi")]:
            out[p + pd.Timedelta(days=dias)] = nome
    return out


def ler_brutos() -> pd.DataFrame:
    arquivos = sorted((DADOS / "raw").glob("CARGA_ENERGIA_*.parquet"))
    if not arquivos:
        sys.exit("Sem arquivos em dados/raw/. Rode antes: python baixar_carga_ons.py")
    partes = []
    for a in arquivos:
        df = pd.read_parquet(a)
        df["arquivo"] = a.name
        partes.append(df)
    raw = pd.concat(partes, ignore_index=True)
    raw["id_subsistema"] = raw["id_subsistema"].astype(str).str.strip()
    raw["instante"] = pd.to_datetime(raw["din_instante"])
    raw["data"] = raw["instante"].dt.normalize()
    raw["valor"] = pd.to_numeric(raw["val_cargaenergiamwmed"], errors="coerce")
    return raw


def ler_series() -> pd.DataFrame:
    """Matriz data x série (MWmed) a partir dos parquets consolidados."""
    cols = {}
    for s in SERIES:
        df = pd.read_parquet(DADOS / f"carga_{s}.parquet")
        cols[s] = df.set_index("din_instante")["val_cargaenergiamwmed"]
    return pd.DataFrame(cols).asfreq("D")


def problemas_brutos(raw: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for _, r in raw[raw["instante"] != raw["data"]].iterrows():
        linhas.append((r["id_subsistema"], r["data"], r["arquivo"], "horário diferente de 00:00", repr(r["val_cargaenergiamwmed"])))
    dup = raw[raw.duplicated(["id_subsistema", "data"], keep=False)]
    for _, r in dup.iterrows():
        linhas.append((r["id_subsistema"], r["data"], r["arquivo"], "data duplicada", repr(r["val_cargaenergiamwmed"])))
    for _, r in raw[raw["valor"].isna()].iterrows():
        linhas.append((r["id_subsistema"], r["data"], r["arquivo"], "valor ausente/não numérico", repr(r["val_cargaenergiamwmed"])))
    for _, r in raw[raw["valor"] <= 0].iterrows():
        linhas.append((r["id_subsistema"], r["data"], r["arquivo"], "valor não positivo", repr(r["val_cargaenergiamwmed"])))
    out = pd.DataFrame(linhas, columns=["subsistema", "data", "arquivo", "problema", "valor_original"])
    return out.sort_values(["data", "subsistema", "problema"]).reset_index(drop=True)


def cobertura(Y: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for periodo, ini in [("completo", None), ("estudo", INICIO_ESTUDO)]:
        sub = Y[ini:] if ini else Y
        esperado = pd.date_range(sub.index.min(), sub.index.max())
        for s in SERIES:
            y = sub[s]
            ausentes = y[y.isna()].index
            linhas.append({
                "periodo": periodo,
                "serie": s,
                "inicio": sub.index.min().date(),
                "fim": sub.index.max().date(),
                "dias_esperados": len(esperado),
                "dias_com_registro": int(y.index.isin(esperado).sum()),
                "dias_com_valor": int(y.notna().sum()),
                "dias_sem_valor": len(ausentes),
                "datas_sem_valor": ";".join(d.strftime("%Y-%m-%d") for d in ausentes),
            })
    return pd.DataFrame(linhas)


def checagem_sin(raw: pd.DataFrame, Y: pd.DataFrame) -> pd.DataFrame:
    soma = Y[SUBS].sum(axis=1, min_count=len(SUBS))
    dif = (Y["SIN"] - soma).abs()
    ok = Y["SIN"].notna()
    return pd.DataFrame([
        {"checagem": "subsistemas na fonte", "resultado": ",".join(sorted(raw["id_subsistema"].unique()))},
        {"checagem": "fonte contém linha agregada (SIN/total)?", "resultado": str(bool(raw["id_subsistema"].str.upper().isin(["SIN", "TOTAL", "BR"]).any()))},
        {"checagem": "registros por (subsistema, data) após consolidação", "resultado": "máx = 1" if not Y.index.duplicated().any() else "duplicado"},
        {"checagem": "dias em que SIN tem valor", "resultado": int(ok.sum())},
        {"checagem": "dias em que algum subsistema falta (SIN = NaN)", "resultado": int((~ok).sum())},
        {"checagem": "máx |SIN - (SE+S+NE+N)| em MWmed", "resultado": float(dif[ok].max())},
    ])


def extremos(Y: pd.DataFrame) -> pd.DataFrame:
    """Resíduo robusto: log(carga) menos a mediana do mesmo dia da semana em ±3 semanas
    (remove semana e nível local), padronizado por MAD móvel de 365 dias.
    Cada dia marcado é classificado como feriado/véspera, ponte ou outro."""
    fer = feriados(range(Y.index.year.min(), Y.index.year.max() + 1))
    um_dia = pd.Timedelta(days=1)
    linhas = []
    for s in SERIES:
        ly = np.log(Y[s].interpolate(limit_area="inside"))
        ref = pd.concat([ly.shift(k) for k in (-21, -14, -7, 7, 14, 21)], axis=1).median(axis=1)
        r = ly - ref
        centro = r.rolling(365, center=True, min_periods=180).median()
        mad = 1.4826 * (r - centro).abs().rolling(365, center=True, min_periods=180).median()
        z = r / mad
        for d, v in z[z.abs() > LIMIAR_Z].dropna().items():
            if d in fer:
                tipo, nome = "feriado/véspera", fer[d]
            elif (d - um_dia) in fer or (d + um_dia) in fer:
                tipo, nome = "ponte/adjacente a feriado", fer.get(d - um_dia) or fer.get(d + um_dia)
            elif (d.month == 12 and d.day >= 24) or (d.month == 1 and d.day <= 2):
                tipo, nome = "festas de fim de ano", ""
            else:
                tipo, nome = "outro", ""
            evento = next((e for i, f, e in EVENTOS if pd.Timestamp(i) <= d <= pd.Timestamp(f)), "")
            linhas.append({
                "serie": s,
                "data": d.date(),
                "dia_semana": d.day_name(),
                "carga_mwmed": float(Y.at[d, s]),
                "desvio_pct_vs_padrao": float(np.expm1(r.at[d]) * 100),
                "z_robusto": float(v),
                "tipo": tipo,
                "feriado": nome,
                "evento_conhecido": evento,
            })
    return pd.DataFrame(linhas).sort_values(["serie", "data"]).reset_index(drop=True)


def quebras(Y: pd.DataFrame) -> pd.DataFrame:
    """Compara a média de w dias antes e depois de cada data e o crescimento contra a
    mesma janela do ano anterior (remove a sazonalidade anual). O salto no crescimento
    anual (em p.p.) aproxima o efeito da mudança de definição."""
    linhas = []
    um_ano = pd.DateOffset(years=1)
    dia = pd.Timedelta(days=1)
    for nome, d in QUEBRAS.items():
        for janela in JANELAS_QUEBRA:
            w = pd.Timedelta(days=janela)
            for s in SERIES:
                y = Y[s]
                antes = y[d - w : d - dia].mean()
                depois = y[d : d + w - dia].mean()
                antes_aa = y[d - um_ano - w : d - um_ano - dia].mean()
                depois_aa = y[d - um_ano : d - um_ano + w - dia].mean()
                cresc_antes = antes / antes_aa - 1
                cresc_depois = depois / depois_aa - 1
                # Contra 2 anos antes: evita a base de 2020 (COVID) na quebra de 2021
                antes_2a = y[d - 2 * um_ano - w : d - 2 * um_ano - dia].mean()
                depois_2a = y[d - 2 * um_ano : d - 2 * um_ano + w - dia].mean()
                cresc2_antes = antes / antes_2a - 1
                cresc2_depois = depois / depois_2a - 1
                linhas.append({
                    "mudanca": nome,
                    "data": d.date(),
                    "janela_dias": janela,
                    "serie": s,
                    "media_antes": antes,
                    "media_depois": depois,
                    "var_pct_depois_vs_antes": (depois / antes - 1) * 100,
                    "cresc_anual_pct_antes": cresc_antes * 100,
                    "cresc_anual_pct_depois": cresc_depois * 100,
                    "salto_cresc_anual_pp": (cresc_depois - cresc_antes) * 100,
                    "cresc_2anos_pct_antes": cresc2_antes * 100,
                    "cresc_2anos_pct_depois": cresc2_depois * 100,
                    "salto_cresc_2anos_pp": (cresc2_depois - cresc2_antes) * 100,
                })
    return pd.DataFrame(linhas)


def contagens_anuais(raw: pd.DataFrame, Y: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    reg = raw.groupby([raw["data"].dt.year, "id_subsistema"]).size()
    for ano, g in Y.groupby(Y.index.year):
        dias_ano = 366 if pd.Timestamp(year=ano, month=1, day=1).is_leap_year else 365
        for s in SERIES:
            y = g[s]
            linhas.append({
                "ano": ano,
                "serie": s,
                "dias_no_ano": dias_ano,
                "registros_fonte": int(reg.get((ano, s), 0)) if s != "SIN" else None,
                "dias_com_valor": int(y.notna().sum()),
                "dias_sem_valor": int(y.isna().sum()),
                "media": y.mean(),
                "desvio_padrao": y.std(),
                "minimo": y.min(),
                "p05": y.quantile(0.05),
                "mediana": y.median(),
                "p95": y.quantile(0.95),
                "maximo": y.max(),
                "cv_pct": y.std() / y.mean() * 100,
            })
    out = pd.DataFrame(linhas)
    out["cresc_media_anual_pct"] = out.groupby("serie")["media"].pct_change() * 100
    return out


def estatisticas_periodo(Y: pd.DataFrame) -> pd.DataFrame:
    y = Y[INICIO_ESTUDO:]
    d = y.describe(percentiles=[0.01, 0.05, 0.5, 0.95, 0.99]).T
    d["assimetria"] = y.skew()
    d["curtose_excesso"] = y.kurt()
    d["cv_pct"] = d["std"] / d["mean"] * 100
    dl = np.log(y).diff()
    d["dp_dlog_pct"] = dl.std() * 100
    d["participacao_media_sin_pct"] = (y.div(y["SIN"], axis=0).mean() * 100)
    d.index.name = "serie"
    return d


def grafico_quebras(Y: pd.DataFrame, caminho: Path) -> None:
    y = Y["SIN"][INICIO_ESTUDO:]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(y.index, y, color="0.75", lw=0.5, label="SIN diário")
    ax.plot(y.index, y.rolling(28, center=True).mean(), color="C0", lw=1.2, label="Média móvel 28 dias")
    ax.plot(y.index, y.rolling(365, center=True).mean(), color="C3", lw=1.5, label="Média móvel 365 dias")
    for i, (nome, d) in enumerate(QUEBRAS.items()):
        ax.axvline(d, color="k", ls="--", lw=0.8)
        ax.text(d, 0.98 - 0.05 * i, " " + nome, transform=ax.get_xaxis_transform(), va="top", ha="left", fontsize=8)
    ax.set_ylabel("Carga (MWmed)")
    ax.set_title("Carga diária do SIN e mudanças de definição da ONS")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(caminho, dpi=120)
    plt.close(fig)


def grafico_participacao(Y: pd.DataFrame, caminho: Path) -> None:
    p = Y[SUBS].div(Y["SIN"], axis=0).rolling(28, center=True).mean() * 100
    p = p[INICIO_ESTUDO:]
    fig, ax = plt.subplots(figsize=(12, 4))
    for s in SUBS:
        ax.plot(p.index, p[s], lw=1, label=s)
    for d in QUEBRAS.values():
        ax.axvline(d, color="k", ls="--", lw=0.8)
    ax.set_ylabel("% do SIN (média móvel 28 dias)")
    ax.set_title("Participação dos subsistemas na carga do SIN")
    ax.legend(ncol=4)
    fig.tight_layout()
    fig.savefig(caminho, dpi=120)
    plt.close(fig)


def main() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    raw = ler_brutos()
    Y = ler_series()

    resultados = {
        "problemas_brutos": problemas_brutos(raw),
        "cobertura": cobertura(Y),
        "checagem_sin": checagem_sin(raw, Y),
        "extremos": extremos(Y),
        "quebras_definicao": quebras(Y),
        "contagens_anuais": contagens_anuais(raw, Y),
    }
    for nome, df in resultados.items():
        df.to_csv(SAIDA / f"{nome}.csv", index=False, float_format="%.4f")
    estatisticas_periodo(Y).to_csv(SAIDA / "estatisticas_periodo.csv", float_format="%.4f")

    grafico_quebras(Y, SAIDA / "serie_sin_quebras.png")
    grafico_participacao(Y, SAIDA / "participacao_subsistemas.png")

    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print("Fonte:", len(raw), "registros, de", raw["data"].min().date(), "a", raw["data"].max().date())
        print("\nProblemas na fonte:\n", resultados["problemas_brutos"].to_string(index=False))
        print("\nChecagem SIN:\n", resultados["checagem_sin"].to_string(index=False))
        q = resultados["quebras_definicao"]
        cols = ["mudanca", "janela_dias", "serie", "salto_cresc_anual_pp", "salto_cresc_2anos_pp"]
        print("\nQuebras (salto no crescimento, p.p.):\n", q[cols].round(2).to_string(index=False))
        ext = resultados["extremos"]
        ext = ext[pd.to_datetime(ext["data"]) >= INICIO_ESTUDO]
        print(f"\nExtremos |z|>{LIMIAR_Z} desde {INICIO_ESTUDO}, por tipo:\n", pd.crosstab(ext["serie"], ext["tipo"]))
        outros = ext.query("tipo == 'outro'").drop(columns=["feriado", "tipo"]).round(1)
        print("\nExtremos fora de feriados/festas:\n", outros.to_string(index=False))
    print(f"\nSaídas em {SAIDA.relative_to(RAIZ)}/")


if __name__ == "__main__":
    main()
