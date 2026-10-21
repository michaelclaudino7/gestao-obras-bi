"""
carregar_postgres.py
--------------------
Lê os CSVs da pasta /dados, faz checagens básicas de qualidade e carrega
as tabelas no PostgreSQL (que roda no Docker).

Pré-requisitos:
    1) docker compose up -d       (banco no ar)
    2) tabelas criadas (sql/01_schema.sql)
    3) python python/gerar_dados.py

Uso:
    python python/carregar_postgres.py
"""
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "dados"

# Lê as credenciais do arquivo .env (as mesmas usadas pelo docker-compose)
load_dotenv(RAIZ / ".env")

USUARIO = os.getenv("POSTGRES_USER", "analista")
SENHA = os.getenv("POSTGRES_PASSWORD", "obras123")
BANCO = os.getenv("POSTGRES_DB", "obras_bi")
HOST = os.getenv("POSTGRES_HOST", "localhost")
PORTA = os.getenv("POSTGRES_PORT", "5432")

# Ordem importa: dimensões primeiro (por causa das chaves estrangeiras).
# Segundo item: colunas de data que precisam ser convertidas ao ler o CSV.
ORDEM_CARGA = [
    ("dim_tempo", ["data"]),
    ("dim_categoria_custo", []),
    ("dim_obra", ["data_inicio", "data_fim_prevista"]),
    ("fato_medicao", ["data_ref"]),
    ("fato_custo", ["data_ref"]),
    ("fato_seguranca", ["data_ocorrencia"]),
]


def checar_qualidade(tabelas: dict) -> None:
    """Validações simples antes de carregar. Interrompe o script se algo estiver errado."""
    erros = []

    # 1) nenhuma tabela pode ter valores nulos
    for nome, df in tabelas.items():
        if df.isnull().any().any():
            colunas = df.columns[df.isnull().any()].tolist()
            erros.append(f"{nome}: valores nulos em {colunas}")

    med = tabelas["fato_medicao"]

    # 2) avanço entre 0 e 1
    if not med["avanco_realizado_acum"].between(0, 1).all():
        erros.append("fato_medicao: avanço realizado fora do intervalo 0–1")

    # 3) uma medição por obra e mês
    if med.duplicated(["id_obra", "data_ref"]).any():
        erros.append("fato_medicao: medição duplicada para a mesma obra e mês")

    # 4) avanço acumulado nunca pode diminuir
    queda = (med.sort_values(["id_obra", "data_ref"])
                .groupby("id_obra")["avanco_realizado_acum"]
                .diff().lt(0).any())
    if queda:
        erros.append("fato_medicao: avanço acumulado diminuiu em algum mês")

    # 5) fatos só podem referenciar obras que existem
    obras = set(tabelas["dim_obra"]["id_obra"])
    for fato in ("fato_medicao", "fato_custo", "fato_seguranca"):
        if not set(tabelas[fato]["id_obra"]).issubset(obras):
            erros.append(f"{fato}: referência a obra inexistente")

    if erros:
        print("Falha na checagem de qualidade:")
        for e in erros:
            print(f"  - {e}")
        sys.exit(1)
    print("Checagem de qualidade: OK")


def main() -> None:
    # --- Leitura dos CSVs ---
    tabelas = {}
    for nome, colunas_data in ORDEM_CARGA:
        caminho = PASTA_DADOS / f"{nome}.csv"
        if not caminho.exists():
            sys.exit(f"Arquivo não encontrado: {caminho}\n"
                     "Rode antes: python python/gerar_dados.py")
        df = pd.read_csv(caminho, parse_dates=colunas_data)
        for c in colunas_data:
            df[c] = df[c].dt.date
        tabelas[nome] = df

    # --- Validação ---
    checar_qualidade(tabelas)

    # --- Carga ---
    url = f"postgresql+psycopg://{USUARIO}:{SENHA}@{HOST}:{PORTA}/{BANCO}"
    engine = create_engine(url)

    # engine.begin() abre uma transação: ou carrega tudo, ou não carrega nada
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE fato_seguranca, fato_custo, fato_medicao, "
            "dim_obra, dim_categoria_custo, dim_tempo"))
        for nome, _ in ORDEM_CARGA:
            tabelas[nome].to_sql(nome, conn, if_exists="append", index=False,
                                 method="multi", chunksize=1000)
            print(f"Carregada {nome:<22} {len(tabelas[nome]):>7} linhas")

    # --- Conferência ---
    with engine.connect() as conn:
        print("\nConferência no banco:")
        for nome, _ in ORDEM_CARGA:
            qtd = conn.execute(text(f"SELECT COUNT(*) FROM {nome}")).scalar()
            print(f"  {nome:<22} {qtd:>7}")

    print("\nPronto! Dados carregados em "
          f"{HOST}:{PORTA}, banco '{BANCO}'.")


if __name__ == "__main__":
    main()