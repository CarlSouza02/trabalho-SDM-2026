import argparse
import datetime as dt
from pathlib import Path

import pandas as pd
import requests

API_URL = "https://dados.ons.org.br/api/3/action/package_show?id=carga-energia"
PASTA = Path(__file__).parent / "dados"
PASTA_RAW = PASTA / "raw"


def listar_parquets() -> list[str]:
    """Consulta a API CKAN da ONS e retorna as URLs dos .parquet."""
    resp = requests.get(API_URL, timeout=60)
    resp.raise_for_status()
    recursos = resp.json()["result"]["resources"]
    urls = [r["url"] for r in recursos if r.get("format", "").upper() == "PARQUET"]
    return sorted(urls)


def baixar(url: str, destino: Path, forcar: bool = False) -> None:
    ano_corrente = str(dt.date.today().year)
    # O arquivo do ano corrente é atualizado pela ONS, então sempre rebaixa.
    if destino.exists() and not forcar and ano_corrente not in destino.name:
        print(f"  já existe: {destino.name}")
        return
    print(f"  baixando: {destino.name}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = destino.with_suffix(".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.replace(destino)


def consolidar(arquivos: list[Path]) -> pd.DataFrame:
    df = pd.concat((pd.read_parquet(a) for a in arquivos), ignore_index=True)
    # Dados diários: trunca para o dia (há registros espúrios como 2013-02-02 00:00:01 no Sul)
    df["din_instante"] = pd.to_datetime(df["din_instante"]).dt.normalize()
    df["val_cargaenergiamwmed"] = pd.to_numeric(df["val_cargaenergiamwmed"], errors="coerce")
    df["id_subsistema"] = df["id_subsistema"].astype(str).str.strip()
    # Em datas duplicadas, prioriza a linha com valor (NaN vai para o início e é descartado)
    df = (
        df.sort_values("val_cargaenergiamwmed", na_position="first", kind="stable")
        .drop_duplicates(subset=["id_subsistema", "din_instante"], keep="last")
        .sort_values(["id_subsistema", "din_instante"])
        .reset_index(drop=True)
    )
    return df


def somar_sin(df: pd.DataFrame) -> pd.DataFrame:
    """Carga do SIN = soma dos submercados em cada dia.

    Se faltar o valor de algum submercado no dia, o SIN fica NaN
    (evita uma soma parcial que pareceria uma queda de carga).
    """
    n_subs = df["id_subsistema"].nunique()
    sin = (
        df.groupby("din_instante")["val_cargaenergiamwmed"]
        .sum(min_count=n_subs)
        .where(df.groupby("din_instante")["id_subsistema"].nunique() == n_subs)
        .rename("val_cargaenergiamwmed")
        .reset_index()
    )
    sin.insert(0, "id_subsistema", "SIN")
    sin.insert(1, "nom_subsistema", "Sistema Interligado Nacional")
    return sin


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forcar", action="store_true", help="rebaixa todos os arquivos")
    args = parser.parse_args()

    PASTA_RAW.mkdir(parents=True, exist_ok=True)

    print("Consultando lista de arquivos na ONS...")
    urls = listar_parquets()
    print(f"{len(urls)} arquivos parquet encontrados.")

    arquivos = []
    for url in urls:
        destino = PASTA_RAW / url.rsplit("/", 1)[-1]
        baixar(url, destino, args.forcar)
        arquivos.append(destino)

    print("Consolidando...")
    df = consolidar(arquivos)
    df.to_parquet(PASTA / "carga_todos_submercados.parquet", index=False)

    for sub, grupo in df.groupby("id_subsistema"):
        saida = PASTA / f"carga_{sub}.parquet"
        grupo.reset_index(drop=True).to_parquet(saida, index=False)
        print(
            f"  {sub:>2} ({grupo['nom_subsistema'].iloc[0]}): {len(grupo):>5} linhas, "
            f"{grupo['din_instante'].min():%Y-%m-%d} a {grupo['din_instante'].max():%Y-%m-%d} -> {saida.name}"
        )

    sin = somar_sin(df)
    sin.to_parquet(PASTA / "carga_SIN.parquet", index=False)
    print(
        f"  SIN (soma): {len(sin):>5} linhas, {sin['val_cargaenergiamwmed'].isna().sum()} NaN, "
        f"{sin['din_instante'].min():%Y-%m-%d} a {sin['din_instante'].max():%Y-%m-%d} -> carga_SIN.parquet"
    )

    print("Pronto.")


if __name__ == "__main__":
    main()
