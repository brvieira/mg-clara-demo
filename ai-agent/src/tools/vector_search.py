from langchain_core.tools import tool

from src.db import get_db
from src.embeddings import embed
from src.config import POLICY_CLAUSES_COLLECTION, VECTOR_INDEX_NAME

# Chunks de ingestão que só trazem o título da seção/número da cláusula (sem corpo de
# texto) ou o índice do documento não ajudam a responder nada — abaixo desse tamanho
# descartamos o candidato e buscamos mais fundo para preencher top_k com conteúdo real.
MIN_CHUNK_CHARS = 200


def search_clauses(query: str, category: str | None = None, top_k: int = 3) -> list[dict]:
    """Implementação interna da busca semântica via Atlas Vector Search."""
    query_embedding = embed(query)

    vector_search_stage = {
        "$vectorSearch": {
            "index": VECTOR_INDEX_NAME,
            "path": "embedding",
            "queryVector": query_embedding,
            "numCandidates": 50,
            "limit": top_k * 4,
        }
    }

    if category:
        vector_search_stage["$vectorSearch"]["filter"] = {"metadata.category": {"$eq": category}}

    pipeline = [
        vector_search_stage,
        {"$match": {"$expr": {"$gte": [{"$strLenCP": "$text"}, MIN_CHUNK_CHARS]}}},
        {"$limit": top_k},
        {
            "$project": {
                "_id": 0,
                "score": {"$meta": "vectorSearchScore"},
                "text": 1,
                "category": "$metadata.category",
                "section": "$metadata.section",
                "source_file": "$metadata.source_file",
                "pages": "$metadata.pages",
            }
        },
    ]

    results = list(get_db()[POLICY_CLAUSES_COLLECTION].aggregate(pipeline))
    return [
        {
            "category": r.get("category"),
            "section": r.get("section"),
            "source_file": r.get("source_file"),
            "pages": r.get("pages"),
            "text": r["text"],
            "score": round(r.get("score", 0), 4),
        }
        for r in results
    ]


@tool
def vector_search_clausulas(query: str, category: str | None = None) -> list[dict]:
    """
    Busca cláusulas de apólice relevantes por similaridade semântica.

    Use esta tool SEMPRE que o cliente relatar um acidente, sinistro ou incidente
    (colisão, roubo, dano, etc.), ou perguntar sobre coberturas, exclusões, franquia,
    prazos de acionamento ou qualquer condição contratual.
    NÃO use para perguntas sobre dados do perfil já disponíveis (número de apólice,
    status de sinistro, dados cadastrais) — esses você responde diretamente.

    Args:
        query: descreva o evento ou tópico exatamente como o cliente mencionou.
        category: opcional — passe "auto", "residencial" ou "vida" se for
                  possível inferir do tipo de apólice do cliente a partir do perfil.
    """
    return search_clauses(query, category=category)
