from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    customer_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    long_term_facts: list[dict]
    customer_profile: dict | None
    new_fact_to_save: dict | None
