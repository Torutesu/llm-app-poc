"""
FastAPI endpoints for chat and RAG search.

Provides:
- Chat query with RAG
- Conversation history
- Search across connected data sources
"""
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.auth_api import get_current_user
from auth.user_manager import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ============================================================
# Request/Response Models
# ============================================================

class ChatMessage(BaseModel):
    """A single chat message."""

    role: str = Field(description="Message role: user or assistant")
    content: str = Field(description="Message content")
    timestamp: Optional[float] = Field(default=None, description="Unix timestamp")


class Source(BaseModel):
    """A source document for RAG."""

    title: str = Field(description="Document title")
    content: str = Field(description="Relevant content snippet")
    url: Optional[str] = Field(default=None, description="Link to source")
    connector_type: Optional[str] = Field(default=None, description="Source type")
    score: Optional[float] = Field(default=None, description="Relevance score")


class ChatQueryRequest(BaseModel):
    """Request to query chat with RAG."""

    query: str = Field(description="User question")
    conversation_history: List[ChatMessage] = Field(
        default_factory=list,
        description="Previous messages in conversation"
    )
    max_sources: int = Field(default=5, description="Maximum sources to retrieve")
    use_web_search: bool = Field(default=True, description="Enable web search fallback")
    search_mode: str = Field(
        default="auto",
        description="Search mode: auto, rag_only, web_only, llm_only"
    )


class ChatQueryResponse(BaseModel):
    """Response from chat query."""

    answer: str = Field(description="Generated answer")
    sources: List[Source] = Field(default_factory=list, description="Source documents")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")


class ConversationSummary(BaseModel):
    """Summary of a conversation."""

    conversation_id: str
    title: str
    created_at: float
    updated_at: float
    message_count: int


# ============================================================
# Mock Data (Replace with real implementation)
# ============================================================

# Mock conversations storage
CONVERSATIONS = {}

# Mock sources for demo
MOCK_SOURCES = [
    {
        "title": "Slack - #product-team",
        "content": "Discussion about Q4 planning and feature priorities for the upcoming release.",
        "url": "https://slack.com/archives/C123456",
        "connector_type": "slack",
        "score": 0.95
    },
    {
        "title": "Google Drive - Q4 Planning.docx",
        "content": "Detailed quarterly planning document outlining goals, milestones, and resource allocation.",
        "url": "https://drive.google.com/file/d/abc123",
        "connector_type": "google_drive",
        "score": 0.89
    },
    {
        "title": "Slack - #engineering",
        "content": "Technical discussion about implementation details and architecture decisions.",
        "url": "https://slack.com/archives/C789012",
        "connector_type": "slack",
        "score": 0.82
    }
]


# ============================================================
# Chat Endpoints
# ============================================================

@router.post("/query", response_model=ChatQueryResponse)
async def chat_query(
    request: ChatQueryRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Query chat with RAG search, Web search, or LLM.

    Search modes:
    - auto: Try RAG first, fallback to Web search, then LLM
    - rag_only: Only search connected data sources
    - web_only: Only use web search
    - llm_only: Direct LLM response without context
    """
    try:
        logger.info(f"Chat query from user {current_user.user_id}: {request.query} (mode: {request.search_mode})")

        sources = []
        answer = ""

        # Determine search strategy
        if request.search_mode == "llm_only":
            # Direct LLM response
            answer = generate_llm_answer(request.query, request.conversation_history)

        elif request.search_mode == "web_only":
            # Web search only
            sources = await perform_web_search(request.query, request.max_sources)
            answer = generate_answer_from_sources(request.query, sources, "web")

        elif request.search_mode == "rag_only":
            # RAG search only (connected data sources)
            sources = await perform_rag_search(request.query, current_user.tenant_id, request.max_sources)
            answer = generate_answer_from_sources(request.query, sources, "rag")

        else:  # auto mode
            # Try RAG first
            sources = await perform_rag_search(request.query, current_user.tenant_id, request.max_sources)

            # If no good RAG results and web search enabled, try web search
            if (not sources or all(s.get("score", 0) < 0.5 for s in sources)) and request.use_web_search:
                logger.info("RAG sources insufficient, trying web search")
                web_sources = await perform_web_search(request.query, 3)
                sources.extend(web_sources)

            # If still no sources, use LLM directly
            if not sources:
                logger.info("No sources found, using LLM directly")
                answer = generate_llm_answer(request.query, request.conversation_history)
            else:
                answer = generate_answer_from_sources(request.query, sources, "hybrid")

        return ChatQueryResponse(
            answer=answer,
            sources=[Source(**s) for s in sources]
        )

    except Exception as e:
        logger.error(f"Error processing chat query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/query/stream")
async def chat_query_stream(
    request: ChatQueryRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Query chat with streaming response.

    Returns Server-Sent Events (SSE) for real-time response.
    """
    async def generate_stream():
        """Generate streaming response."""
        try:
            # Get sources first
            sources = get_mock_sources(request.query, request.max_sources)

            # Stream answer token by token
            answer = generate_mock_answer(request.query, current_user)
            words = answer.split()

            # Send sources first
            yield f"data: {{'type': 'sources', 'sources': {sources}}}\n\n"

            # Stream answer
            for i, word in enumerate(words):
                yield f"data: {{'type': 'token', 'content': '{word} '}}\n\n"
                time.sleep(0.05)  # Simulate streaming delay

            # Send completion
            yield f"data: {{'type': 'done'}}\n\n"

        except Exception as e:
            logger.error(f"Error in streaming: {e}")
            yield f"data: {{'type': 'error', 'message': '{str(e)}'}}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/conversations", response_model=List[ConversationSummary])
async def list_conversations(
    current_user: User = Depends(get_current_user)
):
    """
    List user's conversation history.
    """
    # TODO: Retrieve from database
    user_conversations = [
        conv for conv in CONVERSATIONS.values()
        if conv.get("user_id") == current_user.user_id
    ]

    return [
        ConversationSummary(
            conversation_id=conv["id"],
            title=conv["title"],
            created_at=conv["created_at"],
            updated_at=conv["updated_at"],
            message_count=len(conv["messages"])
        )
        for conv in user_conversations
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get conversation details including all messages.
    """
    conversation = CONVERSATIONS.get(conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Check permission
    if conversation["user_id"] != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return conversation


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a conversation.
    """
    conversation = CONVERSATIONS.get(conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Check permission
    if conversation["user_id"] != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    del CONVERSATIONS[conversation_id]

    return {"message": "Conversation deleted successfully"}


# ============================================================
# Helper Functions
# ============================================================

def generate_mock_answer(query: str, user: User) -> str:
    """
    Generate a mock answer based on the query.

    TODO: Replace with real LLM integration.
    """
    # Simple keyword-based responses for demo
    query_lower = query.lower()

    if "meeting" in query_lower or "discussion" in query_lower:
        return f"""Based on recent Slack conversations in #product-team and #engineering, here are the key points:

**Main Discussion Topics:**
1. Q4 Planning and Priorities
2. Feature roadmap for the next release
3. Resource allocation and team capacity

**Key Decisions:**
- Focus on customer-facing features first
- Allocate 20% of time for technical debt
- Weekly sync meetings on Mondays at 10am

**Action Items:**
- Finalize feature specifications by end of week
- Set up project tracking in Jira
- Schedule follow-up discussions with stakeholders

The team is aligned on priorities and moving forward with implementation."""

    elif "document" in query_lower or "planning" in query_lower:
        return f"""I found several relevant planning documents in your Google Drive:

**Q4 Planning.docx** contains:
- Quarterly goals and objectives
- Timeline with key milestones
- Budget and resource requirements
- Success metrics and KPIs

**Key Highlights:**
- Target: 30% increase in user engagement
- Launch 3 major features this quarter
- Improve system performance by 40%

**Timeline:**
- October: Planning and design phase
- November: Development sprint 1-2
- December: Testing and launch

All stakeholders have reviewed and approved the plan. Implementation starts next week."""

    elif "deadline" in query_lower or "timeline" in query_lower:
        return f"""Based on project documents and team discussions, here are the upcoming deadlines:

**This Week:**
- Feature spec review (Friday, 5pm)
- Design mockups submission (Thursday)

**Next 2 Weeks:**
- Sprint 1 completion (Nov 15)
- API integration testing (Nov 18)

**End of Month:**
- Beta launch (Nov 30)
- User acceptance testing (Nov 28-30)

**Critical Path Items:**
- Database migration must complete by Nov 10
- External API approval needed by Nov 12

Most teams are on track. Engineering flagged potential delay in API integration - monitoring closely."""

    elif "roadmap" in query_lower or "product" in query_lower:
        return f"""Here's a summary of the product roadmap based on recent planning documents and discussions:

**Short-term (Q4 2025):**
1. Enhanced search functionality with AI
2. Real-time collaboration features
3. Mobile app improvements

**Medium-term (Q1 2026):**
1. Enterprise SSO integration
2. Advanced analytics dashboard
3. API marketplace launch

**Long-term (H1 2026):**
1. Multi-language support
2. AI-powered insights
3. Integration ecosystem expansion

**Customer Feedback Integration:**
- Top request: Better mobile experience (in progress)
- Second: More integrations (planned for Q1)
- Third: Customizable dashboards (under consideration)

The roadmap is reviewed quarterly and adjusted based on customer needs and market conditions."""

    else:
        # Generic response
        return f"""I've searched across your connected data sources (Slack, Google Drive, etc.) for information about "{query}".

**What I found:**
Based on recent conversations and documents, here's what's relevant to your question:

1. **From Slack #product-team:** Ongoing discussions about planning and priorities align with your query.

2. **From Google Drive:** Several planning documents contain related information and context.

3. **From team discussions:** Multiple stakeholders have shared insights that may be helpful.

**Summary:**
The information suggests that your team is actively working on related initiatives. Check the sources below for detailed context and specific action items.

**Recommendation:**
Review the linked Slack threads and documents for complete details. Consider scheduling a follow-up meeting with stakeholders if more clarity is needed.

Would you like me to search for more specific information or focus on a particular aspect?"""


def get_mock_sources(query: str, max_sources: int = 5) -> List[dict]:
    """
    Get mock sources for the query.

    TODO: Replace with real vector search.
    """
    # Return first N mock sources
    return MOCK_SOURCES[:max_sources]
