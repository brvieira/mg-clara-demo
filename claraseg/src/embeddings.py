from openai import OpenAI
from src.config import OPENAI_API_KEY, EMBEDDING_MODEL

_client = OpenAI(api_key=OPENAI_API_KEY)


def embed(text: str) -> list[float]:
    response = _client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return response.data[0].embedding
