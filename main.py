import os
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import Project as ProjectSchema, Vote as VoteSchema, Nonce as NonceSchema

# Optional: verify Ethereum signatures
from eth_account.messages import encode_defunct
from eth_account import Account

app = FastAPI(title="Web3 Voting API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    website: Optional[str] = None
    image: Optional[str] = None
    chain: Optional[str] = None


class VoteCreate(BaseModel):
    project_id: str
    address: str
    signature: str
    nonce: str


@app.get("/")
def root():
    return {"message": "Web3 Voting API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:60]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:60]}"
    return response


# Utility helpers

def collection_name(model_cls) -> str:
    return model_cls.__name__.lower()


def generate_nonce() -> str:
    return secrets.token_hex(16)


# Nonce endpoints
@app.post("/api/nonce")
def create_nonce(address: str):
    if not address:
        raise HTTPException(status_code=400, detail="Address required")
    addr = address.lower()

    # Mark previous nonces as used for this address
    db[collection_name(NonceSchema)].update_many({"address": addr, "used": False}, {"$set": {"used": True, "updated_at": datetime.now(timezone.utc)}})

    nonce = generate_nonce()
    create_document(collection_name(NonceSchema), {"address": addr, "nonce": nonce, "used": False})
    return {"address": addr, "nonce": nonce}


@app.post("/api/projects")
def create_project(payload: ProjectCreate):
    data = ProjectSchema(**payload.model_dump())
    project_id = create_document(collection_name(ProjectSchema), data)
    return {"id": project_id, "message": "Project created"}


@app.get("/api/projects")
def list_projects() -> List[dict]:
    projects = get_documents(collection_name(ProjectSchema))
    for p in projects:
        p["id"] = str(p.pop("_id"))
    # Aggregate votes count per project
    votes = get_documents(collection_name(VoteSchema))
    counts = {}
    for v in votes:
        pid = v.get("project_id")
        counts[pid] = counts.get(pid, 0) + 1
    for p in projects:
        p["votes"] = counts.get(p["id"], 0)
    return projects


@app.post("/api/vote")
def cast_vote(payload: VoteCreate):
    # Verify nonce exists and not used
    addr = payload.address.lower()
    nonce_doc = db[collection_name(NonceSchema)].find_one({"address": addr, "nonce": payload.nonce, "used": False})
    if not nonce_doc:
        raise HTTPException(status_code=400, detail="Invalid or used nonce")

    # Verify signature recovers to the address (EIP-191 personal_sign style)
    try:
        message = encode_defunct(text=f"VOTE:{payload.project_id}:{payload.nonce}")
        recovered = Account.recover_message(message, signature=payload.signature)
        if recovered.lower() != addr:
            raise HTTPException(status_code=401, detail="Signature verification failed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid signature: {str(e)[:60]}")

    # Upsert a vote: one vote per address per project
    existing = db[collection_name(VoteSchema)].find_one({"project_id": payload.project_id, "address": addr})
    if existing:
        # If already voted for this project, just acknowledge
        return {"status": "ok", "message": "Vote already recorded"}

    create_document(collection_name(VoteSchema), {
        "project_id": payload.project_id,
        "address": addr,
        "signature": payload.signature,
        "nonce": payload.nonce,
    })

    # Mark nonce as used
    db[collection_name(NonceSchema)].update_one({"_id": nonce_doc.get("_id")}, {"$set": {"used": True, "updated_at": datetime.now(timezone.utc)}})

    return {"status": "ok", "message": "Vote recorded"}


@app.get("/api/projects/{project_id}/votes")
def project_votes(project_id: str):
    votes = get_documents(collection_name(VoteSchema), {"project_id": project_id})
    return {"project_id": project_id, "votes": len(votes)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
