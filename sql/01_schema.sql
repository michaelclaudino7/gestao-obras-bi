-- =====================================================================
-- 01_schema.sql  |  Modelo dimensional (estrela) para gestão de obras
-- Avanços físicos são guardados como proporção (0 a 1).
-- =====================================================================

-- ---------- DIMENSÕES ----------

CREATE TABLE dim_tempo (
    data        DATE        PRIMARY KEY,
    ano         SMALLINT    NOT NULL,
    trimestre   SMALLINT    NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    mes         SMALLINT    NOT NULL CHECK (mes BETWEEN 1 AND 12),
    nome_mes    VARCHAR(10) NOT NULL,
    ano_mes     CHAR(7)     NOT NULL
);

CREATE TABLE dim_obra (
    id_obra            INT           PRIMARY KEY,
    nome_obra          VARCHAR(120)  NOT NULL UNIQUE,
    tipo_obra          VARCHAR(30)   NOT NULL
                       CHECK (tipo_obra IN ('Saneamento', 'Habitação popular',
                                            'Construção escolar', 'Transportes')),
    subtipo            VARCHAR(40),
    municipio          VARCHAR(60)   NOT NULL,
    uf                 CHAR(2)       NOT NULL,
    cliente            VARCHAR(80)   NOT NULL,
    data_inicio        DATE          NOT NULL,
    data_fim_prevista  DATE          NOT NULL,
    valor_contrato     NUMERIC(14,2) NOT NULL CHECK (valor_contrato > 0),
    orcamento_custo    NUMERIC(14,2) NOT NULL CHECK (orcamento_custo > 0),
    status_obra        VARCHAR(20)   NOT NULL
                       CHECK (status_obra IN ('Em andamento', 'Concluída', 'Paralisada')),
    CHECK (data_fim_prevista > data_inicio)
);

CREATE TABLE dim_categoria_custo (
    id_categoria        INT          PRIMARY KEY,
    nome_categoria      VARCHAR(40)  NOT NULL UNIQUE,
    base_apropriacao    VARCHAR(20)  NOT NULL CHECK (base_apropriacao IN ('Avanço físico', 'Prazo')),
    participacao_orcada NUMERIC(5,4) NOT NULL CHECK (participacao_orcada BETWEEN 0 AND 1)
);

-- ---------- FATOS ----------

CREATE TABLE fato_medicao (
    id_obra                INT           NOT NULL REFERENCES dim_obra (id_obra),
    data_ref               DATE          NOT NULL REFERENCES dim_tempo (data),
    avanco_previsto_acum   NUMERIC(6,4)  NOT NULL CHECK (avanco_previsto_acum BETWEEN 0 AND 1),
    avanco_realizado_acum  NUMERIC(6,4)  NOT NULL CHECK (avanco_realizado_acum BETWEEN 0 AND 1),
    valor_medido           NUMERIC(14,2) NOT NULL CHECK (valor_medido >= 0),
    horas_trabalhadas      NUMERIC(12,1) NOT NULL CHECK (horas_trabalhadas >= 0),
    PRIMARY KEY (id_obra, data_ref)
);

CREATE TABLE fato_custo (
    id_obra         INT           NOT NULL REFERENCES dim_obra (id_obra),
    data_ref        DATE          NOT NULL REFERENCES dim_tempo (data),
    id_categoria    INT           NOT NULL REFERENCES dim_categoria_custo (id_categoria),
    valor_orcado    NUMERIC(14,2) NOT NULL CHECK (valor_orcado >= 0),
    valor_realizado NUMERIC(14,2) NOT NULL CHECK (valor_realizado >= 0),
    PRIMARY KEY (id_obra, data_ref, id_categoria)
);

CREATE TABLE fato_seguranca (
    id_ocorrencia    INT          PRIMARY KEY,
    id_obra          INT          NOT NULL REFERENCES dim_obra (id_obra),
    data_ocorrencia  DATE         NOT NULL REFERENCES dim_tempo (data),
    tipo_ocorrencia  VARCHAR(40)  NOT NULL
                     CHECK (tipo_ocorrencia IN ('Acidente com afastamento', 'Acidente sem afastamento',
                                                'Quase acidente', 'Desvio de EPI/normas')),
    gravidade        VARCHAR(10)  NOT NULL CHECK (gravidade IN ('Leve', 'Moderada', 'Grave')),
    dias_afastamento INT          NOT NULL DEFAULT 0 CHECK (dias_afastamento >= 0)
);

-- Índices nas chaves estrangeiras
CREATE INDEX idx_medicao_data   ON fato_medicao (data_ref);
CREATE INDEX idx_custo_obra     ON fato_custo (id_obra, data_ref);
CREATE INDEX idx_custo_cat      ON fato_custo (id_categoria);
CREATE INDEX idx_seg_obra_data  ON fato_seguranca (id_obra, data_ocorrencia);