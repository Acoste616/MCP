from fastapi import APIRouter, WebSocket, HTTPException, WebSocketDisconnect, Depends, Body, Query
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_models import (
    Context, 
    Message, 
    ModelInfo, 
    SessionResponse,
    ModelRequest, # For potential future use
    ModelResponse # For potential future use
)
from app.services.mcp_service import MCPService
from app.api.deps import get_session # Assuming your DB session dependency is here

# Dependency to get MCPService instance
def get_mcp_service() -> MCPService:
    return MCPService()

router = APIRouter(
    prefix="/mcp",
    tags=["mcp"],
)

# --- Session Management Endpoints ---
@router.post("/sessions", response_model=SessionResponse)
async def create_new_session(
    session_id: str = Body(..., embed=True),
    initial_metadata: Optional[Dict[str, Any]] = Body(None, embed=True),
    # initial_context_data: Optional[Dict[str, Any]] = Body(None), # More complex, handle later if needed
    service: MCPService = Depends(get_mcp_service),
    db: AsyncSession = Depends(get_session)
):
    """Creates a new session. session_id is required in the body."""
    # For now, initial_context_data is not taken from the request body for simplicity.
    # A default context will be created by the service.
    created_session = await service.create_session(
        db_session=db, 
        session_id=session_id, 
        initial_metadata=initial_metadata
    )
    if not created_session: # Should be handled by service raising an error ideally
        raise HTTPException(status_code=500, detail="Failed to create session")
    # If create_session can return an existing session, a 200 OK might be more appropriate
    # depending on how create_session handles existing session_ids (e.g. if it raises 409 or returns existing)
    # Current service impl: returns existing if found. So 200 is fine.
    return created_session

@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session_details(
    session_id: str,
    service: MCPService = Depends(get_mcp_service),
    db: AsyncSession = Depends(get_session)
):
    session_data = await service.get_session(db_session=db, session_id=session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_data

@router.put("/sessions/{session_id}/context", response_model=SessionResponse)
async def update_session_context_data(
    session_id: str,
    context_update: Dict[str, Any] = Body(...),
    service: MCPService = Depends(get_mcp_service),
    db: AsyncSession = Depends(get_session)
):
    """Updates parts of a session's context (e.g., messages, shared_memory, models)."""
    updated_session = await service.update_session_context(
        db_session=db, 
        session_id=session_id, 
        context_update_data=context_update
    )
    if not updated_session:
        raise HTTPException(status_code=404, detail="Session not found or update failed")
    return updated_session

@router.put("/sessions/{session_id}/metadata", response_model=SessionResponse)
async def update_session_metadata_data(
    session_id: str,
    metadata_update: Dict[str, Any] = Body(...),
    service: MCPService = Depends(get_mcp_service),
    db: AsyncSession = Depends(get_session)
):
    """Updates a session's metadata."""
    updated_session = await service.update_session_metadata(
        db_session=db, 
        session_id=session_id, 
        metadata_update=metadata_update
    )
    if not updated_session:
        raise HTTPException(status_code=404, detail="Session not found or update failed")
    return updated_session

# --- Message Posting Endpoint (Context Update) ---
@router.post("/sessions/{session_id}/messages", response_model=SessionResponse) # Changed from MCPMessage to SessionResponse
async def post_message_to_session_context(
    session_id: str,
    message_data: Dict[str, Any] = Body(..., examples=[{"model_id": "some_model", "content": "Hello world", "id": "optional_message_id"}]),
    service: MCPService = Depends(get_mcp_service),
    db: AsyncSession = Depends(get_session)
):
    """Posts a message to a specific session. The message is added to the session's context."""
    updated_session = await service.post_message_to_session(
        db_session=db, 
        session_id=session_id, 
        message_data=message_data
    )
    if not updated_session:
        # This could be 404 if session not found, or 400/500 if message data is bad / update fails
        raise HTTPException(status_code=404, detail="Session not found or failed to post message")
    return updated_session

@router.get("/sessions/{session_id}/messages", response_model=List[Message])
async def get_session_messages(
    session_id: str, # Consistent with other session endpoints
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: MCPService = Depends(get_mcp_service),
    db: AsyncSession = Depends(get_session)
):
    """Get messages for a session with pagination."""
    messages = await service.get_messages_for_session(
        db_session=db,
        session_id=session_id,
        limit=limit,
        offset=offset
    )
    if messages is None: # Indicates session not found
        raise HTTPException(status_code=404, detail="Session not found")
    return messages

# --- Model Registry Endpoints ---
@router.post("/models", response_model=ModelInfo, status_code=201)
async def register_new_model(
    model_info: ModelInfo, # Pydantic model for request body
    service: MCPService = Depends(get_mcp_service)
    # db: AsyncSession = Depends(get_session) # Not needed if model registry is in-memory
):
    # Note: Model registry is currently in-memory in the service
    registered_model = await service.register_model(model_info)
    # The service currently prints a warning if overwriting, might want specific error handling for conflicts (409)
    return registered_model

@router.get("/models/{model_id}", response_model=ModelInfo)
async def get_model_info(
    model_id: str,
    service: MCPService = Depends(get_mcp_service)
    # db: AsyncSession = Depends(get_session) # Not needed for in-memory registry
):
    model = await service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model

@router.get("/models", response_model=List[ModelInfo])
async def list_all_models(
    service: MCPService = Depends(get_mcp_service)
    # db: AsyncSession = Depends(get_session) # Not needed for in-memory registry
):
    return await service.list_models()


# --- WebSocket Endpoint (Placeholder - Needs more work) ---
class ConnectionManager:
    def __init__(self):
        # (model_id, session_id) -> WebSocket
        self.active_connections: Dict[tuple[str, str], WebSocket] = {}

    async def connect(self, websocket: WebSocket, model_id: str, session_id: str):
        await websocket.accept()
        self.active_connections[(model_id, session_id)] = websocket
        print(f"WS connected: model {model_id} to session {session_id}")

    def disconnect(self, model_id: str, session_id: str):
        if (model_id, session_id) in self.active_connections:
            del self.active_connections[(model_id, session_id)]
        print(f"WS disconnected: model {model_id} from session {session_id}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast_to_session_model(self, message: str, model_id: str, session_id: str, sender: Optional[WebSocket] = None):
        """Broadcasts to all clients connected to the same model_id AND session_id."""
        for (m_id, s_id), connection in self.active_connections.items():
            if m_id == model_id and s_id == session_id and connection != sender:
                try:
                    await connection.send_text(message)
                except RuntimeError as e:
                    # Handle cases where websocket might be closed unexpectedly
                    print(f"Error sending to websocket for model {m_id}, session {s_id}: {e}")
                    # Potentially mark for disconnection if needed, though disconnect should handle it

manager = ConnectionManager()

@router.websocket("/ws/{model_id}/{session_id}") # Added session_id to path
async def websocket_endpoint(
    websocket: WebSocket,
    model_id: str,
    session_id: str, # Now explicitly part of the path
    service: MCPService = Depends(get_mcp_service),
    db: AsyncSession = Depends(get_session)
):
    await manager.connect(websocket, model_id, session_id)
    try:
        while True:
            data = await websocket.receive_text()
            message_payload = {"model_id": model_id, "content": data} # ID for message can be generated by service

            updated_session = await service.post_message_to_session(
                db_session=db,
                session_id=session_id,
                message_data=message_payload
            )

            if updated_session:
                response_msg = f"Message received & context updated for session {session_id}"
                await manager.send_personal_message(response_msg, websocket)
                # Broadcast to other clients in the same session for this model
                broadcast_content = f"Model {model_id} (session {session_id}) received new data: {data[:50]}..."
                await manager.broadcast_to_session_model(broadcast_content, model_id, session_id, sender=websocket)
            else:
                await manager.send_personal_message(f"Error processing message for session {session_id}", websocket)

    except WebSocketDisconnect:
        manager.disconnect(model_id, session_id)
        # Optionally broadcast that a user left this specific model/session combination
        # await manager.broadcast_to_session_model(f"Client left model {model_id} in session {session_id}", model_id, session_id)
    except Exception as e:
        print(f"WebSocket Error for model {model_id}, session {session_id}: {e}")
        manager.disconnect(model_id, session_id) # Ensure disconnect on any other error


# Old endpoints to be removed or fully refactored:
# @router.get("/context/{session_id}", response_model=Context) # Replaced by get_session_details
# async def get_mcp_context(session_id: str, service: MCPService = Depends(get_mcp_service), db: AsyncSession = Depends(get_session)):
#     session = await service.get_session(db, session_id)
#     if not session or not session.context:
#         raise HTTPException(status_code=404, detail="Context not found for session")
#     return session.context

# @router.post("/context", response_model=Context) # Replaced by update_session_context_data
# async def update_mcp_context(context: Context):
# return await mcp_service.update_context(context)

# @router.get("/messages", response_model=List[Message]) # Needs a new service method
# async def get_mcp_messages(session_id: str | None = None, model_id: str | None = None):
# return await mcp_service.get_messages(session_id=session_id, model_id=model_id) 