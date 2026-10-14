"""Optional graph store on Neo4j. Select it with GRAPH_STORE=neo4j and NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD.

Model:  (:Chunk {key, profile_id, document_id, idx, source, page, text}) -[:MENTIONS]-> (:Entity {key, norm, label, profile_id})
Entities are per profile (key = "<profile>|<norm>"), so businesses never share nodes.
"""
from __future__ import annotations

from typing import Sequence

from ..config import Settings
from ..http import ProviderError
from ..vectorstores.base import Chunk, Hit
from .base import MIN_ENTITY_LEN, Entity, GraphInfo, GraphStore, norm_entity

HOP2_ENTITIES = 12
SETUP = (
    "CREATE CONSTRAINT chunk_key IF NOT EXISTS FOR (c:Chunk) REQUIRE c.key IS UNIQUE",
    "CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (n:Entity) REQUIRE n.key IS UNIQUE",
    "CREATE INDEX chunk_doc IF NOT EXISTS FOR (c:Chunk) ON (c.document_id)",
    "CREATE INDEX entity_norm IF NOT EXISTS FOR (n:Entity) ON (n.norm)",
)
ORPHANS = "MATCH (n:Entity) WHERE NOT (n)<-[:MENTIONS]-() DELETE n"


class Neo4jGraphStore(GraphStore):
    def __init__(self, settings: Settings):
        try:
            from neo4j import GraphDatabase
        except ImportError as e:
            raise ProviderError('The neo4j driver is not installed. Run: pip install neo4j  (or pip install -e ".[neo4j]")') from e
        self.uri, self.database = settings.neo4j_uri, settings.neo4j_database or None
        self.driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
        try:
            self.driver.verify_connectivity()
            for q in SETUP:
                self._run(q)
        except Exception as e:
            self.driver.close()
            raise ProviderError(f"Cannot connect to Neo4j at {settings.neo4j_uri}: {e}") from e

    def _run(self, query: str, **params) -> list[dict]:
        with self.driver.session(database=self.database) as s:
            return [dict(r) for r in s.run(query, **params)]

    def add(self, rows: Sequence[tuple[Chunk, Sequence[str]]]) -> None:
        payload = []
        for ch, entities in rows:
            seen: dict[str, str] = {}
            for e in entities:
                n = norm_entity(e)
                if len(n) >= MIN_ENTITY_LEN:
                    seen.setdefault(n, e.strip())
            payload.append({"key": f"{ch.document_id}#{ch.index}", "profile_id": ch.profile_id, "document_id": ch.document_id,
                            "idx": ch.index, "source": ch.source, "page": ch.page, "text": ch.text,
                            "entities": [{"norm": n, "label": lbl} for n, lbl in seen.items()]})
        if not payload:
            return
        self._run(
            "UNWIND $rows AS r "
            "MERGE (c:Chunk {key: r.key}) SET c.profile_id=r.profile_id, c.document_id=r.document_id, c.idx=r.idx, "
            "c.source=r.source, c.page=r.page, c.text=r.text "
            "WITH c, r UNWIND r.entities AS e "
            "MERGE (n:Entity {key: r.profile_id + '|' + e.norm}) SET n.norm=e.norm, n.label=coalesce(n.label, e.label), n.profile_id=r.profile_id "
            "MERGE (c)-[:MENTIONS]->(n)", rows=payload)

    def delete_document(self, document_id: str) -> None:
        self._run("MATCH (c:Chunk {document_id: $d}) DETACH DELETE c", d=document_id)
        self._run(ORPHANS)

    def delete_profile(self, profile_id: str) -> None:
        self._run("MATCH (c:Chunk {profile_id: $p}) DETACH DELETE c", p=profile_id)
        self._run("MATCH (n:Entity {profile_id: $p}) DETACH DELETE n", p=profile_id)

    def reset(self) -> None:
        self._run("MATCH (n) WHERE n:Chunk OR n:Entity DETACH DELETE n")

    def has_data(self, profile_ids: Sequence[str]) -> bool:
        return bool(self._run("MATCH (n:Entity) WHERE n.profile_id IN $p RETURN 1 AS x LIMIT 1", p=list(profile_ids)))

    def find_in_text(self, text: str, profile_ids: Sequence[str], limit: int = 8) -> list[Entity]:
        rows = self._run("MATCH (n:Entity) WHERE n.profile_id IN $p AND $q CONTAINS n.norm "
                         "RETURN n.norm AS norm, min(n.label) AS label, size(n.norm) AS len "
                         "ORDER BY len DESC LIMIT $limit", p=list(profile_ids), q=norm_entity(text), limit=limit)
        return [Entity(r["norm"], r["label"]) for r in rows]

    def entities_of(self, chunks: Sequence[tuple[str, int]], limit: int = 6) -> list[Entity]:
        if not chunks:
            return []
        rows = self._run("MATCH (c:Chunk)-[:MENTIONS]->(n:Entity) WHERE c.key IN $keys "
                         "RETURN n.norm AS norm, min(n.label) AS label, count(*) AS k ORDER BY k DESC LIMIT $limit",
                         keys=[f"{d}#{i}" for d, i in chunks], limit=limit)
        return [Entity(r["norm"], r["label"]) for r in rows]

    def _mentioning(self, norms: Sequence[str], pids: Sequence[str], limit: int) -> list[dict]:
        return self._run("MATCH (n:Entity)<-[:MENTIONS]-(c:Chunk) WHERE n.profile_id IN $p AND n.norm IN $norms "
                         "WITH c, count(DISTINCT n) AS k RETURN c.document_id AS d, c.idx AS i, c.profile_id AS profile, "
                         "c.source AS source, c.page AS page, c.text AS text, k ORDER BY k DESC LIMIT $limit",
                         p=list(pids), norms=list(norms), limit=limit)

    def neighbors(self, entities, profile_ids, limit, exclude, hops: int = 2) -> list[Hit]:
        norms = [e.norm for e in entities]
        if not norms or limit <= 0:
            return []
        room = limit + len(exclude)
        found: dict[tuple[str, int], tuple[float, dict]] = {}
        for r in self._mentioning(norms, profile_ids, room):
            found[(r["d"], r["i"])] = (r["k"] / len(norms), r)
        if hops >= 2:
            near = self._run("MATCH (n:Entity)<-[:MENTIONS]-(:Chunk)-[:MENTIONS]->(m:Entity) "
                             "WHERE n.profile_id IN $p AND n.norm IN $norms AND m.profile_id = n.profile_id AND NOT m.norm IN $norms "
                             "RETURN m.norm AS norm, count(*) AS k ORDER BY k DESC LIMIT $limit",
                             p=list(profile_ids), norms=norms, limit=HOP2_ENTITIES)
            near_norms = [r["norm"] for r in near]
            if near_norms:
                for r in self._mentioning(near_norms, profile_ids, room):
                    found.setdefault((r["d"], r["i"]), (0.5 * r["k"] / len(near_norms), r))
        ranked = [(k, v) for k, v in sorted(found.items(), key=lambda kv: -kv[1][0]) if k not in exclude][:limit]
        return [Hit(r["profile"], d, r["source"], i, r["text"], round(score, 4), r["page"]) for (d, i), (score, r) in ranked]

    def ping(self) -> GraphInfo:
        chunks = self._run("MATCH (c:Chunk) RETURN count(c) AS n")[0]["n"]
        entities = self._run("MATCH (n:Entity) RETURN count(n) AS n")[0]["n"]
        return GraphInfo("neo4j", self.uri, chunks, entities)

    def close(self) -> None:
        self.driver.close()
