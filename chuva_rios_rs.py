"""
Monitor de Chuva e Rios do RS  (Defesa Civil RS - Rede Hidrometeorologica)

Como rodar:
    pip install streamlit requests pandas altair urllib3
    streamlit run chuva_rios_rs.py

Fonte: API GraphQL publica (Com Query Whitelisting superada)
    https://redehidrometeorologica.defesacivil.rs.gov.br/graphql
"""
from __future__ import annotations

import io
import json
import os
import urllib3
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import requests
import streamlit as st

# Desabilita os avisos de InsecureRequestWarning gerados pelo verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --------------------------------------------------------------------------- #
# Configuracao
# --------------------------------------------------------------------------- #
API_URL = "https://redehidrometeorologica.defesacivil.rs.gov.br/graphql"
CLIENT = "casa-militar-defesa-civil-rs"
SYSTEM = "Qualle_Hidrometeorologia"
FUSO = "America/Sao_Paulo"
TIMEOUT = 45
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (monitor-chuva-rios-rs)",
}

HISTORICO_URL = os.environ.get(
    "HISTORICO_URL",
    "https://raw.githubusercontent.com/jhona1234-del/Rios/dados/historico.csv",
)

JANELAS_CHUVA = {
    "1 hora": "h001",
    "3 horas": "h003",
    "6 horas": "h006",
    "12 horas": "h012",
    "24 horas": "h024",
    "48 horas": "h048",
    "7 dias": "h168",
}

INTERVALOS_HIST = {
    "5 minutos": "MIN_5",
    "15 minutos": "MIN_15",
    "30 minutos": "MIN_30",
    "1 hora": "HOUR_1",
    "3 horas": "HOUR_3",
    "6 horas": "HOUR_6",
    "12 horas": "HOUR_12",
    "24 horas": "HOUR_24",
}

# --------------------------------------------------------------------------- #
# Queries Exatas (Whitelisted pelo Firewall da Defesa Civil)
# --------------------------------------------------------------------------- #
QUERY_TAGS_DATA = """query Tags_data {
  tags_data(clients: ["casa-militar-defesa-civil-rs"]) {
    qualle_meteorologia {
      codigo
      name {
        prefix
        general
        local
      }
      show
      timestamp
      position {
        bacia
        latitude
        longitude
        regiao
        altitude
        filtros {
          outros {
            crepdec {
              nome {
                value
              }
              codigo {
                value
              }
            }
          }
        }
      }
      data {
        rio {
          rio_alarmes {
            inundacao {
              ativo {
                value
              }
              status {
                value
              }
            }
          }
          rio_nome {
            value
          }
          rio_nivel {
            value
          }
          rio_nivel_tendencia {
            value
          }
          rio_area_drenagem {
            value
          }
          homologacao {
            relacao {
              valido {
                value
              }
            }
          }
        }
        chuva {
          acumulado {
            min005 {
              value
            }
            h001 {
              value
            }
            h003 {
              value
            }
            h006 {
              value
            }
            h012 {
              value
            }
            h024 {
              value
            }
            h048 {
              value
            }
            h168 {
              value
            }
          }
          homologacao {
            relacao {
              valido {
                value
              }
            }
          }
        }
        pressaoatmos {
          atual {
            value
          }
          historico {
            diaanterior {
              media {
                value
              }
            }
            diaatual {
              media {
                value
              }
            }
          }
          tendencia {
            value
          }
          homologacao {
            relacao {
              valido {
                value
              }
            }
          }
        }
        senstermica {
          atual {
            value
          }
          historico {
            diaatual {
              media {
                value
              }
            }
            diaanterior {
              media {
                value
              }
            }
          }
          tendencia {
            value
          }
          homologacao {
            relacao {
              valido {
                value
              }
            }
          }
        }
        radiacaosolar {
          atual {
            value
          }
          homologacao {
            relacao {
              valido {
                value
              }
            }
          }
        }
        temperatura {
          atual {
            value
          }
          historico {
            diaanterior {
              media {
                value
              }
            }
            diaatual {
              media {
                value
              }
              maxima {
                value
              }
              minima {
                value
              }
            }
          }
          tendencia {
            value
          }
          homologacao {
            relacao {
              valido {
                value
              }
            }
          }
        }
        umidade {
          atual {
            value
          }
          historico {
            diaanterior {
              media {
                value
              }
            }
            diaatual {
              media {
                value
              }
            }
          }
          tendencia {
            value
          }
          homologacao {
            relacao {
              valido {
                value
              }
            }
          }
        }
        vento {
          direcao {
            value
          }
          velocidade_maxima {
            value
          }
          velocidade_media {
            value
          }
          homologacao {
            relacao {
              valido {
                value
              }
            }
          }
        }
      }
      type
      filter {
        relacao {
          tem_chuva_acumulada
          tem_nivel_do_rio
          tem_pressao_atmosferica
          tem_sensacao_termica
          tem_umidade
          tem_vazao_do_rio
          tem_vento
        }
      }
      resource {
        estacao {
          estado {
            manutencao {
              value
            }
          }
        }
      }
    }
    proximaAtualizacaoEm
  }
}"""

QUERY_HISTORIC = """query Historic($stationCode: String!, $startDate: String!, $endDate: String!, $interval: QueryInterval) {
  historic(
    system: Qualle_Hidrometeorologia
    client: "casa-militar-defesa-civil-rs"
    stationCode: $stationCode
    startDate: $startDate
    endDate: $endDate
    interval: $interval
    opts: { ordenacao: ASC }
  )
}"""

class ApiError(RuntimeError):
    pass

# --------------------------------------------------------------------------- #
# Camada de acesso a API
# --------------------------------------------------------------------------- #
def gql(query: str, variables: dict = None) -> dict:
    """Envia uma consulta GraphQL e devolve o JSON de resposta."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
        
    resp = requests.post(
        API_URL, json=payload, headers=HEADERS, timeout=TIMEOUT, verify=False
    )
    try:
        return resp.json()
    except ValueError:
        resp.raise_for_status()
        raise ApiError(f"Resposta nao-JSON da API (HTTP {resp.status_code}).")

def _achar_estacoes(obj):
    """Percorre o JSON e devolve todos os dicts que parecem uma estacao."""
    if isinstance(obj, dict):
        if "codigo" in obj and ("data" in obj or "position" in obj):
            yield obj
        else:
            for v in obj.values():
                yield from _achar_estacoes(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _achar_estacoes(item)

def _val(d, *path):
    """Navega em dicts aninhados e desembrulha {'value': x}."""
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    if isinstance(d, dict) and "value" in d:
        d = d["value"]
    return d

def _estacao_para_linha(est: dict) -> dict:
    nome = est.get("name") or {}

    def txt(k):
        v = nome.get(k)
        return v.strip() if isinstance(v, str) and v.strip() else None

    prefixo, geral, local = txt("prefix"), txt("general"), txt("local")
    partes: list[str] = []
    for p in (geral, local):
        if p and p not in partes:
            partes.append(p)
    descricao = " - ".join(partes) or prefixo or est.get("codigo")
    cidade = local or geral

    pos = est.get("position") or {}
    linha = {
        "codigo": est.get("codigo"),
        "descricao": descricao,
        "cidade": cidade,
        "bacia": pos.get("bacia"),
        "regiao": pos.get("regiao"),
        "lat": pos.get("latitude"),
        "lon": pos.get("longitude"),
        "altitude": pos.get("altitude"),
        "timestamp": est.get("timestamp"),
        "rio_nome": _val(est, "data", "rio", "rio_nome"),
        "rio_nivel": _val(est, "data", "rio", "rio_nivel"),  # em mm
        "rio_tendencia": _val(est, "data", "rio", "rio_nivel_tendencia"),
        "rio_area": _val(est, "data", "rio", "rio_area_drenagem"),
    }
    acum = _val(est, "data", "chuva", "acumulado")
    acum = acum if isinstance(acum, dict) else {}
    for campo in JANELAS_CHUVA.values():
        v = acum.get(campo)
        linha[f"chuva_{campo}"] = v.get("value") if isinstance(v, dict) else v
    return linha

def _para_local(dt: pd.Series) -> pd.Series:
    if getattr(dt.dt, "tz", None) is not None:
        return dt.dt.tz_convert(FUSO).dt.tz_localize(None)
    return dt

def _parse_ts(serie: pd.Series) -> pd.Series:
    num = pd.to_numeric(serie, errors="coerce")
    if num.notna().mean() > 0.5:
        med = num.median()
        unit = "ms" if med > 1e11 else "s" if med > 1e8 else None
        if unit:
            return _para_local(pd.to_datetime(num, unit=unit, utc=True, errors="coerce"))
    try:
        dt = pd.to_datetime(serie, errors="coerce")
    except (ValueError, TypeError):
        dt = pd.to_datetime(serie, errors="coerce", utc=True)
    if not pd.api.types.is_datetime64_any_dtype(dt):
        dt = pd.to_datetime(serie, errors="coerce", utc=True)
    return _para_local(dt)

def agora_local() -> pd.Timestamp:
    return pd.Timestamp.now(tz=FUSO).tz_localize(None)

def montar_dataframe(payload: dict) -> pd.DataFrame:
    linhas = [_estacao_para_linha(e) for e in _achar_estacoes(payload.get("data"))]
    df = pd.DataFrame(linhas)
    if df.empty:
        return df
    df = df.drop_duplicates(subset="codigo", keep="last").reset_index(drop=True)

    num_cols = ["lat", "lon", "altitude", "rio_nivel", "rio_area"] + [
        c for c in df.columns if c.startswith("chuva_")
    ]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ultima_leitura"] = _parse_ts(df["timestamp"])
    df["bacia"] = df["bacia"].fillna("(sem bacia)").astype(str)
    df["cidade"] = df["cidade"].fillna("(sem cidade)").astype(str)
    df["descricao"] = df["descricao"].fillna(df["codigo"]).astype(str)

    dup = df["descricao"].duplicated(keep=False)
    df["rotulo"] = df["descricao"].where(~dup, df["descricao"] + " (" + df["codigo"] + ")")
    return df

@st.cache_data(ttl=120, show_spinner=False)
def carregar_estacoes() -> tuple[pd.DataFrame, dict]:
    """Usa a query autorizada estática."""
    try:
        payload = gql(QUERY_TAGS_DATA)
    except Exception as exc:
        raise ApiError(f"Erro na conexão com API: {exc}")
        
    if payload.get("errors"):
        msgs = "; ".join(str(e.get("message")) for e in payload["errors"][:3])
        raise ApiError(f"GraphQL: {msgs}")
        
    df = montar_dataframe(payload)
    if df.empty:
        raise ApiError("Resposta sem estações reconhecíveis.")
        
    amostra = next(_achar_estacoes(payload.get("data")), {})
    return df, {"nivel": "completa_oficial", "erros": [], "amostra": amostra}

@st.cache_data(ttl=300, show_spinner=False)
def carregar_historico(codigo: str, inicio: str, fim: str, intervalo: str):
    """Envia a query autorizada com as variaveis."""
    variables = {
        "stationCode": codigo,
        "startDate": inicio,
        "endDate": fim,
        "interval": intervalo
    }
    payload = gql(QUERY_HISTORIC, variables=variables)
    if payload.get("errors") and not payload.get("data"):
        msgs = "; ".join(str(e.get("message")) for e in payload["errors"][:3])
        raise ApiError(msgs)
    return payload.get("data", {}).get("historic")

def historico_para_df(obj) -> pd.DataFrame:
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except ValueError:
            return pd.DataFrame()

    def achar_lista(o):
        if isinstance(o, list) and o and all(isinstance(i, dict) for i in o):
            return o
        if isinstance(o, dict):
            for v in o.values():
                r = achar_lista(v)
                if r is not None:
                    return r
        return None

    lista = achar_lista(obj)
    if lista is None:
        return pd.DataFrame()
    df = pd.json_normalize(lista)

    chaves = ("timestamp", "datetime", "date", "data", "time", "hora", "dt")
    for col in df.columns:
        if any(k in col.lower() for k in chaves):
            t = _parse_ts(df[col])
            if t.notna().mean() > 0.8:
                df[col] = t
                df = df.set_index(col).sort_index()
                break
    for col in df.columns:
        conv = pd.to_numeric(df[col], errors="coerce")
        if conv.notna().mean() > 0.5:
            df[col] = conv
    return df

@st.cache_data(ttl=300, show_spinner=False)
def carregar_coleta() -> pd.DataFrame:
    try:
        resp = requests.get(HISTORICO_URL, timeout=20, headers=HEADERS)
        if resp.status_code != 200:
            return pd.DataFrame()
        df = pd.read_csv(io.StringIO(resp.text))
    except Exception:
        return pd.DataFrame()
    if not {"coletado_em", "codigo", "rio_nivel"} <= set(df.columns):
        return pd.DataFrame()
    t = pd.to_datetime(df["coletado_em"], errors="coerce", utc=True)
    df["quando"] = t.dt.tz_convert(FUSO).dt.tz_localize(None)
    df["rio_nivel"] = pd.to_numeric(df["rio_nivel"], errors="coerce")
    if "chuva_h001" in df:
        df["chuva_h001"] = pd.to_numeric(df["chuva_h001"], errors="coerce")
    return df.dropna(subset=["quando"]).sort_values("quando").reset_index(drop=True)

# --------------------------------------------------------------------------- #
# Calculos de variacao do nivel
# --------------------------------------------------------------------------- #
HORIZONTES = (1, 3, 6, 24)

def calcular_variacoes(serie: pd.Series) -> dict:
    s = serie.dropna()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if len(s) < 2:
        return {}
    t_fim, v_fim = s.index[-1], float(s.iloc[-1])
    out: dict = {"atual": v_fim, "t_fim": t_fim}
    for h in HORIZONTES:
        t_ref = t_fim - pd.Timedelta(hours=h)
        pos = s.index.searchsorted(t_ref, side="right") - 1
        if pos < 0 or t_ref - s.index[pos] > pd.Timedelta(minutes=max(40, 10 * h)):
            out[f"d{h}"] = None
        else:
            out[f"d{h}"] = v_fim - float(s.iloc[pos])
    return out

def variacoes_todas(coleta: pd.DataFrame, niveis_atuais: dict) -> pd.DataFrame:
    agora = agora_local()
    linhas = []
    sub = coleta[coleta["codigo"].isin(niveis_atuais)]
    for cod, g in sub.groupby("codigo"):
        s = g.set_index("quando")["rio_nivel"].copy()
        atual = niveis_atuais.get(cod)
        if atual is not None and pd.notna(atual) and agora > s.index.max():
            s.loc[agora] = float(atual)
        v = calcular_variacoes(s)
        if v:
            linhas.append({"codigo": cod, **{f"d{h}": v.get(f"d{h}") for h in HORIZONTES}})
    cols = ["codigo"] + [f"d{h}" for h in HORIZONTES]
    return pd.DataFrame(linhas, columns=cols)

def situacao(delta_1h, limiar: float) -> str | None:
    if delta_1h is None or pd.isna(delta_1h):
        return None
    if delta_1h > limiar:
        return "⬆️ subindo"
    if delta_1h < -limiar:
        return "⬇️ descendo"
    return "➡️ estável"

# --------------------------------------------------------------------------- #
# Utilidades de interface
# --------------------------------------------------------------------------- #
def fmt_mm(v, casas: int = 0) -> str:
    if v is None or pd.isna(v):
        return "-"
    s = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} mm"

def seta_tendencia(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "-"
    try:
        f = float(v)
        seta = "⬆️ subindo" if f > 0 else "⬇️ descendo" if f < 0 else "➡️ estável"
        return f"{seta} ({f:+g})"
    except (TypeError, ValueError):
        s = str(v).lower()
        if any(k in s for k in ("desc", "baix", "dec", "down", "fall")):
            return f"⬇️ {v}"
        if any(k in s for k in ("sub", "cres", "up", "rise")):
            return f"⬆️ {v}"
        if any(k in s for k in ("est", "stab", "const")):
            return f"➡️ {v}"
        return str(v)

def barras(d: pd.DataFrame, cat: str, val: str, titulo: str, cor: str):
    chart = (
        alt.Chart(d)
        .mark_bar(color=cor)
        .encode(
            y=alt.Y(f"{cat}:N", sort="-x", title=None),
            x=alt.X(f"{val}:Q", title=titulo),
            tooltip=[cat, alt.Tooltip(val, format=".1f", title=titulo)],
        )
        .properties(height=max(180, 26 * len(d)))
    )
    st.altair_chart(chart)

def agregar(df: pd.DataFrame, por: str, col: str) -> pd.DataFrame:
    base = df.dropna(subset=[col])
    if por == "Estação":
        out = base[["rotulo", col]].rename(columns={col: "valor"})
        out["estacoes"] = 1
        return out
    chave = "bacia" if por == "Bacia" else "cidade"
    g = base.groupby(chave).agg(valor=(col, "max"), estacoes=("codigo", "count"))
    return g.reset_index().rename(columns={chave: "rotulo"})

def filtros_laterais(df: pd.DataFrame) -> pd.DataFrame:
    with st.sidebar:
        st.header("Filtros")
        if st.button("🔄 Atualizar dados", type="primary"):
            st.cache_data.clear()
            st.rerun()
        st.caption("Os dados ficam em cache por 2 minutos.")

        bacias = sorted(df["bacia"].unique())
        sel_bacias = st.multiselect("Bacia hidrográfica", bacias, placeholder="Todas")
        df_b = df[df["bacia"].isin(sel_bacias)] if sel_bacias else df

        cidades = sorted(df_b["cidade"].unique())
        sel_cidades = st.multiselect("Cidade / local", cidades, placeholder="Todas")
        df_c = df_b[df_b["cidade"].isin(sel_cidades)] if sel_cidades else df_b

        estacoes = sorted(df_c["rotulo"].unique())
        sel_est = st.multiselect("Estação (descrição)", estacoes, placeholder="Todas")

        busca = st.text_input("Buscar", placeholder="descrição, rio ou código")

    out = df_c
    if sel_est:
        out = out[out["rotulo"].isin(sel_est)]
    if busca.strip():
        b = busca.strip()
        mask = (
            out["descricao"].astype(str).str.contains(b, case=False, regex=False)
            | out["codigo"].astype(str).str.contains(b, case=False, regex=False)
            | out["rio_nome"].astype(str).str.contains(b, case=False, regex=False)
        )
        out = out[mask]
    return out

# --------------------------------------------------------------------------- #
# Aba Rios
# --------------------------------------------------------------------------- #
def _serie_do_rio(cod: str, coleta: pd.DataFrame, horas: int, intervalo: str):
    if coleta is not None and not coleta.empty:
        g = coleta[coleta["codigo"] == cod]
        if len(g) >= 2:
            g = g.set_index("quando")
            chuva = g["chuva_h001"] if "chuva_h001" in g else None
            return g["rio_nivel"], chuva, "coleta própria (a cada ~15 min)"

    fim = datetime.now().replace(second=0, microsecond=0)
    ini = fim - timedelta(hours=horas)
    fmt = "%Y-%m-%d %H:%M:%S"
    try:
        bruto = carregar_historico(cod, ini.strftime(fmt), fim.strftime(fmt), intervalo)
    except Exception as exc:
        return None, None, f"erro na API de histórico: {exc}"
    tab = historico_para_df(bruto)
    if tab.empty or not isinstance(tab.index, pd.DatetimeIndex):
        return None, None, "a API de histórico respondeu em formato não reconhecido"
    numericas = [c for c in tab.columns if pd.api.types.is_numeric_dtype(tab[c])]
    if not numericas:
        return None, None, "histórico sem colunas numéricas"
    palpite = next((c for c in numericas if "nivel" in c.lower()), None) \
        or next((c for c in numericas if "rio" in c.lower()), numericas[0])
    col = st.selectbox("Coluna do nível no histórico da API", numericas,
                       index=numericas.index(palpite), key=f"colnivel_{cod}")
    return tab[col], None, "histórico da API da Defesa Civil"

def detalhe_rio(r: pd.DataFrame, coleta: pd.DataFrame, limiar: float):
    st.subheader("Detalhe da estação")
    r = r.sort_values(["rio", "descricao"])
    rotulos = {
        row.codigo: f"{row.rio} · {row.descricao}" if row.rio != "(sem nome)" else row.descricao
        for row in r.itertuples()
    }
    codigos = list(r["codigo"])
    padrao = codigos.index(r.loc[r["rio_nivel"].idxmax(), "codigo"])
    cod = st.selectbox("Estação", codigos, index=padrao, format_func=lambda c: rotulos[c])
    est = r[r["codigo"] == cod].iloc[0]

    periodo = st.radio("Período do gráfico", ["6 horas", "24 horas", "3 dias", "7 dias"],
                       index=1, horizontal=True)
    horas = {"6 horas": 6, "24 horas": 24, "3 dias": 72, "7 dias": 168}[periodo]
    intervalo = {"6 horas": "MIN_15", "24 horas": "MIN_15",
                 "3 dias": "HOUR_1", "7 dias": "HOUR_1"}[periodo]

    serie, chuva, fonte = _serie_do_rio(cod, coleta, max(horas, 24), intervalo)
    if serie is None:
        st.info(f"Sem série histórica para esta estação ({fonte}). "
                "Ative a coleta automática no GitHub para guardar o histórico.")
        st.metric("Nível atual", fmt_mm(est["rio_nivel"]))
        return

    serie = serie.dropna()
    serie = serie[~serie.index.duplicated(keep="last")].sort_index()
    agora = agora_local()
    if pd.notna(est["rio_nivel"]) and agora > serie.index.max():
        serie.loc[agora] = float(est["rio_nivel"])
    var = calcular_variacoes(serie)

    d1 = var.get("d1")
    sit = situacao(d1, limiar) or seta_tendencia(est["rio_tendencia"])

    a, b = st.columns(2)
    a.metric("Nível atual", fmt_mm(est["rio_nivel"]))
    b.metric("Situação", sit)
    c, d = st.columns(2)
    for col, h in ((c, 1), (d, 3)):
        v = var.get(f"d{h}")
        col.metric(f"Variação em {h} h", "n/d" if v is None else fmt_mm(v),
                   None if v is None else f"{v / h:+.1f} mm/h",
                   delta_color="inverse")
    e, f = st.columns(2)
    for col, h in ((e, 6), (f, 24)):
        v = var.get(f"d{h}")
        col.metric(f"Variação em {h} h", "n/d" if v is None else fmt_mm(v),
                   None if v is None else f"{v / h:+.1f} mm/h",
                   delta_color="inverse")
    st.caption("A velocidade é a variação do nível dividida pelas horas. "
               "Em vermelho: nível subindo.")

    corte = serie.index.max() - pd.Timedelta(hours=horas)
    vis = serie[serie.index >= corte]
    if len(vis) >= 2:
        d_ = vis.rename("nivel").reset_index()
        d_.columns = ["quando", "nivel"]
        linha = (
            alt.Chart(d_)
            .mark_line(point=len(d_) <= 60, color="#0f9d8a")
            .encode(
                x=alt.X("quando:T", title=None),
                y=alt.Y("nivel:Q", title="Nível (mm)", scale=alt.Scale(zero=False)),
                tooltip=[alt.Tooltip("quando:T", title="Quando", format="%d/%m %H:%M"),
                         alt.Tooltip("nivel:Q", title="Nível (mm)", format=".0f")],
            )
            .properties(height=260)
        )
        st.altair_chart(linha)
        if chuva is not None and chuva.notna().any():
            ch = chuva[chuva.index >= corte].dropna().rename("chuva").reset_index()
            ch.columns = ["quando", "chuva"]
            area = (
                alt.Chart(ch)
                .mark_area(color="#2b7de9", opacity=0.6)
                .encode(x=alt.X("quando:T", title=None),
                        y=alt.Y("chuva:Q", title="Chuva na última 1 h (mm)"),
                        tooltip=[alt.Tooltip("quando:T", format="%d/%m %H:%M"),
                                 alt.Tooltip("chuva:Q", format=".1f")])
                .properties(height=110)
            )
            st.altair_chart(area)
        st.caption(f"Fonte: {fonte}.")
        st.download_button("⬇️ Baixar série (CSV)", vis.rename("nivel_mm").to_csv().encode("utf-8"),
                           file_name=f"nivel_{cod}.csv", mime="text/csv")
    else:
        st.info("Poucos pontos no período escolhido para desenhar o gráfico.")

    extras = {
        "Rio": est["rio"], "Descrição": est["descricao"], "Código": cod,
        "Cidade/local": est["cidade"], "Bacia": est["bacia"], "Região": est["regiao"],
        "Altitude": est["altitude"], "Área de drenagem": est["rio_area"],
        "Máx. no período": fmt_mm(vis.max()) if len(vis) else "-",
        "Mín. no período": fmt_mm(vis.min()) if len(vis) else "-",
        "Chuva 1 h": fmt_mm(est.get("chuva_h001"), 1),
        "Chuva 24 h": fmt_mm(est.get("chuva_h024"), 1),
        "Chuva 7 dias": fmt_mm(est.get("chuva_h168"), 1),
        "Última leitura": est["ultima_leitura"],
    }
    tabela = pd.DataFrame({"Campo": list(extras), "Valor": [str(v) for v in extras.values()]})
    with st.expander("Dados da estação"):
        st.dataframe(tabela, hide_index=True)

def aba_rios(df: pd.DataFrame, coleta: pd.DataFrame):
    if "rio_nivel" not in df or df["rio_nivel"].notna().sum() == 0:
        st.info("Nenhuma estação com nível de rio nos filtros atuais.")
        return
    r = df.dropna(subset=["rio_nivel"]).copy()
    rn = r["rio_nome"].fillna("").astype(str).str.strip()
    r["rio"] = rn.where(rn != "", "(sem nome)")
    r["tendencia_api"] = r["rio_tendencia"].map(seta_tendencia)

    with st.expander("Ajustes"):
        limiar = st.slider("Considerar 'estável' quando a variação em 1 h for menor que (mm/h)",
                           0, 100, 5, key="limiar")

    tem_hist = coleta is not None and not coleta.empty
    if tem_hist:
        var = variacoes_todas(coleta, dict(zip(r["codigo"], r["rio_nivel"])))
        r = r.merge(var, on="codigo", how="left")
    for h in HORIZONTES:
        if f"d{h}" not in r:
            r[f"d{h}"] = float("nan")
    r["situacao"] = [situacao(d, limiar) or t for d, t in zip(r["d1"], r["tendencia_api"])]

    subindo = int(r["situacao"].str.contains("⬆️").sum())
    descendo = int(r["situacao"].str.contains("⬇️").sum())
    maior = r.loc[r["rio_nivel"].idxmax()]
    m1, m2 = st.columns(2)
    m1.metric("Estações de rio", len(r))
    m2.metric("Maior nível", fmt_mm(maior["rio_nivel"]), maior["descricao"], delta_color="off")
    m3, m4 = st.columns(2)
    m3.metric("Subindo", subindo)
    m4.metric("Descendo", descendo)
    if not tem_hist:
        st.caption("Situação segundo a API. Com a coleta automática ativa, aparecem também "
                   "variação e velocidade (mm/h) de todas as estações.")

    st.subheader("Visão geral")
    c1, c2 = st.columns(2)
    por = c1.radio("Agrupar por", ["Estação", "Bacia", "Cidade"], key="rio_por")
    opcoes_ord = ["Maior nível", "Rio (A-Z)"]
    if tem_hist:
        opcoes_ord.insert(1, "Subindo mais rápido")
    ordem = c2.radio("Ordenar tabela por", opcoes_ord, key="rio_ordem")

    agg = agregar(r, por, "rio_nivel").sort_values("valor", ascending=False).head(20)
    suf = "" if por == "Estação" else " (máx. do grupo)"
    barras(agg, "rotulo", "valor", f"Nível do rio (mm){suf}", "#0f9d8a")

    if ordem == "Maior nível":
        r = r.sort_values("rio_nivel", ascending=False)
    elif ordem == "Subindo mais rápido":
        r = r.sort_values("d1", ascending=False, na_position="last")
    else:
        r = r.sort_values(["rio", "descricao"])

    cols = ["rio", "descricao", "cidade", "bacia", "rio_nivel", "situacao"]
    cfg = {
        "rio": "Rio", "descricao": "Descrição", "cidade": "Cidade/local", "bacia": "Bacia",
        "rio_nivel": st.column_config.NumberColumn("Nível (mm)", format="%.0f"),
        "situacao": "Situação",
        "d1": st.column_config.NumberColumn("Vel. 1 h (mm/h)", format="%.0f"),
        "d3": st.column_config.NumberColumn("Var. 3 h (mm)", format="%.0f"),
        "d6": st.column_config.NumberColumn("Var. 6 h (mm)", format="%.0f"),
        "d24": st.column_config.NumberColumn("Var. 24 h (mm)", format="%.0f"),
        "rio_area": st.column_config.NumberColumn("Área drenagem", format="%.0f"),
        "ultima_leitura": "Última leitura",
    }
    if tem_hist:
        cols += ["d1", "d3", "d6", "d24"]
    cols += ["rio_area", "ultima_leitura"]
    st.dataframe(r[cols], column_config=cfg, hide_index=True)

    st.divider()
    detalhe_rio(r, coleta, limiar)

# --------------------------------------------------------------------------- #
# Demais abas
# --------------------------------------------------------------------------- #
def aba_chuva(df: pd.DataFrame):
    janelas = {
        r: c for r, c in JANELAS_CHUVA.items()
        if f"chuva_{c}" in df and df[f"chuva_{c}"].notna().any()
    }
    if not janelas:
        st.info("Nenhuma estação com dado de chuva nos filtros atuais.")
        return
    c1, c2, c3 = st.columns([2, 2, 1])
    rotulo_j = c1.selectbox(
        "Chuva acumulada nas últimas", list(janelas), index=min(4, len(janelas) - 1)
    )
    por = c2.radio("Agrupar por", ["Estação", "Bacia", "Cidade"], horizontal=True)
    topn = c3.selectbox("Mostrar", [10, 20, 50], index=1)
    col = f"chuva_{janelas[rotulo_j]}"

    base = df.dropna(subset=[col])
    maior = base.loc[base[col].idxmax()]
    m1, m2, m3 = st.columns(3)
    m1.metric("Estações com dado", len(base))
    m2.metric("Maior acumulado", f"{maior[col]:.1f} mm", maior["descricao"], delta_color="off")
    m3.metric("Média das estações", f"{base[col].mean():.1f} mm")

    agg = agregar(df, por, col).sort_values("valor", ascending=False).head(topn)
    suf = "" if por == "Estação" else " (máx. do grupo)"
    barras(agg, "rotulo", "valor", f"Chuva {rotulo_j} (mm){suf}", "#2b7de9")

    with st.expander("Tabela completa", expanded=False):
        cols = ["descricao", "cidade", "bacia"] + [f"chuva_{c}" for c in janelas.values()]
        cols += ["ultima_leitura"]
        cfg = {
            f"chuva_{c}": st.column_config.NumberColumn(f"{r} (mm)", format="%.1f")
            for r, c in janelas.items()
        }
        cfg[col] = st.column_config.ProgressColumn(
            f"{rotulo_j} (mm)", format="%.1f",
            min_value=0.0, max_value=float(max(base[col].max(), 1)),
        )
        cfg.update({"descricao": "Descrição", "cidade": "Cidade/local", "bacia": "Bacia",
                    "ultima_leitura": "Última leitura"})
        st.dataframe(df.sort_values(col, ascending=False)[cols],
                     column_config=cfg, hide_index=True)

def aba_mapa(df: pd.DataFrame):
    modo = st.radio("Mostrar no mapa", ["Chuva", "Nível do rio"], horizontal=True)
    if modo == "Chuva":
        janelas = {r: c for r, c in JANELAS_CHUVA.items()
                   if f"chuva_{c}" in df and df[f"chuva_{c}"].notna().any()}
        if not janelas:
            st.info("Sem dados de chuva para exibir.")
            return
        rj = st.selectbox("Janela", list(janelas), index=min(4, len(janelas) - 1),
                          key="mapa_j")
        col, cor = f"chuva_{janelas[rj]}", "#2b7de9"
    else:
        col, cor = "rio_nivel", "#0f9d8a"
        if col not in df:
            st.info("Sem dados de rio para exibir.")
            return
        m = df.dropna(subset=["lat", "lon", col]).copy()
        if m.empty:
            st.info("Nenhuma estação com coordenadas e dado para esse filtro.")
            return
        valor = m[col].clip(lower=0)
        m["tamanho"] = 1500 + 12000 * valor / max(float(valor.max()), 1.0)
        st.map(m, latitude="lat", longitude="lon", size="tamanho", color=cor)
        st.caption("O tamanho do círculo é proporcional ao valor medido.")

def aba_historico(df: pd.DataFrame):
    st.write("Série histórica de qualquer estação, direto da API.")
    opcoes = df.sort_values("descricao").set_index("codigo")
    codigo = st.selectbox(
        "Estação", list(opcoes.index),
        format_func=lambda c: f"{opcoes.loc[c, 'descricao']}  ({c})",
    )
    c1, c2 = st.columns(2)
    periodo = c1.selectbox("Período", ["Últimas 24 horas", "Últimos 3 dias",
                                       "Últimos 7 dias"])
    intervalo_lbl = c2.selectbox("Agregação", list(INTERVALOS_HIST), index=3)
    horas = {"Últimas 24 horas": 24, "Últimos 3 dias": 72, "Últimos 7 dias": 168}[periodo]

    fim = datetime.now().replace(second=0, microsecond=0)
    ini = fim - timedelta(hours=horas)
    fmt = "%Y-%m-%d %H:%M:%S"

    if not st.button("Carregar histórico"):
        return
    try:
        bruto = carregar_historico(codigo, ini.strftime(fmt), fim.strftime(fmt),
                                   INTERVALOS_HIST[intervalo_lbl])
    except Exception as exc:
        st.error(f"Não foi possível obter o histórico: {exc}")
        return
    tab = historico_para_df(bruto)
    if tab.empty:
        st.warning("A API respondeu, mas não consegui montar uma tabela. "
                   "Veja a resposta bruta abaixo.")
    else:
        numericas = [c for c in tab.columns if pd.api.types.is_numeric_dtype(tab[c])]
        if numericas:
            sel = st.multiselect("Séries no gráfico", numericas, default=numericas[:3])
            if sel:
                st.line_chart(tab[sel])
        st.dataframe(tab)
        st.download_button("⬇️ Baixar CSV", tab.to_csv().encode("utf-8"),
                           file_name=f"historico_{codigo}.csv", mime="text/csv")
    with st.expander("Resposta bruta da API"):
        st.json(bruto if not isinstance(bruto, str) else {"historic": bruto})

def aba_diagnostico(meta: dict | None, erro: str | None = None,
                    coleta: pd.DataFrame | None = None):
    st.write("Útil para descobrir quais dados a API realmente oferece.")
    if erro:
        st.error("Falhas ao buscar estações:")
        st.code(erro)
    if meta:
        st.write(f"Consulta bem-sucedida no nível: **{meta['nivel']}**")
        if meta["erros"]:
            st.warning("Tentativas anteriores que falharam:")
            st.code("\n".join(meta["erros"]))
        with st.expander("Exemplo de estação (JSON bruto)"):
            st.json(meta["amostra"])

    st.subheader("Coleta de histórico (GitHub)")
    if coleta is None or coleta.empty:
        st.write("Nenhum histórico encontrado em:")
        st.code(HISTORICO_URL)
    else:
        st.write(f"{len(coleta)} registros de {coleta['codigo'].nunique()} estações, "
                 f"de {coleta['quando'].min():%d/%m %H:%M} até {coleta['quando'].max():%d/%m %H:%M}.")


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #
def main():
    st.set_page_config(page_title="Chuva e Rios - RS", page_icon="🌧️", layout="wide")
    st.title("🌊 Rios e chuva no RS")
    st.caption("Rede Hidrometeorológica da Defesa Civil RS · dados em quase tempo real")

    try:
        with st.spinner("Buscando dados da Defesa Civil RS..."):
            df, meta = carregar_estacoes()
    except Exception as exc:
        st.error("Não consegui carregar os dados da API.")
        aba_diagnostico(None, str(exc))
        st.stop()

    coleta = carregar_coleta()
    filtrado = filtros_laterais(df)

    ult = df["ultima_leitura"].max()
    st.caption(
        f"{len(filtrado)} de {len(df)} estações exibidas"
        + (f" · leitura mais recente: {ult:%d/%m/%Y %H:%M}" if pd.notna(ult) else "")
    )
    if filtrado.empty:
        st.warning("Nenhuma estação com esses filtros.")
        st.stop()

    t_rios, t_chuva, t_mapa, t_hist, t_diag = st.tabs(
        ["🌊 Rios", "🌧️ Chuva", "🗺️ Mapa", "📈 Histórico", "🛠️ Diagnóstico"]
    )
    with t_rios:
        aba_rios(filtrado, coleta)
    with t_chuva:
        aba_chuva(filtrado)
    with t_mapa:
        aba_mapa(filtrado)
    with t_hist:
        aba_historico(filtrado)
    with t_diag:
        aba_diagnostico(meta, coleta=coleta)


if __name__ == "__main__":
    main()