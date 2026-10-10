"""
Coletor: tira um "retrato" dos niveis dos rios e acumula em dados/historico.csv.

Rodado pelo GitHub Actions (ver .github/workflows/coletar.yml) a cada ~15 min.
Colunas gravadas: coletado_em (UTC), codigo, rio_nivel (mm), chuva_h001 (mm).
Mantem apenas os ultimos RETENCAO_DIAS dias para o arquivo nao crescer sem limite.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from chuva_rios_rs import carregar_estacoes

ARQUIVO = Path("dados/historico.csv")
RETENCAO_DIAS = 10


def main() -> int:
    df, meta = carregar_estacoes()
    if "rio_nivel" not in df.columns:
        print("A API nao retornou dados de rio:", meta.get("erros"))
        return 1

    agora = datetime.now(timezone.utc).replace(microsecond=0)
    colunas = ["codigo", "rio_nivel"] + (["chuva_h001"] if "chuva_h001" in df else [])
    retrato = df.loc[df["rio_nivel"].notna(), colunas].copy()
    retrato.insert(0, "coletado_em", agora.strftime("%Y-%m-%dT%H:%M:%SZ"))
    print(f"{len(retrato)} estacoes de rio coletadas em {agora:%Y-%m-%d %H:%M}Z")

    if ARQUIVO.exists() and ARQUIVO.stat().st_size > 0:
        antigo = pd.read_csv(ARQUIVO)
        total = pd.concat([antigo, retrato], ignore_index=True)
    else:
        total = retrato

    corte = (agora - timedelta(days=RETENCAO_DIAS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    total = total[total["coletado_em"] >= corte]

    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    total.to_csv(ARQUIVO, index=False)
    print(f"{ARQUIVO}: {len(total)} linhas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
