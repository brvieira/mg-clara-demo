"""Popula as coleções policy_clauses e customer_profile com dados de exemplo."""
import json
from pathlib import Path
from datetime import datetime, timezone

from src.db import get_db
from src.embeddings import embed
from src.config import POLICY_CLAUSES_COLLECTION, CUSTOMER_PROFILE_COLLECTION

DATA_DIR = Path(__file__).parent.parent / "data"


def seed_customers(db) -> None:
    collection = db[CUSTOMER_PROFILE_COLLECTION]
    collection.drop()
    profiles = json.loads((DATA_DIR / "seed_customer_profiles.json").read_text())
    collection.insert_many(profiles)
    print(f"[seed] {len(profiles)} customer profiles inseridos")


def seed_clauses(db) -> None:
    collection = db[POLICY_CLAUSES_COLLECTION]
    collection.drop()
    clauses = json.loads((DATA_DIR / "seed_policy_clauses.json").read_text())

    now = datetime.now(timezone.utc).isoformat()
    for clause in clauses:
        print(f"[seed] gerando embedding para: {clause['clause_id']}")
        clause["embedding"] = embed(clause["text"])
        clause["updated_at"] = now

    collection.insert_many(clauses)
    print(f"[seed] {len(clauses)} cláusulas inseridas com embeddings")


def run() -> None:
    db = get_db()
    seed_customers(db)
    seed_clauses(db)
    print("[seed] concluído")


if __name__ == "__main__":
    run()
