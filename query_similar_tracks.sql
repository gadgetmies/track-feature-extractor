SELECT track_id, track_path
FROM track
         NATURAL JOIN track_embedding
ORDER BY track_embedding_vector <->
         (SELECT track_embedding_vector FROM track_embedding WHERE track_id = 683)
LIMIT 10;