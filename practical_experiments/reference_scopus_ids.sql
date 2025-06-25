WITH reference_scopus_ids AS (
  SELECT
    sja.scopus_id as source_scopus_id,
    sjson.reference_scopus_id
    --sjson.reference_scopus_id_type
  FROM
    scopus_json_abstract_authored sja,
    JSON_TABLE(sja.json_document, '$."abstracts-retrieval-response".item.bibrecord.tail'
      COLUMNS (
        NESTED PATH '$.bibliography.reference[*]' COLUMNS (
          NESTED PATH '$."ref-info"."refd-itemidlist".itemid[*]' COLUMNS (
            reference_scopus_id_type PATH '$."@idtype"',
            reference_scopus_id PATH '$."$"'
          ),
          publication_year PATH '$."ref-info"."ref-publicationyear"."@first"'
        )
      )) sjson
  WHERE sjson.reference_scopus_id_type = 'SGR'
    AND TO_DATE(sjson.publication_year, 'YYYY') > ADD_MONTHS(SYSDATE, - (12 * 3))
  --FETCH FIRST 100 ROWS ONLY
)
-- SELECT COUNT(*) FROM reference_scopus_ids;
-- Raw count on rows is 1,076,182
-- SELECT COUNT(*) FROM (SELECT DISTINCT source_scopus_id, reference_scopus_id FROM reference_scopus_ids);
-- Distinct count is 1,069,258
-- SELECT DISTINCT source_scopus_id, reference_scopus_id
-- FROM unique_reference_scopus_ids
-- ORDER BY source_scopus_id
-- Finally, how many distinct reference scopus ids
SELECT COUNT(*) FROM (SELECT DISTINCT reference_scopus_id FROM reference_scopus_ids)
-- Number of unique reference scopus_ids is 817,236
;
