-- =====================================================================
-- 03_analises.sql  |  Consultas de análise (perguntas de negócio)
-- =====================================================================


-- Q1. Como está distribuída a carteira por status?
SELECT status_obra,
       COUNT(*)                                                         AS qtd_obras,
       ROUND(SUM(valor_contrato) / 1000000.0, 1)                        AS valor_contratado_mi,
       ROUND(100.0 * SUM(valor_contrato) / SUM(SUM(valor_contrato)) OVER (), 1) AS pct_da_carteira
FROM dim_obra
GROUP BY status_obra
ORDER BY valor_contratado_mi DESC;


-- Q2. Qual tipo de obra concentra mais valor? (ranking)
SELECT tipo_obra,
       COUNT(*)                                          AS qtd_obras,
       ROUND(SUM(valor_contrato) / 1000000.0, 1)         AS valor_contratado_mi,
       ROUND(AVG(valor_contrato) / 1000000.0, 1)         AS ticket_medio_mi,
       RANK() OVER (ORDER BY SUM(valor_contrato) DESC)   AS ranking
FROM dim_obra
GROUP BY tipo_obra
ORDER BY ranking;


-- Q3. Quais são as 10 obras mais atrasadas fisicamente (em execução)?
SELECT RANK() OVER (ORDER BY desvio_fisico)       AS ranking_atraso,
       nome_obra,
       tipo_obra,
       status_obra,
       ROUND(avanco_previsto_acum  * 100, 1)       AS previsto_pct,
       ROUND(avanco_realizado_acum * 100, 1)       AS realizado_pct,
       ROUND(desvio_fisico * 100, 1)               AS desvio_pontos_pct,
       spi
FROM vw_obra_situacao_atual
WHERE status_obra <> 'Concluída'
ORDER BY ranking_atraso
LIMIT 10;


-- Q4. Evolução mensal do faturamento: variação mensal (LAG) e média móvel de 3 meses
WITH mensal AS (
    SELECT data_ref, SUM(valor_medido) AS valor_medido
    FROM fato_medicao
    GROUP BY data_ref
)
SELECT data_ref,
       ROUND(valor_medido / 1000000.0, 2)                                     AS medido_mi,
       ROUND((valor_medido - LAG(valor_medido) OVER w)
             / NULLIF(LAG(valor_medido) OVER w, 0) * 100, 1)                  AS variacao_mensal_pct,
       ROUND(AVG(valor_medido) OVER (ORDER BY data_ref
                                     ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
             / 1000000.0, 2)                                                  AS media_movel_3m_mi,
       ROUND(SUM(valor_medido) OVER (ORDER BY data_ref) / 1000000.0, 1)       AS acumulado_mi
FROM mensal
WINDOW w AS (ORDER BY data_ref)
ORDER BY data_ref;


-- Q5. Onde gastamos mais do que o esperado PARA O AVANÇO executado?
-- (Comparar só "orçado x realizado" engana: obra atrasada gasta menos no período.
--  O correto é comparar o custo com o avanço realizado.)
WITH avanco_mensal AS (
    SELECT id_obra,
           data_ref,
           avanco_realizado_acum
             - COALESCE(LAG(avanco_realizado_acum) OVER (PARTITION BY id_obra ORDER BY data_ref), 0)
             AS avanco_mes
    FROM fato_medicao
),
comparativo AS (
    SELECT o.tipo_obra,
           cat.nome_categoria,
           SUM(fc.valor_realizado)                                            AS realizado,
           SUM(a.avanco_mes * o.orcamento_custo * cat.participacao_orcada)    AS esperado_para_o_avanco
    FROM fato_custo fc
    JOIN dim_categoria_custo cat ON cat.id_categoria = fc.id_categoria
    JOIN dim_obra o              ON o.id_obra = fc.id_obra
    JOIN avanco_mensal a         ON a.id_obra = fc.id_obra AND a.data_ref = fc.data_ref
    WHERE cat.base_apropriacao = 'Avanço físico'
    GROUP BY o.tipo_obra, cat.nome_categoria
)
SELECT tipo_obra,
       nome_categoria,
       ROUND(realizado / 1000000.0, 2)                                        AS realizado_mi,
       ROUND(esperado_para_o_avanco / 1000000.0, 2)                           AS esperado_mi,
       ROUND((realizado / NULLIF(esperado_para_o_avanco, 0) - 1) * 100, 1)    AS estouro_pct
FROM comparativo
ORDER BY estouro_pct DESC;


-- Q6. Obras em risco: classificação de saúde e quartil de CPI (NTILE)
WITH base AS (
    SELECT nome_obra,
           tipo_obra,
           status_obra,
           spi,
           cpi,
           classificacao_saude,
           NTILE(4) OVER (ORDER BY cpi) AS quartil_cpi      -- 1 = pior quartil de custo
    FROM vw_obra_situacao_atual
    WHERE status_obra <> 'Concluída'
)
SELECT *
FROM base
WHERE quartil_cpi = 1 OR classificacao_saude = 'Crítica'
ORDER BY cpi;


-- Q7. Segurança: taxa de frequência por obra
--     Taxa de frequência = acidentes com afastamento x 1.000.000 / horas trabalhadas
WITH horas AS (
    SELECT id_obra, SUM(horas_trabalhadas) AS horas
    FROM fato_medicao
    GROUP BY id_obra
),
acidentes AS (
    SELECT id_obra,
           COUNT(*) FILTER (WHERE tipo_ocorrencia = 'Acidente com afastamento') AS com_afastamento,
           COALESCE(SUM(dias_afastamento), 0)                                   AS dias_perdidos
    FROM fato_seguranca
    GROUP BY id_obra
)
SELECT RANK() OVER (ORDER BY COALESCE(a.com_afastamento, 0) * 1000000.0
                             / NULLIF(h.horas, 0) DESC)                  AS ranking,
       o.nome_obra,
       o.tipo_obra,
       ROUND(h.horas, 0)                                                 AS horas_trabalhadas,
       COALESCE(a.com_afastamento, 0)                                    AS acidentes_com_afastamento,
       COALESCE(a.dias_perdidos, 0)                                      AS dias_perdidos,
       ROUND(COALESCE(a.com_afastamento, 0) * 1000000.0 / NULLIF(h.horas, 0), 2) AS taxa_frequencia
FROM dim_obra o
JOIN horas h           ON h.id_obra = o.id_obra
LEFT JOIN acidentes a  ON a.id_obra = o.id_obra
ORDER BY ranking;


-- Q8. Alerta precoce: avanço do mês abaixo de 80% do previsto por 3 meses CONSECUTIVOS
WITH mensal AS (
    SELECT id_obra,
           data_ref,
           avanco_realizado_acum - COALESCE(LAG(avanco_realizado_acum) OVER w, 0) AS real_mes,
           avanco_previsto_acum  - COALESCE(LAG(avanco_previsto_acum)  OVER w, 0) AS previsto_mes
    FROM fato_medicao
    WINDOW w AS (PARTITION BY id_obra ORDER BY data_ref)
),
sinalizado AS (
    SELECT *,
           CASE WHEN real_mes < 0.8 * previsto_mes THEN 1 ELSE 0 END AS abaixo
    FROM mensal
),
janela AS (
    SELECT *,
           SUM(abaixo) OVER (PARTITION BY id_obra ORDER BY data_ref
                             ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS abaixo_ultimos_3m
    FROM sinalizado
)
SELECT o.nome_obra,
       o.status_obra,
       MIN(j.data_ref) AS primeiro_alerta,
       COUNT(*)        AS meses_em_alerta
FROM janela j
JOIN dim_obra o ON o.id_obra = j.id_obra
WHERE j.abaixo_ultimos_3m = 3
GROUP BY o.nome_obra, o.status_obra
ORDER BY meses_em_alerta DESC, o.nome_obra;


-- Q9. Para onde vai o dinheiro? Participação de cada categoria no custo total
SELECT cat.nome_categoria,
       ROUND(SUM(fc.valor_realizado) / 1000000.0, 1)                                   AS realizado_mi,
       ROUND(100.0 * SUM(fc.valor_realizado) / SUM(SUM(fc.valor_realizado)) OVER (), 1) AS pct_do_total
FROM fato_custo fc
JOIN dim_categoria_custo cat ON cat.id_categoria = fc.id_categoria
GROUP BY cat.nome_categoria
ORDER BY realizado_mi DESC;