import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.environ["MONGODB_URI"]
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "claraseg")
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
VECTOR_INDEX_NAME = os.getenv("VECTOR_INDEX_NAME", "policy_clauses_vector_index")

POLICY_CLAUSES_COLLECTION = "policy_clauses"
CUSTOMER_PROFILE_COLLECTION = "customer_profile"
