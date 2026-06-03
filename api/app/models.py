from typing import Literal

from pydantic import BaseModel, Field


SortBy = Literal["relevance", "lastUpdatedDate", "submittedDate"]
SortOrder = Literal["ascending", "descending"]


class Paper(BaseModel):
    id: str
    title: str
    summary: str
    published: str
    updated: str
    authors: list[str]
    categories: list[str]
    hub_categories: list[str] = Field(default_factory=list)
    primary_category: str | None = None
    canonical_id: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    venue: str | None = None
    source_name: str = "Unknown source"
    source_type: str = "unknown"
    merged_from_sources: list[str] = Field(default_factory=list)
    source_records: list["SourceRecord"] = Field(default_factory=list)
    paper_url: str
    pdf_url: str | None = None


class SourceRecord(BaseModel):
    source_name: str
    source_type: str
    source_id: str
    record_url: str
    title: str
    summary: str
    authors: list[str] = Field(default_factory=list)
    published: str = ""
    doi: str | None = None
    arxiv_id: str | None = None
    venue: str | None = None


class SearchResponse(BaseModel):
    query: str
    total_results: int
    returned_results: int
    papers: list[Paper]


class AgentSearchRequest(BaseModel):
    topic: str = Field(..., min_length=3, description="Natural language research topic.")
    max_results: int = Field(default=10, ge=1, le=25)
    sort_by: SortBy = "relevance"
    sort_order: SortOrder = "descending"
    categories: list[str] = Field(default_factory=list)
    include_terms: list[str] = Field(default_factory=list)
    exclude_terms: list[str] = Field(default_factory=list)
    min_fit_score: float = Field(default=2.0, ge=0.0, description="Minimum score required to mark a paper as a fit.")
    include_rejected: bool = Field(
        default=False,
        description="Include papers rejected by the reviewer agent in the response.",
    )
    save_to_zotero: bool = Field(
        default=False,
        description="When true, save accepted papers to the user's Zotero library.",
    )
    zotero_api_key: str | None = Field(default=None, description="Zotero API key used to write accepted papers.")
    zotero_username: str | None = Field(default=None, description="Optional Zotero username used only for workflow labeling.")


class RankedPaper(Paper):
    relevance_score: float
    rationale: str


class ReviewedPaper(RankedPaper):
    is_fit: bool
    fit_score: float
    reviewer_notes: str
    classification_confidence: float | None = None
    classification_notes: str | None = None
    key_points_summary: list[str] | None = None


class AgentSearchResponse(BaseModel):
    topic: str
    query_used: str
    total_candidates: int
    accepted_papers: int
    zotero_saved_items: int = 0
    zotero_deleted_items: int = 0
    workflow_steps: list[str]
    sanity_report: list[str] = Field(default_factory=list)
    papers: list[ReviewedPaper]


class ExportRequest(BaseModel):
    papers: list[ReviewedPaper] = Field(..., min_length=1, description="Selected papers to export.")


class LiteratureReviewOutlineRequest(BaseModel):
    topic: str = Field(..., min_length=3, description="Literature review topic.")
    username: str = Field(..., min_length=1, description="Zotero username.")
    api_key: str = Field(..., min_length=1, description="Zotero API key.")
    max_items: int = Field(default=100, ge=1, le=500)
    min_fit_score: float = Field(default=2.0, ge=0.0)
    include_rejected: bool = Field(default=False)


class LiteratureOutlineSection(BaseModel):
    title: str
    overview: str
    bullet_points: list[str] = Field(default_factory=list)


class LiteratureReviewOutlineResponse(BaseModel):
    topic: str
    outline_title: str
    query_used: str
    total_candidates: int
    accepted_papers: int
    workflow_steps: list[str]
    sanity_report: list[str] = Field(default_factory=list)
    sections: list[LiteratureOutlineSection]
    bibliography: list[str] = Field(default_factory=list)


class OutlineExportRequest(BaseModel):
    outline: LiteratureReviewOutlineResponse
