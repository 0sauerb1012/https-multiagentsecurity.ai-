import asyncio
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models import (
    AgentSearchRequest,
    AgentSearchResponse,
    ExportRequest,
    LiteratureReviewOutlineRequest,
    LiteratureReviewOutlineResponse,
    OutlineExportRequest,
    SearchResponse,
)
from app.services.exporters import build_outline_docx, build_ris, build_xlsx, slugify_filename
from app.services.arxiv import ArxivClient
from app.services.graph import PaperDiscoveryGraph
from app.services.job_store import JobStore
from app.services.literature_outline import LiteratureOutlineService, OutlineInput
from app.services.upload_discovery import UploadDiscoveryRequest, UploadDiscoveryService
from app.services.zotero_api import ZoteroDiscoveryRequest, ZoteroDiscoveryService


app = FastAPI(title=settings.app_name, version="0.1.0")
arxiv_client = ArxivClient()
discovery_graph = PaperDiscoveryGraph(arxiv_client)
upload_discovery_service = UploadDiscoveryService()
zotero_discovery_service = ZoteroDiscoveryService()
job_store = JobStore()
literature_outline_service = LiteratureOutlineService()
static_dir = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
async def root() -> HTMLResponse:
    return HTMLResponse((static_dir / "index.html").read_text(encoding="utf-8"))


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> JSONResponse:
    return JSONResponse(status_code=204, content=None)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/papers/search", response_model=SearchResponse)
async def search_papers(
    q: str = Query(..., min_length=3, description="Raw arXiv query string or natural language topic."),
    max_results: int = Query(default=settings.default_max_results, ge=1, le=settings.max_results_limit),
    sort_by: str = Query(default="relevance"),
    sort_order: str = Query(default="descending"),
) -> SearchResponse:
    try:
        result = await arxiv_client.search(
            q,
            max_results=max_results,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"arXiv request failed: {exc}") from exc

    return SearchResponse(
        query=q,
        total_results=result.total_results,
        returned_results=len(result.papers),
        papers=result.papers,
    )


@app.post("/papers/discover", response_model=AgentSearchResponse)
async def discover_papers(payload: AgentSearchRequest) -> AgentSearchResponse:
    try:
        result = await discovery_graph.run(payload)
        if payload.save_to_zotero:
            if not payload.zotero_api_key:
                raise HTTPException(status_code=400, detail="Provide a Zotero API key to save accepted papers.")
            save_result = await zotero_discovery_service.save_search_results(
                api_key=payload.zotero_api_key,
                papers=result.papers,
                username=payload.zotero_username,
                topic=payload.topic,
            )
            result.zotero_saved_items = save_result.saved_items
            result.workflow_steps.append(f"zotero_sync: {save_result.message}")
        return result
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"arXiv request failed: {exc}") from exc


@app.post("/papers/upload", response_model=AgentSearchResponse)
async def upload_papers(
    topic: str = Form(..., min_length=3),
    min_fit_score: float = Form(2.0),
    include_rejected: bool = Form(False),
    files: list[UploadFile] = File(...),
) -> AgentSearchResponse:
    accepted_files = [file for file in files if (file.filename or "").lower().endswith((".pdf", ".rdf"))]
    if not accepted_files:
        raise HTTPException(status_code=400, detail="Upload at least one PDF or Zotero RDF file.")

    try:
        return await upload_discovery_service.run(
            UploadDiscoveryRequest(
                topic=topic,
                min_fit_score=min_fit_score,
                include_rejected=include_rejected,
            ),
            accepted_files,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"Uploaded PDF processing failed: {exc}") from exc


@app.post("/papers/upload/organize", response_model=AgentSearchResponse)
async def upload_papers_for_organization(
    files: list[UploadFile] = File(...),
) -> AgentSearchResponse:
    accepted_files = [file for file in files if (file.filename or "").lower().endswith((".pdf", ".rdf"))]
    if not accepted_files:
        raise HTTPException(status_code=400, detail="Upload at least one PDF or Zotero RDF file.")

    try:
        return await upload_discovery_service.run(
            UploadDiscoveryRequest(
                topic=None,
                min_fit_score=0.0,
                include_rejected=True,
                score_against_topic=False,
            ),
            accepted_files,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"Uploaded PDF processing failed: {exc}") from exc


@app.post("/papers/zotero", response_model=AgentSearchResponse)
async def discover_zotero_papers(
    topic: str = Form(..., min_length=3),
    username: str = Form(..., min_length=1),
    api_key: str = Form(..., min_length=1),
    min_fit_score: float = Form(2.0),
    include_rejected: bool = Form(False),
    max_items: int = Form(100, ge=1, le=500),
    delete_below_score: bool = Form(False),
    delete_duplicates: bool = Form(False),
) -> AgentSearchResponse:
    try:
        return await zotero_discovery_service.run(
            ZoteroDiscoveryRequest(
                topic=topic,
                username=username,
                api_key=api_key,
                min_fit_score=min_fit_score,
                include_rejected=include_rejected,
                max_items=max_items,
                delete_below_score=delete_below_score,
                delete_duplicates=delete_duplicates,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"Zotero request failed: {exc}") from exc


@app.post("/papers/zotero/outline", response_model=LiteratureReviewOutlineResponse)
async def build_zotero_literature_outline(payload: LiteratureReviewOutlineRequest) -> LiteratureReviewOutlineResponse:
    try:
        discovery_result = await zotero_discovery_service.run(
            ZoteroDiscoveryRequest(
                topic=payload.topic,
                username=payload.username,
                api_key=payload.api_key,
                min_fit_score=payload.min_fit_score,
                include_rejected=payload.include_rejected,
                max_items=payload.max_items,
            )
        )
        return literature_outline_service.build_outline(
            OutlineInput(
                topic=payload.topic,
                query_used=f"zotero_outline_{payload.username}",
                total_candidates=discovery_result.total_candidates,
                accepted_papers=discovery_result.accepted_papers,
                workflow_steps=discovery_result.workflow_steps,
                sanity_report=discovery_result.sanity_report,
                papers=discovery_result.papers,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=502, detail=f"Zotero outline request failed: {exc}") from exc


@app.post("/papers/zotero/jobs")
async def create_zotero_job(
    topic: str = Form(..., min_length=3),
    username: str = Form(..., min_length=1),
    api_key: str = Form(..., min_length=1),
    min_fit_score: float = Form(2.0),
    include_rejected: bool = Form(False),
    max_items: int = Form(100, ge=1, le=500),
    delete_below_score: bool = Form(False),
    delete_duplicates: bool = Form(False),
) -> dict[str, str]:
    record = job_store.create("Queued Zotero job")
    request = ZoteroDiscoveryRequest(
        topic=topic,
        username=username,
        api_key=api_key,
        min_fit_score=min_fit_score,
        include_rejected=include_rejected,
        max_items=max_items,
        delete_below_score=delete_below_score,
        delete_duplicates=delete_duplicates,
    )

    async def runner() -> None:
        try:
            result = await zotero_discovery_service.run(
                request,
                progress_callback=lambda progress, message: job_store.update(record.id, progress=progress, message=message),
            )
            job_store.complete(record.id, result)
        except Exception as exc:  # pragma: no cover
            job_store.fail(record.id, f"Zotero request failed: {exc}")

    task = asyncio.create_task(runner())
    job_store.set_task(record.id, task)
    return {"job_id": record.id}


@app.get("/papers/zotero/jobs/{job_id}")
async def get_zotero_job(job_id: str) -> dict:
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown Zotero job.")

    return {
        "job_id": record.id,
        "status": record.status,
        "progress": record.progress,
        "message": record.message,
        "error": record.error,
        "result": record.result.model_dump() if record.result is not None else None,
    }


@app.post("/exports/ris")
async def export_ris(payload: ExportRequest) -> Response:
    ris_text = build_ris(payload.papers)
    filename = f"{slugify_filename(payload.papers[0].title)}-papers.ris"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=ris_text, media_type="application/x-research-info-systems", headers=headers)


@app.post("/exports/xlsx")
async def export_xlsx(payload: ExportRequest) -> StreamingResponse:
    xlsx_bytes = build_xlsx(payload.papers)
    filename = f"{slugify_filename(payload.papers[0].title)}-papers.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([xlsx_bytes]), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)


@app.post("/exports/literature-review/docx")
async def export_literature_review_docx(payload: OutlineExportRequest) -> StreamingResponse:
    docx_bytes = build_outline_docx(payload.outline)
    filename = f"{slugify_filename(payload.outline.outline_title)}.docx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        iter([docx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )
