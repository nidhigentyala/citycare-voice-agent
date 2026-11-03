from typing import Annotated, TypedDict

from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from dotenv import load_dotenv

load_dotenv(".env.local")

class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    intent: str

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
)

def classify_intent(state: State):
    """Classify the user's request."""

    user_message = state["messages"][-1].content

    text = user_message.lower()

    if any(word in text for word in ["book", "appointment", "schedule"]):
        intent = "appointment"

    elif any(word in text for word in [
        "cancel",
        "late",
        "policy",
        "doctor",
        "payment",
    ]):
        intent = "policy"

    elif any(word in text for word in [
        "hour",
        "open",
        "address",
        "parking",
        "service",
        "insurance",
    ]):
        intent = "clinic_information"

    else:
        intent = "general"

    return {
        "intent": intent
    }


def answer(state: State):
    """Generate the final answer."""

    intent = state["intent"]

    system_message = SystemMessage(
        content=f"""
You are the friendly front desk assistant for CityCare Clinic.

The user's intent has been classified as: {intent}

Answer the user's question naturally and briefly.

Do not provide medical advice.
Do not invent clinic policy information.
If the question is unrelated to CityCare Clinic, politely say
you can only help with CityCare Clinic.
"""
    )

    messages = [system_message] + state["messages"]

    response = llm.invoke(messages)

    return {
        "messages": [response]
    }


def create_graph():
    builder = StateGraph(State)

    builder.add_node(
        "classify_intent",
        classify_intent,
    )

    builder.add_node(
        "answer",
        answer,
    )

    builder.add_edge(
        START,
        "classify_intent",
    )

    builder.add_edge(
        "classify_intent",
        "answer",
    )

    return builder.compile()


graph = create_graph()