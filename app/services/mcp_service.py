import json
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from datetime import datetime

from app.models.mcp_models import (
    Context,
    Message,
    ModelInfo,
    Session,
    SessionResponse
)

# Placeholder for in-memory storage for non-session data.
global_mcp_model_registry: Dict[str, ModelInfo] = {} # Using new ModelInfo

class MCPService:
    # --- Session Management ---
    async def get_session(self, db_session: AsyncSession, session_id: str) -> SessionResponse | None:
        """Retrieves a session and its deserialized context and metadata from the database."""
        statement = select(Session).where(Session.session_id == session_id)
        result = await db_session.execute(statement)
        db_session_obj = result.scalar_one_or_none()

        if db_session_obj:
            try:
                # Deserialize context_data and metadata
                context_obj = Context(**json.loads(db_session_obj.context_data))
                # Ensure the session_id in the deserialized context matches the parent session_id
                if context_obj.session_id != db_session_obj.session_id:
                    # This case should ideally not happen if data is saved correctly,
                    # but good to be aware of. Could log a warning.
                    # For now, we align them:
                    context_obj.session_id = db_session_obj.session_id
                
                metadata_obj = json.loads(db_session_obj.metadata)
                
                return SessionResponse(
                    session_id=db_session_obj.session_id,
                    created_at=db_session_obj.created_at,
                    updated_at=db_session_obj.updated_at,
                    context=context_obj,
                    metadata=metadata_obj
                )
            except json.JSONDecodeError as e:
                # Handle error if JSON is malformed, log it, and potentially return None or raise
                print(f"Error decoding JSON for session {session_id}: {e}") # Replace with proper logging
                return None
        return None

    async def create_session(
        self, 
        db_session: AsyncSession, 
        session_id: str, 
        initial_context_data: Optional[Dict[str, Any]] = None, 
        initial_metadata: Optional[Dict[str, Any]] = None
    ) -> SessionResponse:
        """Creates a new session with initial context and metadata, stores it in the database."""
        
        # Check if session already exists
        existing_session = await self.get_session(db_session, session_id)
        if existing_session:
            # Or raise HTTPException(status_code=409, detail="Session already exists")
            # For now, let's return the existing one
            return existing_session

        now = datetime.now()

        # Prepare context object
        if initial_context_data:
            # If full context data is provided (e.g. including messages, shared_memory)
            # It must include session_id matching the main session_id
            if initial_context_data.get("session_id") != session_id:
                initial_context_data["session_id"] = session_id # Ensure alignment
            context_obj = Context(**initial_context_data)
        else:
            # Create a default empty context for the session
            context_obj = Context(session_id=session_id, messages=[], shared_memory={}, models=[])
        
        serialized_context = json.dumps(context_obj.model_dump())

        # Prepare metadata
        final_metadata = initial_metadata if initial_metadata is not None else {}
        serialized_metadata = json.dumps(final_metadata)

        db_session_obj = Session(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            context_data=serialized_context,
            metadata=serialized_metadata
        )
        
        db_session.add(db_session_obj)
        await db_session.commit()
        await db_session.refresh(db_session_obj)

        return SessionResponse(
            session_id=db_session_obj.session_id,
            created_at=db_session_obj.created_at,
            updated_at=db_session_obj.updated_at,
            context=context_obj, # Return the live Pydantic model
            metadata=final_metadata # Return the live dict
        )

    async def update_session_context(
        self, 
        db_session: AsyncSession, 
        session_id: str, 
        context_update_data: Dict[str, Any] # Data to update parts of the context
    ) -> SessionResponse | None:
        """Updates specific parts of a session's context (e.g., messages, shared_memory)."""
        statement = select(Session).where(Session.session_id == session_id)
        result = await db_session.execute(statement)
        db_session_obj = result.scalar_one_or_none()

        if not db_session_obj:
            return None # Or raise HTTPException(status_code=404, detail="Session not found")

        try:
            current_context = Context(**json.loads(db_session_obj.context_data))
            
            # Update messages if provided
            if "messages" in context_update_data and isinstance(context_update_data["messages"], list):
                for msg_data in context_update_data["messages"]:
                    # Assuming msg_data is a dict that can be parsed into a Message model
                    # You might want to add more validation here
                    current_context.messages.append(Message(**msg_data)) 
            
            # Update shared_memory if provided
            if "shared_memory" in context_update_data and isinstance(context_update_data["shared_memory"], dict):
                current_context.shared_memory.update(context_update_data["shared_memory"])

            # Update active models if provided
            if "models" in context_update_data and isinstance(context_update_data["models"], list):
                current_context.models = list(set(current_context.models + context_update_data["models"])) # Example: append unique

            db_session_obj.context_data = json.dumps(current_context.model_dump())
            db_session_obj.updated_at = datetime.now()
            
            await db_session.commit()
            await db_session.refresh(db_session_obj)
            
            current_metadata = json.loads(db_session_obj.metadata)

            return SessionResponse(
                session_id=db_session_obj.session_id,
                created_at=db_session_obj.created_at,
                updated_at=db_session_obj.updated_at,
                context=current_context,
                metadata=current_metadata
            )
        except json.JSONDecodeError as e:
            print(f"Error decoding/encoding JSON for session context update {session_id}: {e}")
            return None
        except Exception as e: # Catch other potential errors during update
            print(f"Error updating session context for {session_id}: {e}")
            await db_session.rollback() # Rollback on error
            return None

    async def update_session_metadata(
        self,
        db_session: AsyncSession,
        session_id: str,
        metadata_update: Dict[str, Any]
    ) -> SessionResponse | None:
        """Updates a session's metadata."""
        statement = select(Session).where(Session.session_id == session_id)
        result = await db_session.execute(statement)
        db_session_obj = result.scalar_one_or_none()

        if not db_session_obj:
            return None

        try:
            current_metadata = json.loads(db_session_obj.metadata)
            current_metadata.update(metadata_update)
            
            db_session_obj.metadata = json.dumps(current_metadata)
            db_session_obj.updated_at = datetime.now()

            await db_session.commit()
            await db_session.refresh(db_session_obj)

            current_context = Context(**json.loads(db_session_obj.context_data))

            return SessionResponse(
                session_id=db_session_obj.session_id,
                created_at=db_session_obj.created_at,
                updated_at=db_session_obj.updated_at,
                context=current_context,
                metadata=current_metadata
            )
        except json.JSONDecodeError as e:
            print(f"Error decoding/encoding JSON for session metadata update {session_id}: {e}")
            return None
        except Exception as e:
            print(f"Error updating session metadata for {session_id}: {e}")
            await db_session.rollback()
            return None
            
    # --- Context Management (now part of Session management) ---
    # async def get_context(self, session_id: str) -> Context | None:
    #     # This logic is now part of get_session
    #     pass

    # async def update_context(self, context: Context) -> Context:
    #     # This logic is now part of update_session_context
    #     pass

    # --- Message Handling (now part of Session's Context) ---
    async def post_message_to_session(
        self, 
        db_session: AsyncSession, 
        session_id: str, 
        message_data: Dict[str, Any] # e.g. {"model_id": "xyz", "content": "hello"}
    ) -> SessionResponse | None:
        """Adds a message to a session's context and persists it."""
        # This is a specific type of context update.
        # We construct the message and then use update_session_context logic (or similar)
        
        # Create the message object
        # You might want to add id generation here, e.g. using uuid
        if 'id' not in message_data:
            import uuid
            message_data['id'] = str(uuid.uuid4())
        
        new_message = Message(**message_data)

        # Fetch current session and context
        statement = select(Session).where(Session.session_id == session_id)
        result = await db_session.execute(statement)
        db_session_obj = result.scalar_one_or_none()

        if not db_session_obj:
            return None # Session not found

        try:
            current_context = Context(**json.loads(db_session_obj.context_data))
            current_context.messages.append(new_message) # Add the new message

            db_session_obj.context_data = json.dumps(current_context.model_dump())
            db_session_obj.updated_at = datetime.now()
            
            await db_session.commit()
            await db_session.refresh(db_session_obj)
            
            current_metadata = json.loads(db_session_obj.metadata)

            return SessionResponse(
                session_id=db_session_obj.session_id,
                created_at=db_session_obj.created_at,
                updated_at=db_session_obj.updated_at,
                context=current_context,
                metadata=current_metadata
            )
        except (json.JSONDecodeError, TypeError) as e: # TypeError for Message(**message_data) if data is bad
            print(f"Error processing message for session {session_id}: {e}")
            await db_session.rollback()
            return None
        except Exception as e:
            print(f"Generic error posting message to session {session_id}: {e}")
            await db_session.rollback()
            return None

    async def get_messages_for_session(
        self, 
        db_session: AsyncSession, 
        session_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Message] | None:
        """Retrieves messages for a specific session with pagination from its context."""
        session_response = await self.get_session(db_session, session_id)

        if session_response and session_response.context and session_response.context.messages:
            # Sort messages by timestamp (default: ascending, older first)
            # For descending (newer first), use reverse=True
            sorted_messages = sorted(session_response.context.messages, key=lambda m: m.timestamp)
            
            # Apply pagination
            paginated_messages = sorted_messages[offset : offset + limit]
            return paginated_messages
        elif session_response: # Session exists but no messages or context
            return []
        return None # Session not found

    # --- Model Registry (using in-memory for now) ---
    async def register_model(self, model_info: ModelInfo) -> ModelInfo:
        """Registers a model in the in-memory registry."""
        if model_info.id in global_mcp_model_registry:
            # Or raise an exception for conflict
            print(f"Warning: Model ID {model_info.id} already exists. Overwriting.")
        global_mcp_model_registry[model_info.id] = model_info
        return model_info

    async def get_model(self, model_id: str) -> ModelInfo | None:
        """Retrieves a model's details from the in-memory registry."""
        return global_mcp_model_registry.get(model_id)

    async def list_models(self) -> List[ModelInfo]:
        """Lists all registered models from the in-memory registry."""
        return list(global_mcp_model_registry.values())

# Initialize a default service instance (optional, depends on how you manage dependencies)
# mcp_service = MCPService() 
# It's often better to inject dependencies (like db_session) rather than using a global service instance directly.
# For FastAPI, you'd typically create an instance and make its methods available via Depends. 