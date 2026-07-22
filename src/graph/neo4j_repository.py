from __future__ import annotations


class Neo4jGraphRepository:
    def __init__(self, uri: str, user: str, password: str):
        from neo4j import GraphDatabase

        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self.driver.close()

    def find_entity(self, name: str) -> dict | None:
        query = """
        MATCH (e:Entity)
        WHERE toLower(e.entity_id)=toLower($name)
           OR toLower(e.name_en)=toLower($name)
           OR toLower(e.name_zh)=toLower($name)
           OR any(alias IN e.aliases WHERE toLower(alias)=toLower($name))
        RETURN e LIMIT 1
        """
        with self.driver.session() as session:
            record = session.run(query, name=name).single()
        return dict(record["e"]) if record else None

    def get_neighbors(
        self,
        entity_id: str,
        relation_types: list[str] | None = None,
        include_incoming: bool = True,
    ) -> list[dict]:
        query = """
        MATCH (focus:Entity {entity_id: $entity_id})-[r]-(other:Entity)
        WHERE r.review_status = 'approved'
          AND ($relation_types IS NULL OR type(r) IN $relation_types)
          AND ($include_incoming OR startNode(r) = focus)
        WITH startNode(r) AS a, endNode(r) AS b, r
        RETURN a, type(r) AS relation, r, b
        LIMIT 50
        """
        with self.driver.session() as session:
            records = session.run(
                query,
                entity_id=entity_id,
                relation_types=relation_types,
                include_incoming=include_incoming,
            ).data()
        return [self._record_to_triple(row) for row in records]

    def find_paths(
        self,
        source_id: str,
        target_id: str | None = None,
        max_hops: int = 2,
    ) -> list[dict]:
        if target_id:
            query = """
            MATCH path=(a:Entity {entity_id: $source_id})-[*1..2]->(b:Entity {entity_id: $target_id})
            RETURN path LIMIT 10
            """
            params = {"source_id": source_id, "target_id": target_id}
        else:
            query = """
            MATCH path=(a:Entity {entity_id: $source_id})-[*1..2]->(b:Entity)
            RETURN path LIMIT 10
            """
            params = {"source_id": source_id}
        params["max_hops"] = max_hops
        with self.driver.session() as session:
            records = session.run(query, **params).data()
        return [{"triples": self._path_to_triples(row["path"])} for row in records]

    def validate_path(self, triples: list[dict]) -> bool:
        query = """
        MATCH (a:Entity {entity_id: $source_id})-[r]->(b:Entity {entity_id: $target_id})
        WHERE type(r) = $relation AND r.review_status = 'approved'
        RETURN count(r) AS count
        """
        with self.driver.session() as session:
            for triple in triples:
                record = session.run(query, **triple).single()
                if not record or record["count"] == 0:
                    return False
        return True

    def _record_to_triple(self, row: dict) -> dict:
        a = dict(row["a"])
        b = dict(row["b"])
        rel = dict(row["r"])
        return {
            "source_id": a["entity_id"],
            "source_name": a["name_zh"],
            "relation": row["relation"],
            "target_id": b["entity_id"],
            "target_name": b["name_zh"],
            "relation_id": rel.get("relation_id", ""),
            "evidence_source_id": rel.get("evidence_source_id"),
            "evidence_chunk_ids": rel.get("evidence_chunk_ids", []),
            "review_status": rel.get("review_status", ""),
        }

    def _path_to_triples(self, path) -> list[dict]:
        triples = []
        for rel in path.relationships:
            start = dict(rel.start_node)
            end = dict(rel.end_node)
            props = dict(rel)
            triples.append({
                "source_id": start["entity_id"],
                "source_name": start["name_zh"],
                "relation": rel.type,
                "target_id": end["entity_id"],
                "target_name": end["name_zh"],
                "relation_id": props.get("relation_id", ""),
                "evidence_source_id": props.get("evidence_source_id"),
                "evidence_chunk_ids": props.get("evidence_chunk_ids", []),
                "review_status": props.get("review_status", ""),
            })
        return triples
