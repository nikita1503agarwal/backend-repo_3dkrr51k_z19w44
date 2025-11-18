"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional

# Web3 Voting Platform Schemas

class Project(BaseModel):
    """
    Web3 Project being voted on
    Collection: "project"
    """
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Short description")
    website: Optional[str] = Field(None, description="Website URL")
    image: Optional[str] = Field(None, description="Logo or image URL")
    chain: Optional[str] = Field(None, description="Primary blockchain e.g., Ethereum, Polygon")


class Vote(BaseModel):
    """
    Vote document
    Collection: "vote"
    """
    project_id: str = Field(..., description="ID of the project voted for")
    address: str = Field(..., description="Voter wallet address (checksum or lowercase)")
    signature: str = Field(..., description="Signature of vote message")
    nonce: str = Field(..., description="Nonce used for signing")


class Nonce(BaseModel):
    """
    One-time nonce per address to prevent replay
    Collection: "nonce"
    """
    address: str = Field(..., description="Wallet address")
    nonce: str = Field(..., description="Random nonce value")
    used: bool = Field(False, description="Whether nonce has been consumed")
