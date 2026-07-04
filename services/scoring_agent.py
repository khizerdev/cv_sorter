import os
import json
from typing import TypedDict, List, Optional
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from langgraph.graph import StateGraph, END

from services.vector_store import search_candidates

load_dotenv()

# ─── LLM setup ───────────────────────────────────────────────────────────────
# ChatGroq is LangChain's wrapper around Groq API.
# We use it here instead of raw Groq SDK because LangChain chains 
# and LangGraph nodes expect LangChain-compatible LLM objects.
llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model="llama-3.3-70b-versatile",
    temperature=0
)


# ─── State definition ────────────────────────────────────────────────────────
# State is the shared object that flows through every node in the graph.
# Each node reads from state and writes back to state.
# TypedDict gives us type hints so we know what's in state at every step.
class AgentState(TypedDict):
    job_description: str           # input from user
    top_n: int                     # how many candidates to retrieve
    candidates: List[dict]         # raw candidates from ChromaDB
    scored: List[dict]             # candidates with scores added
    shortlisted: List[dict]        # only candidates who passed threshold
    rejected: List[dict]           # candidates who didn't pass
    final_report: Optional[str]    # human-readable summary


# ─── Node 1: Retrieve ────────────────────────────────────────────────────────
def retrieve_node(state: AgentState) -> AgentState:
    """
    First node: queries ChromaDB for the top-N candidates
    most similar to the job description.
    Writes the results into state["candidates"].
    """
    print("📥 [Node 1] Retrieving candidates from ChromaDB...")

    matches = search_candidates(state["job_description"], state["top_n"])
    state["candidates"] = matches

    print(f"   Found {len(matches)} candidates")
    return state


# ─── Node 2: Score ───────────────────────────────────────────────────────────
def score_node(state: AgentState) -> AgentState:
    """
    Second node: for each candidate, asks Groq to score them 0-100
    against the job description using multi-criteria reasoning.
    """
    print("🧠 [Node 2] Scoring candidates with Groq...")

    scoring_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert technical recruiter.
Score a candidate against a job description. Return ONLY a JSON object, no explanation:
{{
  "score": <integer 0-100>,
  "skills_match": <integer 0-100>,
  "experience_match": <integer 0-100>,
  "reasoning": "<one sentence explaining the score>"
}}

Scoring guide:
- 80-100: Excellent fit, meets almost all requirements
- 60-79: Good fit, meets most requirements  
- 40-59: Partial fit, meets some requirements
- 0-39: Poor fit, missing key requirements"""),
        ("user", """Job Description:
{job_description}

Candidate Profile:
{candidate_profile}

Score this candidate.""")
    ])

    scored = []
    for candidate in state["candidates"]:
        # Build a readable profile string for Groq to evaluate
        profile_text = f"""
Name: {candidate.get('name', 'Unknown')}
Current Role: {candidate.get('current_role', 'N/A')}
Years of Experience: {candidate.get('years_experience', 'N/A')}
Similarity Score (semantic): {candidate.get('similarity_score', 0)}
"""
        try:
            chain = scoring_prompt | llm
            response = chain.invoke({
                "job_description": state["job_description"],
                "candidate_profile": profile_text
            })

            result = json.loads(response.content)

            candidate_with_score = {
                **candidate,
                "ai_score": result.get("score", 0),
                "skills_match": result.get("skills_match", 0),
                "experience_match": result.get("experience_match", 0),
                "reasoning": result.get("reasoning", "")
            }
            scored.append(candidate_with_score)

        except Exception as e:
            print(f"   ⚠️ Scoring failed for candidate {candidate.get('name')}: {e}")
            # Don't crash — give failed candidates a score of 0
            scored.append({**candidate, "ai_score": 0, "reasoning": "Scoring failed"})

    # Sort by ai_score descending
    scored.sort(key=lambda x: x["ai_score"], reverse=True)
    state["scored"] = scored

    print(f"   Scored {len(scored)} candidates")
    return state


# ─── Node 3: Route (shortlist vs reject) ────────────────────────────────────
def route_node(state: AgentState) -> AgentState:
    """
    Third node: splits scored candidates into shortlisted and rejected
    based on a threshold. This is the actual 'sorting' decision.
    """
    print("🔀 [Node 3] Routing candidates...")

    THRESHOLD = 60  # candidates scoring >= 60 are shortlisted

    shortlisted = [c for c in state["scored"] if c["ai_score"] >= THRESHOLD]
    rejected = [c for c in state["scored"] if c["ai_score"] < THRESHOLD]

    state["shortlisted"] = shortlisted
    state["rejected"] = rejected

    print(f"   ✅ Shortlisted: {len(shortlisted)} | ❌ Rejected: {len(rejected)}")
    return state


# ─── Node 4: Summarize ───────────────────────────────────────────────────────
def summarize_node(state: AgentState) -> AgentState:
    """
    Final node: generates a human-readable report of the shortlisted candidates.
    This is what you'd send to a hiring manager.
    """
    print("📝 [Node 4] Generating final report...")

    if not state["shortlisted"]:
        state["final_report"] = "No candidates met the minimum threshold of 60/100 for this role."
        return state

    summary_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a recruitment assistant. Write a clear, concise hiring report."),
        ("user", """Write a short hiring report for these shortlisted candidates for the role below.
For each candidate give: rank, name, score, and one sentence on why they are a good fit.
End with a recommendation on who to interview first.

Job Description: {job_description}

Shortlisted Candidates:
{candidates_text}""")
    ])

    candidates_text = "\n\n".join([
        f"Rank {i+1}: {c['name']} | Score: {c['ai_score']}/100 | "
        f"Role: {c['current_role']} | Experience: {c['years_experience']} yrs | "
        f"Reasoning: {c['reasoning']}"
        for i, c in enumerate(state["shortlisted"])
    ])

    chain = summary_prompt | llm
    response = chain.invoke({
        "job_description": state["job_description"],
        "candidates_text": candidates_text
    })

    state["final_report"] = response.content
    print("   Report generated")
    return state


# ─── Build the graph ─────────────────────────────────────────────────────────
def build_agent():
    """
    Assembles the LangGraph StateGraph — wires nodes together in order.
    Think of this like drawing arrows between boxes in a flowchart.
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("score", score_node)
    graph.add_node("route", route_node)
    graph.add_node("summarize", summarize_node)

    # Connect nodes in sequence
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "score")
    graph.add_edge("score", "route")
    graph.add_edge("route", "summarize")
    graph.add_edge("summarize", END)

    return graph.compile()


# Single compiled agent instance — reused across requests
agent = build_agent()


def run_agent(job_description: str, top_n: int = 5) -> dict:
    """
    Public function to run the full agent pipeline.
    Call this from your FastAPI endpoint.
    """
    initial_state: AgentState = {
        "job_description": job_description,
        "top_n": top_n,
        "candidates": [],
        "scored": [],
        "shortlisted": [],
        "rejected": [],
        "final_report": None
    }

    final_state = agent.invoke(initial_state)

    return {
        "shortlisted": final_state["shortlisted"],
        "rejected": final_state["rejected"],
        "final_report": final_state["final_report"],
        "total_evaluated": len(final_state["scored"])
    }