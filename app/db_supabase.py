# app/db_supabase.py
import os, uuid, traceback
from typing import Any, Dict, Optional
from supabase import create_client, Client

SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  

_sb: Optional[Client] = None
def sb() -> Client:
    global _sb
    if _sb is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("Faltan SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")
        _sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _sb

def new_request_id() -> str:
    return str(uuid.uuid4())

def log_general(message: str, route: str = None, level: str = "INFO",
                context: Dict[str, Any] | None = None, request_id: str | None = None) -> None:
    try:
        sb().table("logs_general").insert({
            "message": message,
            "route": route,
            "level": level,
            "context": context or {},
            "request_id": request_id,
        }).execute()
    except Exception:
        # Nunca romper la request por fallo de logging
        pass

def log_error(error_type: str, message: str, route: str = None,
             context: Dict[str, Any] | None = None, request_id: str | None = None) -> None:
    try:
        sb().table("logs_error").insert({
            "error_type": error_type,
            "message": message,
            "route": route,
            "context": context or {},
            "request_id": request_id,
            "stacktrace": traceback.format_exc(),
        }).execute()
    except Exception:
        pass

def ping_supabase() -> bool:
    try:
        # consulta muy barata para healthcheck
        sb().table("logs_general").select("id").limit(1).execute()
        return True
    except Exception:
        return False
