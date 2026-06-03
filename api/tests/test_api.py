import asyncio

import httpx

from app.main import app, arxiv_client, discovery_graph, upload_discovery_service, zotero_discovery_service
from app.models import AgentSearchResponse, LiteratureReviewOutlineResponse, Paper, ReviewedPaper
from app.services.arxiv import ArxivSearchResult
from app.services.openai_agents import PaperSummary, ReviewDecision, SearchPlan
from app.services.upload_discovery import UploadDiscoveryRequest
from app.services.zotero_api import ZoteroDiscoveryRequest, ZoteroSaveResult


def build_paper(title: str) -> Paper:
    return Paper(
        id=title.lower().replace(" ", "-"),
        title=title,
        summary="Relevant summary text.",
        published="2024-01-01T00:00:00Z",
        updated="2024-01-01T00:00:00Z",
        authors=["A. Author"],
        categories=["cs.AI"],
        primary_category="cs.AI",
        paper_url="https://arxiv.org/abs/1234.5678",
        pdf_url="https://arxiv.org/pdf/1234.5678.pdf",
    )


def build_reviewed_paper(title: str) -> ReviewedPaper:
    return ReviewedPaper(
        **build_paper(title).model_dump(),
        relevance_score=4.5,
        rationale="title matches: graph, neural",
        is_fit=True,
        fit_score=4.5,
        reviewer_notes="accepted at score 4.500 against threshold 2.000; title matches: graph, neural",
        key_points_summary=[
            "Summarizes the uploaded paper.",
            "Highlights the main method.",
            "Notes the evidence reported by the authors.",
            "Connects the paper to the requested topic.",
            "Suitable for spreadsheet export.",
        ],
    )


def test_healthcheck() -> None:
    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.get("/health")

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_serves_web_app() -> None:
    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.get("/")

    response = asyncio.run(run())
    assert response.status_code == 200
    assert "Search papers through a five-agent research desk." in response.text
    assert "Summary Agent" in response.text
    assert "Sanity Agent" in response.text
    assert "Outline Agent" in response.text


def test_discover_papers_ranks_results(monkeypatch) -> None:
    async def fake_search(*args, **kwargs) -> ArxivSearchResult:
        return ArxivSearchResult(
            total_results=2,
            papers=[
                build_paper("Graph Neural Networks for Molecules"),
                build_paper("Vision Transformers"),
            ],
        )

    monkeypatch.setattr(arxiv_client, "search", fake_search)
    async def fake_fetch_text(*args, **kwargs) -> str:
        return (
            "Graph neural networks are used for molecule representations. "
            "The method improves decision quality in structured chemistry tasks. "
            "Experiments show strong performance across the reported benchmarks. "
            "The paper discusses practical drug discovery implications and limitations."
        )
    monkeypatch.setattr(discovery_graph.paper_content_service, "fetch_text", fake_fetch_text)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/papers/discover",
                json={
                    "topic": "graph neural networks for drug discovery",
                    "max_results": 2,
                    "categories": ["cs.LG"],
                },
            )

    response = asyncio.run(run())

    assert response.status_code == 200
    data = response.json()
    assert data["query_used"] == 'all:"graph neural networks for drug discovery" AND cat:cs.LG'
    assert data["total_candidates"] == 2
    assert data["accepted_papers"] == 1
    assert data["papers"][0]["title"] == "Graph Neural Networks for Molecules"
    assert data["papers"][0]["is_fit"] is True
    assert isinstance(data["papers"][0]["key_points_summary"], list)
    assert len(data["papers"][0]["key_points_summary"]) >= 5
    assert "search_agent" in " ".join(data["workflow_steps"])
    assert "review_agent" in " ".join(data["workflow_steps"])
    assert "summary_agent" in " ".join(data["workflow_steps"])
    assert "sanity_agent" in " ".join(data["workflow_steps"])
    assert data["sanity_report"][0].startswith("Sanity status:")


def test_discover_papers_can_include_rejected(monkeypatch) -> None:
    async def fake_search(*args, **kwargs) -> ArxivSearchResult:
        return ArxivSearchResult(
            total_results=2,
            papers=[
                build_paper("Graph Neural Networks for Molecules"),
                build_paper("Vision Transformers"),
            ],
        )

    monkeypatch.setattr(arxiv_client, "search", fake_search)
    async def fake_fetch_text(*args, **kwargs) -> str:
        return "Planning is modeled with graphs. The architecture improves structured decisions."
    monkeypatch.setattr(discovery_graph.paper_content_service, "fetch_text", fake_fetch_text)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/papers/discover",
                json={
                    "topic": "graph neural networks for drug discovery",
                    "max_results": 2,
                    "categories": ["cs.LG"],
                    "include_rejected": True,
                },
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    data = response.json()
    assert len(data["papers"]) == 2
    assert data["papers"][1]["is_fit"] is False
    assert data["papers"][1]["key_points_summary"] is None


def test_discover_papers_can_save_accepted_results_to_zotero(monkeypatch) -> None:
    async def fake_search(*args, **kwargs) -> ArxivSearchResult:
        return ArxivSearchResult(
            total_results=2,
            papers=[
                build_paper("Graph Neural Networks for Molecules"),
                build_paper("Vision Transformers"),
            ],
        )

    async def fake_fetch_text(*args, **kwargs) -> str:
        return (
            "Graph neural networks are used for molecule representations. "
            "The method improves decision quality in structured chemistry tasks."
        )

    async def fake_save_search_results(*, api_key: str, papers, username: str | None = None, topic: str | None = None) -> ZoteroSaveResult:
        assert api_key == "write-key"
        assert username == "0sauerb"
        assert topic == "graph neural networks for drug discovery"
        assert len([paper for paper in papers if paper.is_fit]) == 1
        return ZoteroSaveResult(
            saved_items=1,
            failed_items=0,
            message="Saved 1 accepted paper(s) to Zotero library 0sauerb.",
        )

    monkeypatch.setattr(arxiv_client, "search", fake_search)
    monkeypatch.setattr(discovery_graph.paper_content_service, "fetch_text", fake_fetch_text)
    monkeypatch.setattr(zotero_discovery_service, "save_search_results", fake_save_search_results)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/papers/discover",
                json={
                    "topic": "graph neural networks for drug discovery",
                    "max_results": 2,
                    "categories": ["cs.LG"],
                    "save_to_zotero": True,
                    "zotero_api_key": "write-key",
                    "zotero_username": "0sauerb",
                },
            )

    response = asyncio.run(run())

    assert response.status_code == 200
    data = response.json()
    assert data["zotero_saved_items"] == 1
    assert "zotero_sync" in " ".join(data["workflow_steps"])


def test_discover_papers_requires_zotero_key_when_save_enabled() -> None:
    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/papers/discover",
                json={
                    "topic": "graph neural networks for drug discovery",
                    "save_to_zotero": True,
                },
            )

    response = asyncio.run(run())
    assert response.status_code == 400
    assert response.json()["detail"] == "Provide a Zotero API key to save accepted papers."


def test_discover_papers_uses_openai_agents_when_available(monkeypatch) -> None:
    async def fake_search(*args, **kwargs) -> ArxivSearchResult:
        return ArxivSearchResult(
            total_results=1,
            papers=[build_paper("Planning with Graph Neural Networks")],
        )

    async def fake_plan_search(request, fallback_query) -> SearchPlan:
        return SearchPlan(
            query='all:"planning with graph neural networks" AND cat:cs.AI',
            notes="Expanded the topic into a tighter arXiv query.",
        )

    async def fake_review_paper(**kwargs) -> ReviewDecision:
        return ReviewDecision(
            is_fit=True,
            fit_score=8.7,
            reviewer_notes="The abstract directly addresses the requested topic.",
        )

    async def fake_summarize_paper(**kwargs) -> PaperSummary:
        return PaperSummary(
            key_points_summary=[
                "Frames planning as a graph reasoning problem.",
                "Uses graph neural networks to represent structured state transitions.",
                "Improves decision quality on the reported tasks.",
                "Targets structured planning environments.",
                "Matches the requested topic closely.",
            ],
        )

    monkeypatch.setattr(arxiv_client, "search", fake_search)
    async def fake_fetch_text(*args, **kwargs) -> str:
        return (
            "Planning is modeled with graphs. The architecture improves structured decisions. "
            "The paper reports gains on representative planning benchmarks."
        )
    monkeypatch.setattr(discovery_graph.paper_content_service, "fetch_text", fake_fetch_text)
    monkeypatch.setattr(discovery_graph.agent_service, "is_enabled", lambda: True)
    monkeypatch.setattr(discovery_graph.agent_service, "summarizer_enabled", lambda: True)
    monkeypatch.setattr(discovery_graph.agent_service, "plan_search", fake_plan_search)
    monkeypatch.setattr(discovery_graph.agent_service, "review_paper", fake_review_paper)
    monkeypatch.setattr(discovery_graph.agent_service, "summarize_paper", fake_summarize_paper)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/papers/discover",
                json={
                    "topic": "planning with graph neural networks",
                    "max_results": 1,
                    "categories": ["cs.AI"],
                },
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    data = response.json()
    assert data["query_used"] == 'all:"planning with graph neural networks" AND cat:cs.AI'
    assert data["papers"][0]["fit_score"] == 8.7
    assert data["papers"][0]["key_points_summary"][0].startswith("Frames planning")
    assert "LangChain/OpenAI planner" in " ".join(data["workflow_steps"])
    assert "LangChain/OpenAI reviewer" in " ".join(data["workflow_steps"])
    assert "LangChain/OpenAI summarizer" in " ".join(data["workflow_steps"])
    assert "sanity_agent" in " ".join(data["workflow_steps"])


def test_upload_papers_processes_pdf_batch(monkeypatch) -> None:
    async def fake_run(request: UploadDiscoveryRequest, files) -> AgentSearchResponse:
        assert request.topic == "graph neural networks for drug discovery"
        assert request.min_fit_score == 2.0
        assert request.include_rejected is False
        assert len(files) == 2
        return AgentSearchResponse(
            topic=request.topic,
            query_used="uploaded_batch_analyze",
            total_candidates=2,
            accepted_papers=1,
            workflow_steps=[
                "upload_agent processed 2 uploaded references",
                "review_agent used deterministic reviewer for 2 uploaded papers",
                "summary_agent used deterministic summarizer for 1 accepted uploaded papers",
            ],
            papers=[build_reviewed_paper("Uploaded Molecule GNN Paper")],
        )

    monkeypatch.setattr(upload_discovery_service, "run", fake_run)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/papers/upload",
                data={
                    "topic": "graph neural networks for drug discovery",
                    "min_fit_score": "2.0",
                    "include_rejected": "false",
                },
                files=[
                    ("files", ("paper-1.pdf", b"%PDF-1.4 fake 1", "application/pdf")),
                    ("files", ("paper-2.pdf", b"%PDF-1.4 fake 2", "application/pdf")),
                ],
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    data = response.json()
    assert data["query_used"] == "uploaded_batch_analyze"
    assert data["total_candidates"] == 2
    assert data["accepted_papers"] == 1
    assert data["papers"][0]["title"] == "Uploaded Molecule GNN Paper"


def test_upload_papers_requires_pdf_files() -> None:
    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/papers/upload",
                data={
                    "topic": "graph neural networks for drug discovery",
                    "min_fit_score": "2.0",
                    "include_rejected": "false",
                },
                files=[
                    ("files", ("notes.txt", b"not a pdf", "text/plain")),
                ],
            )

    response = asyncio.run(run())
    assert response.status_code == 400
    assert response.json()["detail"] == "Upload at least one PDF or Zotero RDF file."


def test_upload_papers_for_organization(monkeypatch) -> None:
    async def fake_run(request: UploadDiscoveryRequest, files) -> AgentSearchResponse:
        assert request.topic is None
        assert request.score_against_topic is False
        assert request.include_rejected is True
        assert len(files) == 2
        return AgentSearchResponse(
            topic="",
            query_used="uploaded_batch_organize",
            total_candidates=2,
            accepted_papers=2,
            workflow_steps=[
                "upload_agent processed 2 uploaded references",
                "review_agent skipped topic scoring and accepted 2 uploaded papers for organization",
                "summary_agent used deterministic summarizer for 2 accepted uploaded papers",
            ],
            papers=[
                build_reviewed_paper("Uploaded Paper One"),
                build_reviewed_paper("Uploaded Paper Two"),
            ],
        )

    monkeypatch.setattr(upload_discovery_service, "run", fake_run)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/papers/upload/organize",
                files=[
                    ("files", ("paper-1.pdf", b"%PDF-1.4 fake 1", "application/pdf")),
                    ("files", ("paper-2.pdf", b"%PDF-1.4 fake 2", "application/pdf")),
                ],
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    data = response.json()
    assert data["query_used"] == "uploaded_batch_organize"
    assert data["accepted_papers"] == 2
    assert len(data["papers"]) == 2


def test_upload_papers_accepts_rdf(monkeypatch) -> None:
    async def fake_run(request: UploadDiscoveryRequest, files) -> AgentSearchResponse:
        assert request.topic == "knowledge graphs"
        assert len(files) == 1
        assert files[0].filename == "library.rdf"
        return AgentSearchResponse(
            topic=request.topic,
            query_used="uploaded_batch_analyze",
            total_candidates=1,
            accepted_papers=1,
            workflow_steps=["upload_agent processed 1 uploaded references"],
            papers=[build_reviewed_paper("Imported RDF Entry")],
        )

    monkeypatch.setattr(upload_discovery_service, "run", fake_run)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/papers/upload",
                data={
                    "topic": "knowledge graphs",
                    "min_fit_score": "2.0",
                    "include_rejected": "false",
                },
                files=[
                    ("files", ("library.rdf", b"<rdf:RDF></rdf:RDF>", "application/rdf+xml")),
                ],
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    data = response.json()
    assert data["papers"][0]["title"] == "Imported RDF Entry"


def test_discover_zotero_papers(monkeypatch) -> None:
    async def fake_run(request: ZoteroDiscoveryRequest) -> AgentSearchResponse:
        assert request.topic == "knowledge graphs"
        assert request.username == "0sauerb"
        assert request.api_key == "secret-key"
        assert request.max_items == 25
        return AgentSearchResponse(
            topic=request.topic,
            query_used="zotero_user_0sauerb",
            total_candidates=2,
            accepted_papers=1,
            workflow_steps=[
                "upload_agent: read Zotero personal library 0sauerb and extract text candidates",
                "review_agent used deterministic reviewer for 2 uploaded papers",
                "summary_agent used deterministic summarizer for 1 accepted uploaded papers",
            ],
            papers=[build_reviewed_paper("Zotero Imported Paper")],
        )

    monkeypatch.setattr(zotero_discovery_service, "run", fake_run)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/papers/zotero",
                data={
                    "topic": "knowledge graphs",
                    "username": "0sauerb",
                    "api_key": "secret-key",
                    "min_fit_score": "2.0",
                    "include_rejected": "false",
                    "max_items": "25",
                },
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    data = response.json()
    assert data["query_used"] == "zotero_user_0sauerb"
    assert data["accepted_papers"] == 1
    assert data["papers"][0]["title"] == "Zotero Imported Paper"


def test_build_zotero_literature_outline(monkeypatch) -> None:
    async def fake_run(request: ZoteroDiscoveryRequest) -> AgentSearchResponse:
        return AgentSearchResponse(
            topic=request.topic,
            query_used="zotero_user_0sauerb",
            total_candidates=2,
            accepted_papers=1,
            workflow_steps=[
                "upload_agent: read Zotero personal library 0sauerb and extract text candidates",
                "review_agent used deterministic reviewer for 2 uploaded papers",
                "summary_agent used deterministic summarizer for 1 accepted uploaded papers",
                "sanity_agent completed passed audit for 2 reviewed papers",
            ],
            sanity_report=["Sanity status: passed. 0 warning(s) across query, review, and summary checks."],
            papers=[build_reviewed_paper("Zotero Imported Paper")],
        )

    monkeypatch.setattr(zotero_discovery_service, "run", fake_run)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/papers/zotero/outline",
                json={
                    "topic": "knowledge graphs",
                    "username": "0sauerb",
                    "api_key": "secret-key",
                    "max_items": 25,
                    "min_fit_score": 2.0,
                },
            )

    response = asyncio.run(run())
    assert response.status_code == 200
    data = response.json()
    assert data["outline_title"].startswith("Literature Review Outline:")
    assert len(data["sections"]) >= 2
    assert len(data["bibliography"]) == 1
    assert "outline_agent" in " ".join(data["workflow_steps"])


def test_zotero_job_reports_progress(monkeypatch) -> None:
    async def fake_run(request: ZoteroDiscoveryRequest, progress_callback=None) -> AgentSearchResponse:
        if progress_callback is not None:
            progress_callback(25, "Fetched 10 Zotero items")
            progress_callback(85, "Summarizing accepted references")
        return AgentSearchResponse(
            topic=request.topic,
            query_used="zotero_user_0sauerb",
            total_candidates=2,
            accepted_papers=1,
            workflow_steps=["summary_agent used deterministic summarizer for 1 accepted uploaded papers"],
            papers=[build_reviewed_paper("Zotero Imported Paper")],
        )

    monkeypatch.setattr(zotero_discovery_service, "run", fake_run)

    async def run() -> tuple[httpx.Response, httpx.Response]:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            create_response = await client.post(
                "/papers/zotero/jobs",
                data={
                    "topic": "knowledge graphs",
                    "username": "0sauerb",
                    "api_key": "secret-key",
                    "min_fit_score": "2.0",
                    "include_rejected": "false",
                    "max_items": "25",
                },
            )
            job_id = create_response.json()["job_id"]
            for _ in range(20):
                status_response = await client.get(f"/papers/zotero/jobs/{job_id}")
                if status_response.json()["status"] == "completed":
                    return create_response, status_response
                await asyncio.sleep(0)
            return create_response, status_response

    create_response, status_response = asyncio.run(run())
    assert create_response.status_code == 200
    status_data = status_response.json()
    assert status_data["status"] == "completed"
    assert status_data["progress"] == 100
    assert status_data["result"]["papers"][0]["title"] == "Zotero Imported Paper"
