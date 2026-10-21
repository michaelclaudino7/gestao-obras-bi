-- =====================================================================
-- 02_views.sql  |  Camada semântica para o Power BI
-- Indicadores de Earned Value:
--   PV  = avanço previsto  x orçamento de custo
--   EV  = avanço realizado x orçamento de custo
--   AC  = custo realizado acumulado
--   SPI = EV / PV  (< 1 obra atrasada)      CPI = EV / AC  (< 1 custo acima do esperado)
-- =====================================================================

-- Evolução mensal de cada obra, com acumulados e indicadores
CREATE OR REPLACE VIEW vw_earned_value AS
WITH custo_mes AS (
    SELECT id_obra,
           data_ref,
           SUM(valor_orcado)    AS orcado_mes,
           SUM(valor_realizado) AS realizado_mes
    FROM fato_custo
    GROUP BY id_obra, data_ref
),
base AS (
    SELECT m.id_obra,
           m.data_ref,
           m.avanco_previsto_acum,
           m.avanco_realizado_acum,
           m.valor_medido,
           m.horas_trabalhadas,
           COALESCE(c.orcado_mes, 0)    AS orcado_mes,
           COALESCE(c.realizado_mes, 0) AS realizado_mes
    FROM fato_medicao m
    LEFT JOIN custo_mes c ON c.id_obra = m.id_obra AND c.data_ref = m.data_ref
)
SELECT b.id_obra,
       b.data_ref,
       b.avanco_previsto_acum,
       b.avanco_realizado_acum,
       b.avanco_realizado_acum - b.avanco_previsto_acum                AS desvio_fisico,
       b.valor_medido,
       b.horas_trabalhadas,
       b.orcado_mes,
       b.realizado_mes,
       SUM(b.orcado_mes)    OVER w                                      AS orcado_acum,
       SUM(b.realizado_mes) OVER w                                      AS realizado_acum,
       b.avanco_previsto_acum  * o.orcamento_custo                      AS pv,
       b.avanco_realizado_acum * o.orcamento_custo                      AS ev,
       ROUND(b.avanco_realizado_acum / NULLIF(b.avanco_previsto_acum, 0), 3) AS spi,
       ROUND((b.avanco_realizado_acum * o.orcamento_custo)
             / NULLIF(SUM(b.realizado_mes) OVER w, 0), 3)               AS cpi
FROM base b
JOIN dim_obra o ON o.id_obra = b.id_obra
WINDOW w AS (PARTITION BY b.id_obra ORDER BY b.data_ref);


-- Retrato atual de cada obra (última medição) com classificação de saúde
CREATE OR REPLACE VIEW vw_obra_situacao_atual AS
SELECT DISTINCT ON (ev.id_obra)
       o.id_obra,
       o.nome_obra,
       o.tipo_obra,
       o.municipio,
       o.uf,
       o.cliente,
       o.status_obra,
       o.data_inicio,
       o.data_fim_prevista,
       o.valor_contrato,
       o.orcamento_custo,
       ev.data_ref                                            AS ultima_medicao,
       ev.avanco_previsto_acum,
       ev.avanco_realizado_acum,
       ev.desvio_fisico,
       ev.orcado_acum,
       ev.realizado_acum,
       ev.spi,
       ev.cpi,
       GREATEST(0, ev.data_ref - o.data_fim_prevista)         AS dias_atraso,
       CASE
           WHEN ev.spi < 0.85 OR ev.cpi < 0.90 THEN 'Crítica'
           WHEN ev.spi < 0.95 OR ev.cpi < 0.95 THEN 'Atenção'
           ELSE 'Saudável'
       END                                                    AS classificacao_saude
FROM vw_earned_value ev
JOIN dim_obra o ON o.id_obra = ev.id_obra
ORDER BY ev.id_obra, ev.data_ref DESC;


-- Ocorrências de segurança agregadas por obra e mês
CREATE OR REPLACE VIEW vw_seguranca_mensal AS
SELECT s.id_obra,
       DATE_TRUNC('month', s.data_ocorrencia)::DATE                           AS data_ref,
       COUNT(*)                                                               AS total_ocorrencias,
       COUNT(*) FILTER (WHERE s.tipo_ocorrencia = 'Acidente com afastamento') AS acidentes_com_afastamento,
       COALESCE(SUM(s.dias_afastamento), 0)                                   AS dias_perdidos
FROM fato_seguranca s
GROUP BY s.id_obra, DATE_TRUNC('month', s.data_ocorrencia)::DATE;