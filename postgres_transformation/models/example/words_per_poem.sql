WITH poem_data AS (
    SELECT 
        p.*,
        w.*
    FROM 
        {{ ref('poems_poem') }} p
    JOIN 
        {{ ref('poems_poem_words') }} pw 
        ON pw.poem_id = p.poem_id
    JOIN 
        {{ ref('poems_word') }} w 
        ON w.word_id = pw.word_id
)

SELECT * FROM poem_data