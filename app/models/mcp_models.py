from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField

# MCP Message Models
class Message(BaseModel):
    id: str # Consider making this optional or default_factory=uuid.uuid4 if it's generated
    model_id: str
    content: Any # Can be str, dict, etc. depending on the model
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Context(BaseModel):
    session_id: str
    messages: List[Message] = Field(default_factory=list)
    shared_memory: Dict[str, Any] = Field(default_factory=dict)
    models: List[str] = Field(default_factory=list) # List of active model_ids in this context/session

# MCP Request/Response Models for interaction with specific models
class ModelRequest(BaseModel):
    model_id: str
    message: Any # The actual input for the model (e.g. string for LLM, image data for vision)
    context: Optional[Context] = None # Full context can be passed if needed
    parameters: Dict[str, Any] = Field(default_factory=dict) # Model-specific parameters

class ModelResponse(BaseModel):
    model_id: str
    response: Any # The actual output from the model
    context_update: Optional[Dict[str, Any]] = None # Partial update to be merged into Context.shared_memory or messages
    metadata: Dict[str, Any] = Field(default_factory=dict)

# Model Registry Information
class ModelInfo(BaseModel):
    id: str # Unique model identifier
    name: str
    type: str  # e.g., "llm", "vision", "audio", "tool", etc.
    endpoint: str # How to reach this model (could be an internal route or external URL)
    capabilities: List[str] = Field(default_factory=list) # What the model can do
    status: str = "active"  # e.g., "active", "inactive", "deprecated"
    input_schema: Optional[Dict[str, Any]] = None # Optional: JSON schema for expected input
    output_schema: Optional[Dict[str, Any]] = None # Optional: JSON schema for output

# Session Management - Stored in DB
class Session(SQLModel, table=True):
    id: Optional[int] = SQLField(default=None, primary_key=True)
    session_id: str = SQLField(unique=True, index=True) # User/client-facing session identifier
    created_at: datetime = SQLField(default_factory=datetime.now)
    updated_at: datetime = SQLField(default_factory=datetime.now) # Should be updated on modification
    
    # Store complex objects as JSON strings in the database
    # The service layer will handle serialization/deserialization
    context_data: str = SQLField(default='{}')  # JSON serialized Context object (excluding session_id itself)
    # active_models: str = SQLField(default='[]') # JSON list of model IDs - This is now part of Context.models
    metadata: str = SQLField(default='{}') # JSON metadata for the session

    # If you need to search/query by aspects of context or metadata frequently,
    # consider promoting some fields to be actual columns instead of keeping them in JSON.
    # For example, last_model_used_id: Optional[str] = SQLField(index=True, default=None)

# Pydantic model for API responses when returning session details (without DB id)
class SessionResponse(BaseModel):
    session_id: str
    created_at: datetime
    updated_at: datetime
    context: Context # Deserialized context
    metadata: Dict[str, Any] # Deserialized metadata 