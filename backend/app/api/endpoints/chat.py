"""Chat endpoint: Gemini AI agent for reconciliation queries."""

from fastapi import APIRouter

from app.schemas.schemas import ChatRequest, ChatResponse
from app.services.ai_agent import GeminiAgent

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    agent = GeminiAgent()
    response = agent.chat(req.session_id, req.message)
    return ChatResponse(response=response)
