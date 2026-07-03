"""Popula a coleção customer_profile com dados de exemplo."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# ai-agent/ lives in a sibling directory; add it to sys.path so `from src...`
# imports resolve.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ai-agent"))

from src.db import get_db
from src.embeddings import embed
from src.config import CUSTOMER_PROFILE_COLLECTION, WORKSHOPS_COLLECTION

DATA_DIR = Path(__file__).parent


def seed_customers(db) -> None:
    collection = db[CUSTOMER_PROFILE_COLLECTION]
    collection.drop()
    profiles = json.loads((DATA_DIR / "seed_customer_profiles.json").read_text())
    collection.insert_many(profiles)
    print(f"[seed] {len(profiles)} customer profiles inseridos")


def seed_workshops(db) -> None:
    collection = db[WORKSHOPS_COLLECTION]
    collection.drop()
    workshops = json.loads((DATA_DIR / "seed_workshops.json").read_text())
    collection.insert_many(workshops)
    print(f"[seed] {len(workshops)} oficinas inseridas")


def run() -> None:
    db = get_db()
    seed_customers(db)
    seed_workshops(db)
    print("[seed] concluído")


if __name__ == "__main__":
    run()
