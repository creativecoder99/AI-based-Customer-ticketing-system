from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from src.database import (
    init_db,
    create_user,
    get_user_by_email,
    create_ticket,
    create_decision,
    get_tickets_by_user,
    get_ticket_by_id
)
from src.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)
from src.retrieval import rag_pipeline
from src.decision import generate_decision, DecisionOutput


# Lifespan context for DB initialization
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Minimal AI Decision API",
    description="Support-ticket decision assistant with FastAPI, JWT, SQLite, and RAG",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Request / Response Schemas
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: str


class TicketCreateRequest(BaseModel):
    message: str = Field(..., min_length=3, description="Support ticket inquiry or issue description")
    meta: Optional[Dict[str, Any]] = Field(default=None, description="Optional order metadata context (value, delivery days, dispatch days, status, etc.)")


class DecisionResponse(BaseModel):
    id: int
    ticket_id: int
    action: str
    reason: str
    confidence: float
    sources: List[str]
    created_at: str


class TicketDetailResponse(BaseModel):
    id: int
    user_id: int
    message: str
    created_at: str
    decision: Optional[DecisionResponse] = None


# Endpoints
@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint confirming API and RAG pipeline readiness."""
    return {
        "status": "healthy",
        "service": "Minimal AI Decision API",
        "rag_chunks_loaded": len(rag_pipeline.chunks)
    }


@app.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"]
)
def register(request: RegisterRequest):
    """Register a new user account with unique email and hashed password."""
    existing_user = get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )

    pwd_hash = hash_password(request.password)
    new_user = create_user(request.email, pwd_hash)
    return new_user


@app.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"]
)
def login(request: LoginRequest):
    """Authenticate user credentials and issue a signed JWT Bearer token."""
    user = get_user_by_email(request.email)
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    token = create_access_token(data={"user_id": user["id"], "email": user["email"]})
    return {"access_token": token, "token_type": "bearer"}


@app.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    tags=["Authentication"]
)
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user


@app.post(
    "/tickets",
    response_model=TicketDetailResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Tickets"]
)
def submit_ticket(
    request: TicketCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Submit a support ticket, run RAG retrieval over policy documents,
    generate a grounded AI decision, persist ticket and decision, and return the result.
    """
    # 1. Insert ticket
    ticket = create_ticket(user_id=current_user["id"], message=request.message)

    # 2. RAG retrieval
    retrieved_chunks = rag_pipeline.retrieve(request.message, top_k=3)

    # 3. AI decision generation & validation
    decision_out: DecisionOutput = generate_decision(
        ticket_message=request.message,
        retrieved_chunks=retrieved_chunks,
        meta=request.meta
    )

    # 4. Persist decision in SQLite
    saved_decision = create_decision(
        ticket_id=ticket["id"],
        action=decision_out.action,
        reason=decision_out.reason,
        confidence=decision_out.confidence,
        sources=decision_out.sources
    )

    return {
        "id": ticket["id"],
        "user_id": ticket["user_id"],
        "message": ticket["message"],
        "created_at": ticket["created_at"],
        "decision": saved_decision
    }


@app.get(
    "/tickets",
    response_model=List[TicketDetailResponse],
    status_code=status.HTTP_200_OK,
    tags=["Tickets"]
)
def list_tickets(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return all tickets and their associated decisions submitted by the authenticated user."""
    tickets = get_tickets_by_user(user_id=current_user["id"])
    return tickets


@app.get(
    "/tickets/{ticket_id}",
    response_model=TicketDetailResponse,
    status_code=status.HTTP_200_OK,
    tags=["Tickets"]
)
def get_ticket(
    ticket_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Return a single ticket and its decision.
    Strict tenant authorization: returns 403 Forbidden if ticket belongs to a different user.
    """
    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket #{ticket_id} not found."
        )

    # Strict authorization isolation check
    if ticket["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: You do not have permission to view this ticket."
        )

    return ticket
