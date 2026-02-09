"""
Pydantic models for agentic discovery pipeline.

These models define the structure of data discovered by agents using
Gemini Search Grounding, including citations and source metadata.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class DiscoveryMethod(str, Enum):
    """How the source was discovered."""

    KNOWN = "known"  # Direct URL check (e.g., Charity Navigator, ProPublica)
    SEARCH = "search"  # Discovered via Gemini Search Grounding


class AgentType(str, Enum):
    """Types of discovery agents in the pipeline."""

    AUTHORITATIVE = "authoritative"  # Form 990, IRS status
    RATING = "rating"  # CN, BBB, Candid ratings
    PROFILE = "profile"  # Mission, programs, leadership
    EVIDENCE = "evidence"  # Evaluations, RCTs, studies
    REPUTATION = "reputation"  # News, awards, controversies
    PRIMARY = "primary"  # Charity's own website


class SourceType(str, Enum):
    """Type of source for citations."""

    FORM_990 = "form990"
    RATING = "rating"
    EVALUATION = "evaluation"
    NEWS = "news"
    WEBSITE = "website"
    SEARCH = "search"
    ACADEMIC = "academic"
    GOVERNMENT = "government"


class GroundingChunk(BaseModel):
    """A web source used for grounding from Gemini Search."""

    uri: Optional[str] = Field(None, description="Full URL of the web page")
    title: Optional[str] = Field(None, description="Title of the web page")
    domain: Optional[str] = Field(None, description="Domain of the web source")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "uri": "https://www.charitynavigator.org/ein/953782961",
                "title": "Islamic Relief USA - Charity Navigator",
                "domain": "charitynavigator.org",
            }
        }
    )


class GroundingSupport(BaseModel):
    """Support information linking claims to grounding chunks."""

    segment_text: Optional[str] = Field(None, description="Text segment being supported")
    start_index: Optional[int] = Field(None, description="Start index in response")
    end_index: Optional[int] = Field(None, description="End index in response")
    confidence_scores: list[float] = Field(default_factory=list, description="Confidence scores")
    grounding_chunk_indices: list[int] = Field(
        default_factory=list, description="Indices of supporting grounding chunks"
    )


class GroundingMetadata(BaseModel):
    """
    Parsed grounding metadata from Gemini Search response.

    This captures the full context of how Gemini grounded its response
    in web search results.
    """

    web_search_queries: list[str] = Field(
        default_factory=list, description="Search queries Gemini performed"
    )
    grounding_chunks: list[GroundingChunk] = Field(
        default_factory=list, description="Web sources used for grounding"
    )
    grounding_supports: list[GroundingSupport] = Field(
        default_factory=list, description="Links between claims and sources"
    )
    retrieval_queries: list[str] = Field(
        default_factory=list, description="Queries used in retrieval"
    )

    @property
    def source_urls(self) -> list[str]:
        """Get all unique source URLs from grounding chunks."""
        return [chunk.uri for chunk in self.grounding_chunks if chunk.uri]

    @property
    def source_domains(self) -> list[str]:
        """Get all unique domains from grounding chunks."""
        return list({chunk.domain for chunk in self.grounding_chunks if chunk.domain})

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "web_search_queries": ["Islamic Relief USA charity rating"],
                "grounding_chunks": [
                    {
                        "uri": "https://www.charitynavigator.org/ein/953782961",
                        "title": "Islamic Relief USA",
                        "domain": "charitynavigator.org",
                    }
                ],
            }
        }
    )


class Citation(BaseModel):
    """
    A citation linking a claim to its source.

    Used to provide verifiable references in rich narratives.
    """

    id: str = Field(..., description="Citation identifier (e.g., 'cite_1')")
    claim: str = Field(..., description="The specific claim being cited")
    source_name: str = Field(..., description="Human-readable source name")
    source_url: Optional[str] = Field(None, description="Clickable URL to source")
    source_type: SourceType = Field(..., description="Type of source")
    quote: Optional[str] = Field(None, description="Exact text from source if available")
    access_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When source was accessed")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score (0-1)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "cite_1",
                "claim": "Islamic Relief USA has a 4-star rating",
                "source_name": "Charity Navigator",
                "source_url": "https://www.charitynavigator.org/ein/953782961",
                "source_type": "rating",
                "confidence": 0.95,
            }
        }
    )


class DiscoveredSource(BaseModel):
    """
    A source discovered by an agent during crawling.

    This is the primary record stored in the agent_discoveries table.
    """

    charity_ein: str = Field(..., description="EIN of the charity this discovery relates to")
    agent_type: AgentType = Field(..., description="Which agent discovered this")
    source_name: str = Field(..., description="Human-readable source name")
    source_url: Optional[str] = Field(None, description="URL of the source")
    discovery_method: DiscoveryMethod = Field(..., description="How the source was found")
    search_query: Optional[str] = Field(None, description="Query used if discovered via search")

    # Content
    raw_content: Optional[str] = Field(None, description="Raw text content extracted")
    parsed_data: Optional[dict[str, Any]] = Field(None, description="Structured data extracted")

    # Grounding metadata (for search discoveries)
    grounding_metadata: Optional[GroundingMetadata] = Field(
        None, description="Full grounding metadata from Gemini"
    )

    # Quality signals
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in this discovery")
    relevance_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="How relevant to the charity"
    )

    # Timestamps
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When discovered")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "charity_ein": "95-3782961",
                "agent_type": "rating",
                "source_name": "Charity Navigator",
                "source_url": "https://www.charitynavigator.org/ein/953782961",
                "discovery_method": "known",
                "confidence": 1.0,
            }
        }
    )


class AgentDiscoveryBundle(BaseModel):
    """
    Collection of all discoveries from a single agent run.

    Used to batch discoveries before storing.
    """

    charity_ein: str = Field(..., description="EIN of the charity")
    agent_type: AgentType = Field(..., description="Agent that ran")
    discoveries: list[DiscoveredSource] = Field(default_factory=list, description="All discoveries")
    search_queries_used: int = Field(0, description="Number of search queries consumed")
    total_cost_usd: float = Field(0.0, description="Total cost of agent run")
    run_duration_seconds: float = Field(0.0, description="How long the agent ran")
    run_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="When agent ran")

    @property
    def discovery_count(self) -> int:
        """Number of sources discovered."""
        return len(self.discoveries)

    @property
    def search_discoveries(self) -> list[DiscoveredSource]:
        """Discoveries made via search (not known sources)."""
        return [d for d in self.discoveries if d.discovery_method == DiscoveryMethod.SEARCH]
