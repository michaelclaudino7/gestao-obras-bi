"""
gerar_dados.py
--------------
Gera uma base FICTÍCIA de gestão de obras (saneamento, habitação, escolas e
transportes) e salva em CSV na pasta /dados.

Os dados são simulados e reprodutíveis (semente fixa). Nada aqui representa
contratos, valores ou indicadores reais de nenhuma empresa.

Uso:
    python python/gerar_dados.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
DATA_CORTE = pd.Timestamp("2026-09-01")      # último mês medido (1º dia do mês)
PASTA_SAIDA = Path(__file__).resolve().parent.parent / "dados"

rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------------------
# 1. Catálogo de obras (nome, tipo, subtipo, município, UF)
# ---------------------------------------------------------------------------
CATALOGO = [
    ("Adutora de Água Tratada", "Saneamento", "Adutora", "Campinas", "SP"),
    ("Reservatório Elevado", "Saneamento", "Reservatório", "Sorocaba", "SP"),
    ("Estação de Tratamento de Esgoto", "Saneamento", "ETE", "Ribeirão Preto", "SP"),
    ("Estação de Tratamento de Água", "Saneamento", "ETA", "Londrina", "PR"),
    ("Adutora de Água Bruta", "Saneamento", "Adutora", "Uberlândia", "MG"),
    ("Ampliação de Rede Coletora de Esgoto", "Saneamento", "Rede de esgoto", "Santos", "SP"),
    ("Reservatório Enterrado", "Saneamento", "Reservatório", "Maringá", "PR"),
    ("Estação de Tratamento de Esgoto", "Saneamento", "ETE", "Juiz de Fora", "MG"),
    ("Conjunto Habitacional", "Habitação popular", "Conjunto", "Guarulhos", "SP"),
    ("Conjunto Habitacional", "Habitação popular", "Conjunto", "Osasco", "SP"),
    ("Residencial Popular", "Habitação popular", "Residencial", "São José dos Campos", "SP"),
    ("Conjunto Habitacional", "Habitação popular", "Conjunto", "Contagem", "MG"),
    ("Urbanização de Comunidade", "Habitação popular", "Urbanização", "Diadema", "SP"),
    ("Residencial Popular", "Habitação popular", "Residencial", "Curitiba", "PR"),
    ("Escola Municipal", "Construção escolar", "Ensino fundamental", "Mogi das Cruzes", "SP"),
    ("Escola Municipal", "Construção escolar", "Ensino fundamental", "Piracicaba", "SP"),
    ("Creche Municipal", "Construção escolar", "Creche", "Bauru", "SP"),
    ("Escola Técnica", "Construção escolar", "Ensino técnico", "Betim", "MG"),
    ("Creche Municipal", "Construção escolar", "Creche", "Ponta Grossa", "PR"),
    ("Corredor de Ônibus", "Transportes", "Corredor", "São Bernardo do Campo", "SP"),
    ("Viaduto", "Transportes", "Viaduto", "Jundiaí", "SP"),
    ("Terminal de Ônibus", "Transportes", "Terminal", "Cascavel", "PR"),
    ("Duplicação de Avenida", "Transportes", "Via urbana", "Campo Grande", "MS"),
    ("Ponte Urbana", "Transportes", "Ponte", "Taubaté", "SP"),
]

# (faixa de valor do contrato em R$ milhões), (faixa de duração em meses)
PARAMETROS_TIPO = {
    "Saneamento": ((18, 120), (14, 30)),
    "Habitação popular": ((25, 90), (16, 32)),
    "Construção escolar": ((6, 28), (10, 20)),
    "Transportes": ((35, 150), (18, 36)),
}

# Fator de risco de segurança por tipo (escavações e vias costumam ter mais risco)
RISCO_SEGURANCA = {
    "Saneamento": 1.2,
    "Habitação popular": 1.0,
    "Construção escolar": 0.8,
    "Transportes": 1.3,
}

# (id, nome, base de apropriação, participação no orçamento de custo)
CATEGORIAS = [
    (1, "Mão de obra", "Avanço físico", 0.30),
    (2, "Materiais", "Avanço físico", 0.38),
    (3, "Equipamentos", "Avanço físico", 0.12),
    (4, "Subempreiteiros", "Avanço físico", 0.15),
    (5, "Administração e canteiro", "Prazo", 0.05),
]
CUSTO_HORA_MO = 45.0  # R$ por hora-homem (usado para estimar horas trabalhadas)

MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
            "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def curva_s(x):
    """Curva S normalizada: 0 em x=0 e 1 em x=1 (distribuição típica de avanço de obra)."""
    s = lambda v: 1.0 / (1.0 + np.exp(-9.0 * (np.asarray(v) - 0.5)))
    return (s(x) - s(0.0)) / (s(1.0) - s(0.0))


# ---------------------------------------------------------------------------
# 2. Dimensões
# ---------------------------------------------------------------------------
def gerar_dim_tempo():
    datas = pd.date_range("2023-01-01", "2026-12-31", freq="D")
    return pd.DataFrame({
        "data": datas.date,
        "ano": datas.year,
        "trimestre": datas.quarter,
        "mes": datas.month,
        "nome_mes": [MESES_PT[m - 1] for m in datas.month],
        "ano_mes": datas.strftime("%Y-%m"),
    })


def gerar_dim_categoria():
    return pd.DataFrame(CATEGORIAS, columns=[
        "id_categoria", "nome_categoria", "base_apropriacao", "participacao_orcada"])


def sortear_obras():
    """Define cadastro, prazo, valor e comportamento (ritmo) de cada obra."""
    obras = []
    inicios_possiveis = pd.date_range("2023-01-01", "2026-03-01", freq="MS")
    for i, (nome, tipo, subtipo, municipio, uf) in enumerate(CATALOGO, start=1):
        (v_min, v_max), (d_min, d_max) = PARAMETROS_TIPO[tipo]
        duracao = int(rng.integers(d_min, d_max + 1))
        inicio = inicios_possiveis[int(rng.integers(0, len(inicios_possiveis)))]
        valor = round(float(rng.uniform(v_min, v_max)) * 1_000_000, 2)
        margem = float(rng.uniform(0.08, 0.18))
        cliente = (f"Serviço de Água e Esgoto de {municipio}" if tipo == "Saneamento"
                   else f"Prefeitura de {municipio}")
        obras.append({
            "id_obra": i,
            "nome_obra": f"{nome} – {municipio}",
            "tipo_obra": tipo,
            "subtipo": subtipo,
            "municipio": municipio,
            "uf": uf,
            "cliente": cliente,
            "data_inicio": inicio,
            "duracao_meses": duracao,
            "data_fim_prevista": inicio + pd.DateOffset(months=duracao),
            "valor_contrato": valor,
            "orcamento_custo": round(valor * (1 - margem), 2),
            # ritmo da obra: <1 = ritmo abaixo do planejado
            "ritmo": float(np.clip(rng.normal(0.93, 0.09), 0.72, 1.0)),
            # pressão de custo da obra (>1 = custo acima do esperado para o avanço)
            "pressao_custo": float(rng.normal(1.03, 0.05)),
            "mes_parada": None,
        })

    # Duas obras em andamento ficam paralisadas no meio da execução
    candidatas = [o for o in obras
                  if o["data_inicio"] <= pd.Timestamp("2025-06-01")
                  and o["data_fim_prevista"] > DATA_CORTE + pd.DateOffset(months=3)]
    for idx in rng.choice(len(candidatas), size=min(2, len(candidatas)), replace=False):
        o = candidatas[int(idx)]
        meses_ate_corte = (DATA_CORTE.year - o["data_inicio"].year) * 12 + \
                          (DATA_CORTE.month - o["data_inicio"].month) + 1
        o["mes_parada"] = int(meses_ate_corte * rng.uniform(0.5, 0.75))
    return obras


# ---------------------------------------------------------------------------
# 3. Fatos (simulação mês a mês de cada obra)
# ---------------------------------------------------------------------------
def simular(obras):
    medicoes, custos, ocorrencias = [], [], []
    id_ocorrencia = 1

    for o in obras:
        T = o["duracao_meses"]
        meses = pd.date_range(o["data_inicio"], DATA_CORTE, freq="MS")
        # planejado acumulado e incremental por mês (t = 1..T)
        prev_acum = np.concatenate([[0.0], curva_s(np.arange(1, T + 1) / T)])
        prev_inc = np.diff(prev_acum, prepend=0.0)[1:]  # índice t-1 -> mês t
        prev_inc = np.concatenate([[0.0], prev_inc])    # índice t -> mês t

        cum_real = 0.0
        concluida = False
        paralisada = False
        fatores_cat = {cid: float(rng.lognormal(np.log(o["pressao_custo"]), 0.04))
                       for cid, *_ in CATEGORIAS}

        for t, data_ref in enumerate(meses, start=1):
            plan_inc = prev_inc[t] if t <= T else 0.0
            plan_acum = prev_acum[min(t, T)]

            # avanço real do mês
            if o["mes_parada"] is not None and t > o["mes_parada"]:
                inc = 0.0
                paralisada = True
            else:
                base = plan_inc if t <= T else 0.8 / T      # depois do prazo, ritmo residual
                inc = base * o["ritmo"] * max(0.0, rng.normal(1.0, 0.18))
            inc = min(inc, 1.0 - cum_real)
            if 1.0 - cum_real - inc < 0.004:                 # evita sobra de 0,1%
                inc = 1.0 - cum_real
            cum_real += inc

            # custos por categoria
            horas = 0.0
            for cid, nome_cat, base_ap, share in CATEGORIAS:
                if base_ap == "Avanço físico":
                    orcado = plan_inc * o["orcamento_custo"] * share
                    realizado = (inc * o["orcamento_custo"] * share
                                 * fatores_cat[cid] * max(0.0, rng.normal(1.0, 0.05)))
                else:  # custo por prazo (administração e canteiro)
                    mensal = o["orcamento_custo"] * share / T
                    orcado = mensal if t <= T else 0.0
                    realizado = mensal * max(0.0, rng.normal(1.0, 0.04))
                if cid == 1:
                    horas = realizado / CUSTO_HORA_MO
                custos.append({
                    "id_obra": o["id_obra"], "data_ref": data_ref.date(),
                    "id_categoria": cid,
                    "valor_orcado": round(orcado, 2),
                    "valor_realizado": round(realizado, 2),
                })

            medicoes.append({
                "id_obra": o["id_obra"], "data_ref": data_ref.date(),
                "avanco_previsto_acum": round(float(plan_acum), 4),
                "avanco_realizado_acum": round(min(cum_real, 1.0), 4),
                "valor_medido": round(inc * o["valor_contrato"], 2),
                "horas_trabalhadas": round(horas, 1),
            })

            # ocorrências de segurança (taxas por milhão de horas trabalhadas)
            risco = RISCO_SEGURANCA[o["tipo_obra"]] * o.setdefault(
                "risco_obra", float(rng.lognormal(0, 0.35)))
            taxas = [
                ("Acidente com afastamento", 8e-6),
                ("Acidente sem afastamento", 15e-6),
                ("Quase acidente", 40e-6),
                ("Desvio de EPI/normas", 60e-6),
            ]
            for tipo_oc, taxa in taxas:
                for _ in range(int(rng.poisson(horas * taxa * risco))):
                    if tipo_oc == "Acidente com afastamento":
                        grave = rng.random() < 0.2
                        gravidade = "Grave" if grave else "Moderada"
                        dias = int(rng.integers(15, 91) if grave else rng.integers(3, 15))
                    elif tipo_oc == "Acidente sem afastamento":
                        gravidade, dias = "Leve", 0
                    else:
                        gravidade, dias = "Leve", 0
                    dia = int(rng.integers(1, 29))
                    ocorrencias.append({
                        "id_ocorrencia": id_ocorrencia,
                        "id_obra": o["id_obra"],
                        "data_ocorrencia": data_ref.replace(day=dia).date(),
                        "tipo_ocorrencia": tipo_oc,
                        "gravidade": gravidade,
                        "dias_afastamento": dias,
                    })
                    id_ocorrencia += 1

            if cum_real >= 0.9999:
                concluida = True
                break

        o["status_obra"] = ("Concluída" if concluida
                            else "Paralisada" if paralisada else "Em andamento")

    return (pd.DataFrame(medicoes), pd.DataFrame(custos),
            pd.DataFrame(ocorrencias))


def main():
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)

    obras = sortear_obras()
    fato_medicao, fato_custo, fato_seguranca = simular(obras)

    dim_obra = pd.DataFrame(obras)[[
        "id_obra", "nome_obra", "tipo_obra", "subtipo", "municipio", "uf", "cliente",
        "data_inicio", "data_fim_prevista", "valor_contrato", "orcamento_custo", "status_obra"]]
    dim_obra["data_inicio"] = pd.to_datetime(dim_obra["data_inicio"]).dt.date
    dim_obra["data_fim_prevista"] = pd.to_datetime(dim_obra["data_fim_prevista"]).dt.date

    tabelas = {
        "dim_tempo": gerar_dim_tempo(),
        "dim_obra": dim_obra,
        "dim_categoria_custo": gerar_dim_categoria(),
        "fato_medicao": fato_medicao,
        "fato_custo": fato_custo,
        "fato_seguranca": fato_seguranca,
    }
    for nome, df in tabelas.items():
        df.to_csv(PASTA_SAIDA / f"{nome}.csv", index=False, encoding="utf-8")
        print(f"{nome:<22} {len(df):>7,} linhas".replace(",", "."))

    print("\nStatus das obras:")
    print(dim_obra["status_obra"].value_counts().to_string())
    print(f"\nArquivos salvos em: {PASTA_SAIDA}")


if __name__ == "__main__":
    main()