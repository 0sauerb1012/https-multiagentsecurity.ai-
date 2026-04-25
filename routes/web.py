from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from services.research_hub import ResearchHubService
from services.export_utils import build_ris, slugify_filename
from services.topic_catalog import BROAD_AGENTIC_AI_TOPICS


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
hub_service = ResearchHubService()

ACTIVE_SOURCE_FEEDS = ["arXiv", "OpenAlex", "Crossref", "Semantic Scholar", "DBLP"]

SITE_NAV = [
    {"label": "Home", "href": "/"},
    {
        "label": "Research",
        "href": "/research-feed",
        "children": [
            {"label": "Research Feed", "href": "/research-feed"},
            {"label": "Research Library", "href": "/research-library"},
            {"label": "Research Trends", "href": "/research-gaps"},
        ],
    },
    {
        "label": "Signals",
        "href": "/industry-intel",
        "children": [
            {"label": "Blog", "href": "/blog"},
        ],
    },
    {
        "label": "About",
        "href": "/about",
    },
]

HOME_FEATURES = [
    {
        "title": "Research feed",
        "href": "/research-feed",
        "description": "Review recently collected multi-agent security papers across scholarly sources, with summaries and source metadata.",
        "eyebrow": "Current literature",
    },
    {
        "title": "Research library",
        "href": "/research-library",
        "description": "Browse the stored literature by topic area using the current site taxonomy.",
        "eyebrow": "Categorized literature",
    },
    {
        "title": "Research trends",
        "href": "/research-gaps",
        "description": "Inspect category momentum, concentration, and emerging areas in the stored corpus.",
        "eyebrow": "Trend analysis",
    },
    {
        "title": "Concepts",
        "href": "/concepts",
        "description": "Read short concept notes on topics such as prompt injection, trust scoring, and agent identity.",
        "eyebrow": "Reference material",
    },
    {
        "title": "Talks / about",
        "href": "/about",
        "description": "Provide short background information and a record of talk formats associated with the project.",
        "eyebrow": "Project information",
    },
]

LIBRARY_TOPICS = [
    {
        "slug": "prompt-injection",
        "title": "Prompt injection",
        "description": "Injection paths in planning loops, agent memory, tool use, and multi-turn orchestration chains.",
    },
    {
        "slug": "trust-and-identity",
        "title": "Trust and identity",
        "description": "Authentication, dynamic trust scoring, role separation, and identity in agent-to-agent interactions.",
    },
    {
        "slug": "agent-to-agent-communication",
        "title": "Agent-to-agent communication",
        "description": "Messaging protocols, negotiation, shared context, and manipulation risks across autonomous agents.",
    },
    {
        "slug": "orchestration-risk",
        "title": "Orchestration risk",
        "description": "Supervisor vulnerabilities, planner abuse, unsafe delegation, and cascading failure modes in MAS systems.",
    },
    {
        "slug": "memory-poisoning",
        "title": "Memory poisoning",
        "description": "Corrupted context stores, retrieval attacks, long-horizon manipulation, and state pollution.",
    },
    {
        "slug": "governance-and-policy",
        "title": "Governance and policy",
        "description": "Controls, accountability, assurance, safety policy, and operational governance for agent ecosystems.",
    },
    {
        "slug": "benchmarks-and-evaluation",
        "title": "Benchmarks and evaluation",
        "description": "Threat models, safety benchmarks, evaluation harnesses, and empirical MAS security measurement.",
    },
]

HOME_RESEARCH_PREVIEW = [
    {
        "title": "Prompt injection through delegation chains",
        "summary": "Recent work on multi-step compromise, tool misuse, and indirect prompt injection in agent workflows.",
        "meta": "Latest papers",
    },
    {
        "title": "Trust, identity, and cross-agent verification",
        "summary": "Recent work on dynamic trust scoring, role separation, and verification in agent-to-agent interaction.",
        "meta": "Emerging themes",
    },
    {
        "title": "Memory poisoning and long-horizon manipulation",
        "summary": "Recent work connecting retrieval, persistent memory, and long-horizon manipulation in agent systems.",
        "meta": "Recent summaries",
    },
]

HOME_GAP_PREVIEW = [
    {"label": "Leading signals", "value": "Prompt injection, orchestration risk"},
    {"label": "Building momentum", "value": "Trust scoring, evaluation benchmarks"},
    {"label": "Early watchlist", "value": "Agent identity, long-horizon governance"},
]

BLOG_POSTS: list[dict[str, str]] = [
    {
        "slug": "a-tiny-multi-agent-experiment-that-explains-multi-agent-systems",
        "title": "A Tiny Multi-Agent Experiment That Explains Multi-Agent Systems",
        "date": "2026-03-07",
        "summary": (
            "A small LangChain-based experiment that uses a research agent, writer agent, editor agent, "
            "and coordinator to show why orchestration and role specialization matter in multi-agent systems."
        ),
        "content_html": """
<p><strong>Framework used</strong></p>
<ul class="article-list">
  <li>Lightweight Python + LangChain setup</li>
  <li><code>langchain-openai</code> with a shared <code>ChatOpenAI</code> model (<code>gpt-4o-mini</code>)</li>
  <li>Role-specific system prompts for each agent</li>
  <li>A simple coordinator in <code>app.py</code> to run the pipeline</li>
  <li>Repository: <a class="post-link" href="https://github.com/0sauerb1012/simplemultiagentsystem" target="_blank" rel="noopener noreferrer">simplemultiagentsystem</a></li>
</ul>
<p><strong>The system architecture</strong><br />The system runs as a simple sequential pipeline:</p>
<div class="flow-diagram" aria-label="Multi-agent pipeline diagram">
  <p class="flow-caption">Pipeline Execution Graph</p>
  <div class="flow-steps">
    <div class="flow-step">
      <span class="flow-step-num">S1</span>
      <div class="flow-step-body">
        <p class="flow-step-text">Input: User Question</p>
        <p class="flow-step-meta">artifact: raw query</p>
      </div>
    </div>
    <div class="flow-step">
      <span class="flow-step-num">S2</span>
      <div class="flow-step-body">
        <p class="flow-step-text">Research Agent</p>
        <p class="flow-step-meta">artifact: concise notes</p>
      </div>
    </div>
    <div class="flow-step">
      <span class="flow-step-num">S3</span>
      <div class="flow-step-body">
        <p class="flow-step-text">Writer Agent (Draft)</p>
        <p class="flow-step-meta">artifact: initial explanation</p>
      </div>
    </div>
    <div class="flow-step">
      <span class="flow-step-num">S4</span>
      <div class="flow-step-body">
        <p class="flow-step-text">Editor Agent</p>
        <p class="flow-step-meta">artifact: critique + revision requests</p>
      </div>
    </div>
    <div class="flow-step">
      <span class="flow-step-num">S5</span>
      <div class="flow-step-body">
        <p class="flow-step-text">Writer Agent (Revision)</p>
        <p class="flow-step-meta">artifact: improved explanation</p>
      </div>
    </div>
    <div class="flow-step">
      <span class="flow-step-num">S6</span>
      <div class="flow-step-body">
        <p class="flow-step-text">Coordinator</p>
        <p class="flow-step-meta">artifact: final answer</p>
      </div>
    </div>
  </div>
</div>
<p>The Coordinator manages the workflow by:</p>
<ul class="article-list">
  <li>Passing outputs between agents</li>
  <li>Controlling execution order</li>
  <li>Printing the final results</li>
</ul>
<p>This keeps each agent simple, while the pipeline stays clear and easy to follow.</p>
<p><strong>Why multi-agent systems matter</strong><br />Single-agent AI can do a lot: answer questions, summarize, and write code. But when a task gets more complex, it often helps to split the work up.</p>
<p>That is the core idea behind multi-agent systems: instead of one "do everything" prompt, you assign roles. Each role focuses on one part of the problem, and the pieces are combined into a better final result.</p>
<p>In this post, we walk through a small, runnable-style experiment that shows how a simple group of agents can collaborate to create a clearer explanation than a single prompt alone.</p>
<p>This is the first post in a series. I will start here, build out a simple multi-agent system, and slowly add capabilities to make it more robust. Along the way I will introduce security considerations. The goal is both personal experimentation and a ride along for those interested in multi-agent systems and security.</p>
<p><strong>What is a multi-agent system?</strong><br />A multi-agent system (MAS) is an AI setup where multiple agents collaborate to solve a problem.</p>
<ul class="article-list">
  <li>A specific role</li>
  <li>A focused responsibility</li>
  <li>A clear handoff to the next agent</li>
</ul>
<p>Instead of one model trying to do everything at once, work is distributed across specialized roles. A quick analogy is a content team:</p>
<ul class="article-list">
  <li>Researcher: gathers facts</li>
  <li>Writer: produces a draft</li>
  <li>Editor: reviews and improves it</li>
</ul>
<p>A multi-agent system works the same way, only the team members are agents.</p>
<p><strong>The goal of this experiment</strong><br />Use a small multi-agent system to answer one question: "What is a multi-agent system?"</p>
<p>To keep it educational and focused, the experiment uses these constraints:</p>
<ul class="article-list">
  <li>Minimal architecture</li>
  <li>The same LLM powers all agents</li>
  <li>No tools</li>
  <li>No memory</li>
  <li>No RAG</li>
  <li>No web search</li>
</ul>
<p>This isolates the real lesson: orchestration plus role specialization.</p>
<p><strong>Agent roles (what each one does)</strong></p>
<ul class="article-list">
  <li>Research Agent: produces concise bullet notes about the question to give the writer useful context</li>
  <li>Writer Agent: turns notes into a readable explanation (draft, then revision based on editor feedback)</li>
  <li>Editor Agent: reviews the draft and suggests improvements; critiques only and does not rewrite</li>
  <li>Coordinator: orchestrates the process and ensures execution order, visibility, and logging</li>
</ul>
<p><strong>Making collaboration visible</strong><br />To make teamwork easy to understand, the program prints each stage:</p>
<ul class="article-list">
  <li>USER QUESTION</li>
  <li>RESEARCH NOTES</li>
  <li>DRAFT EXPLANATION</li>
  <li>EDITOR FEEDBACK</li>
  <li>REVISED EXPLANATION</li>
  <li>FINAL ANSWER</li>
</ul>
<p>This turns the system into a learning tool. Instead of a black box, you can watch the explanation improve step-by-step.</p>
<p><strong>Logging and traceability</strong><br />The experiment produces two helpful logs:</p>
<ul class="article-list">
  <li>Detailed interaction log (<code>.log</code>): prompts, agent responses, and handoff messages</li>
  <li>Execution trace (<code>_trace.md</code>): a clean, step-by-step record of the pipeline</li>
</ul>
<p>Useful for debugging, inspecting behavior, and visualizing how information moves through the system.</p>
<p><strong>Lessons from the experiment</strong></p>
<ul class="article-list">
  <li>Specialization improves clarity: roles create more structured output</li>
  <li>Review loops improve quality: editor to writer revision boosts the final explanation</li>
  <li>Multi-agent value shows up fast: benefits appear without complicated infrastructure</li>
</ul>
<p><strong>Closing thoughts</strong><br />Multi-agent systems are not about making AI more complicated. They are about structured collaboration. Even a small pipeline like this demonstrates the key advantage: divide the work, specialize roles, and improve results through review.</p>
<p>If you want to try it yourself, modify the code and ask new questions. You may be surprised how far a simple agent workflow can go.</p>
""",
    },
]

CONCEPT_ARTICLES = [
    {
        "slug": "what-is-multi-agent-security",
        "title": "What is multi-agent security?",
        "summary": "Define the field, its core threat models, and the gap between single-agent safety and multi-agent system security.",
    },
    {
        "slug": "prompt-injection-in-agent-systems",
        "title": "What is prompt injection in agent systems?",
        "summary": "Explain prompt injection beyond chat interfaces, including delegation, tool use, and long-horizon workflows.",
    },
    {
        "slug": "dynamic-trust-scoring",
        "title": "What is dynamic trust scoring?",
        "summary": "An introductory note on trust calibration between agents, tools, identities, and external services.",
    },
]

TOOLS_AND_FRAMEWORKS = [
    {
        "title": "Agent identity and trust layer",
        "description": "Placeholder for identity frameworks, trust exchanges, and secure service-to-agent communication models.",
        "tag": "Identity",
    },
    {
        "title": "Prompt and tool policy enforcement",
        "description": "Policy layers, execution controls, and runtime filtering approaches for tool-enabled agent systems.",
        "tag": "Policy",
    },
    {
        "title": "Evaluation harnesses",
        "description": "Benchmarks and red-team frameworks for assessing prompt injection, orchestration failure, and memory abuse.",
        "tag": "Evaluation",
    },
    {
        "title": "Secure orchestration patterns",
        "description": "Reference architectures for supervisors, message buses, approval gates, and bounded delegation.",
        "tag": "Architecture",
    },
]

EXPERIMENTS = [
    {
        "title": "Delegation abuse simulator",
        "description": "A placeholder for experiments on how unsafe task handoffs propagate risk across agent teams.",
    },
    {
        "title": "Prompt injection replay lab",
        "description": "A placeholder for experiments that replay prompt-injection patterns against agent workflows and tool chains.",
    },
    {
        "title": "Trust scoring sandbox",
        "description": "A placeholder for experiments on confidence, authorization, and trust decay in multi-agent interaction.",
    },
]

INDUSTRY_ITEMS = [
    {
        "title": "Vendor research watch",
        "description": "Track publications from model vendors, infrastructure providers, and platform teams working on agent security.",
        "tag": "Vendor",
    },
    {
        "title": "Incident and failure notes",
        "description": "Capture agent incidents, coordination failures, and lessons from production deployments.",
        "tag": "Incidents",
    },
    {
        "title": "Ecosystem commentary",
        "description": "A placeholder for practitioner perspectives, architecture critiques, and commentary on current developments.",
        "tag": "Analysis",
    },
]

INDUSTRY_FEEDS = [
    {
        "name": "OWASP Blog",
        "category": "ai_security",
        "url": "https://owasp.org/blog/feed.xml",
        "priority": "high",
        "notes": "Includes AI agent security guidance and emerging patterns",
    },
    {
        "name": "Trail of Bits Blog",
        "category": "security_research",
        "url": "https://blog.trailofbits.com/feed/",
        "priority": "critical",
        "notes": "High-quality offensive and defensive research, including multi-agent systems work",
    },
    {
        "name": "Anthropic News",
        "category": "ai_research",
        "url": "https://www.anthropic.com/news/rss.xml",
        "priority": "high",
        "notes": "Frontier AI safety and agent-related research updates",
    },
    {
        "name": "OpenAI Blog",
        "category": "ai_research",
        "url": "https://openai.com/blog/rss.xml",
        "priority": "medium",
        "notes": "Occasional agent and safety related content",
    },
    {
        "name": "Hugging Face Blog",
        "category": "ai_tools",
        "url": "https://huggingface.co/blog/feed.xml",
        "priority": "high",
        "notes": "Agent frameworks, tooling, and experiments",
    },
    {
        "name": "LangChain Blog",
        "category": "ai_agents",
        "url": "https://blog.langchain.dev/rss/",
        "priority": "high",
        "notes": "Agent architectures and real-world implementations",
    },
    {
        "name": "Schneier on Security",
        "category": "security_thought_leadership",
        "url": "https://www.schneier.com/feed/atom/",
        "priority": "medium",
        "notes": "High-level security insights, occasionally relevant to AI/agents",
    },
    {
        "name": "Dark Reading",
        "category": "security_news",
        "url": "https://www.darkreading.com/rss.xml",
        "priority": "low",
        "notes": "Industry news, requires filtering for relevance",
    },
    {
        "name": "Towards Data Science",
        "category": "ai_general",
        "url": "https://towardsdatascience.com/feed",
        "priority": "low",
        "notes": "High volume, requires heavy filtering for agent relevance",
    },
    {
        "name": "arXiv cs.AI",
        "category": "academic",
        "url": "https://rss.arxiv.org/rss/cs.AI",
        "priority": "critical",
        "notes": "Core AI research feed",
    },
    {
        "name": "arXiv cs.CR",
        "category": "academic_security",
        "url": "https://rss.arxiv.org/rss/cs.CR",
        "priority": "critical",
        "notes": "Security and cryptography papers",
    },
    {
        "name": "arXiv cs.MA",
        "category": "multi_agent",
        "url": "https://rss.arxiv.org/rss/cs.MA",
        "priority": "critical",
        "notes": "Multi-agent systems research",
    },
]

INDUSTRY_FILTER_KEYWORDS = [
    "agent",
    "multi-agent",
    "autonomous agent",
    "agentic",
    "llm agent",
    "tool use",
    "prompt injection",
    "agent orchestration",
    "function calling",
    "agent memory",
    "a2a",
    "agent communication",
]

INDUSTRY_EXCLUDE_KEYWORDS = [
    "marketing",
    "advertisement",
    "sponsored",
]

INDUSTRY_SCORING_WEIGHTS = {
    "recency": 0.4,
    "source_priority": 0.3,
    "keyword_match": 0.3,
}

TALKS = [
    {
        "title": "Multi-agent security landscape",
        "description": "A talk format focused on threat taxonomy, research structure, and design patterns in multi-agent security.",
    },
    {
        "title": "Research-driven practitioner briefings",
        "description": "Shorter briefing format for teams evaluating agent orchestration, identity, and runtime control models.",
    },
]

ABOUT_PROFILE = {
    "name": "Benjamin Sauers",
    "location": "Michigan",
    "role": "",
    "linkedin_url": "https://www.linkedin.com/in/benjamin-sauers",
    "bio": (
        "Benjamin Sauers is a Michigan-based PhD student at Eastern Michigan University and a cybersecurity "
        "professional at Rocket. His work sits at the intersection of cloud-native technologies, AI, and modern "
        "security practice, with a particular interest in how emerging intelligent systems change operational and "
        "architectural risk."
    ),
}

ABOUT_FOCUS_AREAS = [
    "Cloud-native technologies and modern platform security",
    "Applied AI and agentic system risk",
    "Security operations and vulnerability management",
    "Multi-agent systems research",
]

ABOUT_EDUCATION = {
    "school": "Eastern Michigan University",
    "items": [
        "Research focus: cybersecurity, applied computing, and multi-agent systems",
        "PhD studies in progress at Eastern Michigan University",
        "M.S. in Cybersecurity, Eastern Michigan University",
        "M.A. in Teaching, University of Saint Francis",
    ],
}

ABOUT_CERTIFICATIONS = [
    "AWS Certified Cloud Practitioner",
    "AWS Certified Solutions Architect - Associate",
    "CompTIA PenTest+",
    "CompTIA Security+",
    "CompTIA CySA+",
    "CompTIA Advanced Security Practitioner (SecurityX)",
]


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    research_preview = await _build_home_research_preview()
    trend_preview, trend_visual = await _build_home_trend_preview()
    return templates.TemplateResponse(
        request,
        "index.html",
        _base_context(
            active_page="/",
            home_features=HOME_FEATURES,
            featured_research=LIBRARY_TOPICS[:3],
            featured_posts=BLOG_POSTS[:2],
            research_preview=research_preview,
            gap_preview=trend_preview,
            trend_visual=trend_visual,
            concept_preview=CONCEPT_ARTICLES,
        ),
    )


@router.get("/research-feed", response_class=HTMLResponse)
async def research_feed(
    request: Request,
    source: str = Query(default=""),
) -> HTMLResponse:
    context = await _build_feed_context(request, limit=12, source_filter=source)
    context.update(
        _base_context(
            active_page="/research-feed",
            topics=BROAD_AGENTIC_AI_TOPICS,
            active_source_feeds=ACTIVE_SOURCE_FEEDS,
            limit=12,
        )
    )
    return templates.TemplateResponse(
        request,
        "research_feed.html",
        context,
    )


@router.get("/feed", response_class=HTMLResponse)
async def get_feed_partial(
    request: Request,
    limit: int = Query(default=12, ge=1, le=20),
) -> HTMLResponse:
    context = await _build_feed_context(request, limit=limit)
    return templates.TemplateResponse(request, "_feed_content.html", context)


@router.get("/research-library", response_class=HTMLResponse)
async def research_library(request: Request) -> HTMLResponse:
    try:
        library_groups = await hub_service.fetch_library_groups(limit=24)
        error = None if library_groups else "No classified papers are available for the library yet."
    except Exception as exc:
        library_groups = []
        detail = str(exc).strip() or exc.__class__.__name__
        error = f"Unable to build the research library right now: {detail}"

    return templates.TemplateResponse(
        request,
        "research_library.html",
        _base_context(
            active_page="/research-library",
            library_topics=LIBRARY_TOPICS,
            library_groups=library_groups,
            error=error,
        ),
    )


@router.get("/research-gaps", response_class=HTMLResponse)
async def research_gaps(request: Request) -> HTMLResponse:
    context = await _build_gap_context(request)
    context.update(
        _base_context(
            active_page="/research-gaps",
        )
    )
    return templates.TemplateResponse(request, "research_gaps.html", context)


@router.get("/paper", response_class=HTMLResponse)
async def paper_detail(request: Request, paper_id: str = Query(..., min_length=1)) -> HTMLResponse:
    try:
        card = await hub_service.fetch_paper_card(canonical_id=paper_id)
        error = None
    except Exception as exc:
        card = None
        detail = str(exc).strip() or exc.__class__.__name__
        error = f"Unable to load this paper right now: {detail}"

    return templates.TemplateResponse(
        request,
        "paper_detail.html",
        _base_context(
            active_page="/research-feed",
            card=card,
            error=error,
        ),
    )


@router.get("/blog", response_class=HTMLResponse)
async def blog_index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "blog_index.html",
        _base_context(
            active_page="/blog",
            posts=BLOG_POSTS,
        ),
    )


@router.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_post(request: Request, slug: str) -> HTMLResponse:
    post = next((item for item in BLOG_POSTS if item["slug"] == slug), None)
    if post is None:
        raise HTTPException(status_code=404, detail="Blog post not found.")
    return templates.TemplateResponse(
        request,
        "blog_post.html",
        _base_context(
            active_page="/blog",
            post=post,
        ),
    )


@router.get("/concepts", response_class=HTMLResponse)
async def concepts_index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "concepts.html",
        _base_context(
            active_page="/concepts",
            concept_articles=CONCEPT_ARTICLES,
        ),
    )


@router.get("/concepts/{slug}", response_class=HTMLResponse)
async def concept_detail(request: Request, slug: str) -> HTMLResponse:
    article = next((item for item in CONCEPT_ARTICLES if item["slug"] == slug), CONCEPT_ARTICLES[0])
    return templates.TemplateResponse(
        request,
        "concept_detail.html",
        _base_context(
            active_page="/concepts",
            article=article,
        ),
    )


@router.get("/tools-frameworks", response_class=HTMLResponse)
async def tools_frameworks(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "tools_frameworks.html",
        _base_context(
            active_page="/tools-frameworks",
            tools=TOOLS_AND_FRAMEWORKS,
        ),
    )


@router.get("/experiments", response_class=HTMLResponse)
async def experiments(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "experiments.html",
        _base_context(
            active_page="/experiments",
            experiments=EXPERIMENTS,
        ),
    )


@router.get("/industry-intel", response_class=HTMLResponse)
async def industry_intel(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "industry_intel.html",
        _base_context(
            active_page="/industry-intel",
            intel_items=INDUSTRY_ITEMS,
            intel_feeds=INDUSTRY_FEEDS,
            intel_filter_keywords=INDUSTRY_FILTER_KEYWORDS,
            intel_exclude_keywords=INDUSTRY_EXCLUDE_KEYWORDS,
            intel_scoring_weights=INDUSTRY_SCORING_WEIGHTS,
        ),
    )


@router.get("/about", response_class=HTMLResponse)
async def about(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "about.html",
        _base_context(
            active_page="/about",
            profile=ABOUT_PROFILE,
            focus_areas=ABOUT_FOCUS_AREAS,
            education=ABOUT_EDUCATION,
            certifications=ABOUT_CERTIFICATIONS,
        ),
    )


@router.get("/areas/{area_slug}", response_class=HTMLResponse)
async def area_detail(
    request: Request,
    area_slug: str,
    limit: int = Query(default=36, ge=1, le=500),
    q: str = Query(default=""),
    source: str = Query(default=""),
) -> HTMLResponse:
    context = await _build_area_context(
        request,
        area_slug=area_slug,
        limit=limit,
        q=q,
        source=source,
    )

    return templates.TemplateResponse(
        request,
        "area.html",
        _base_context(
            active_page="/research-gaps",
            **context,
        ),
    )


@router.post("/areas/{area_slug}/export", response_model=None)
async def export_area_papers(
    request: Request,
    area_slug: str,
    limit: int = Form(default=36),
    q: str = Form(default=""),
    source: str = Form(default=""),
    paper_id: list[str] = Form(default=[]),
    export_format: str = Form(...),
) -> Response:
    context = await _build_area_context(
        request,
        area_slug=area_slug,
        limit=max(1, min(limit, 500)),
        q=q,
        source=source,
    )
    cards = context["cards"]
    selected_ids = {item.strip() for item in paper_id if item.strip()}
    selected_cards = [
        card for card in cards if (card.paper.canonical_id or card.paper.id) in selected_ids
    ]

    if not selected_cards:
        context["error"] = "Select at least one article to export."
        return templates.TemplateResponse(
            request,
            "area.html",
            _base_context(active_page="/research-gaps", **context),
            status_code=400,
        )

    area_slugified = slugify_filename(str(context["area_label"]))
    if export_format == "csv":
        filename = f"{area_slugified}-papers.csv"
        content = _build_cards_csv(selected_cards)
        media_type = "text/csv; charset=utf-8"
    elif export_format == "zotero":
        filename = f"{area_slugified}-papers.ris"
        content = build_ris([card.paper for card in selected_cards])
        media_type = "application/x-research-info-systems"
    else:
        context["error"] = "Unknown export format."
        return templates.TemplateResponse(
            request,
            "area.html",
            _base_context(active_page="/research-gaps", **context),
            status_code=400,
        )

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/fetch", response_class=HTMLResponse)
async def fetch_latest_papers(
    request: Request,
    limit: int = Form(default=12),
) -> HTMLResponse:
    context = await _build_feed_context(request, limit=limit)
    context.update(_base_context(active_page="/research-feed"))
    return templates.TemplateResponse(request, "research_feed.html", context)


async def _build_feed_context(request: Request, *, limit: int, source_filter: str = "") -> dict:
    try:
        available_sources = hub_service.fetch_stored_sources()
        selected_source = source_filter.strip()
        if selected_source:
            result = hub_service.fetch_stored_latest_papers_by_source(
                source_filter=selected_source,
                limit=limit,
            )
        else:
            result = hub_service.fetch_stored_latest_papers(limit=limit)
        error = None if result.cards else "No papers were returned for the tracked feed."
        cards = result.cards
        feed_label = result.feed_label
        tracked_topics = result.tracked_topics
        heatmap_rows = result.heatmap_rows
        gap_labels = result.gap_labels
        concentration_labels = result.concentration_labels
    except Exception as exc:
        cards = []
        feed_label = None
        tracked_topics = []
        heatmap_rows = []
        gap_labels = []
        concentration_labels = []
        available_sources = []
        selected_source = source_filter.strip()
        detail = str(exc).strip() or exc.__class__.__name__
        error = f"Unable to build the merged research feed right now: {detail}"

    return {
        "request": request,
        "cards": cards,
        "error": error,
        "feed_label": feed_label,
        "tracked_topics": tracked_topics,
        "topics": BROAD_AGENTIC_AI_TOPICS,
        "active_source_feeds": ACTIVE_SOURCE_FEEDS,
        "heatmap_rows": heatmap_rows,
        "gap_labels": gap_labels,
        "concentration_labels": concentration_labels,
        "limit": max(1, min(limit, 20)),
        "available_sources": available_sources,
        "selected_source": selected_source,
    }


async def _build_gap_context(request: Request) -> dict:
    try:
        result = await hub_service.fetch_gap_snapshot()
        error = None if result.heatmap_rows else "No categorized papers are available in the stored corpus yet."
        cards = result.cards
        feed_label = result.feed_label
        tracked_topics = result.tracked_topics
        heatmap_rows = result.heatmap_rows
        gap_labels = result.gap_labels
        concentration_labels = result.concentration_labels
    except Exception as exc:
        cards = []
        feed_label = None
        tracked_topics = []
        heatmap_rows = []
        gap_labels = []
        concentration_labels = []
        detail = str(exc).strip() or exc.__class__.__name__
        error = f"Unable to build the research gaps view right now: {detail}"

    return {
        "request": request,
        "cards": cards,
        "error": error,
        "feed_label": feed_label,
        "tracked_topics": tracked_topics,
        "topics": BROAD_AGENTIC_AI_TOPICS,
        "active_source_feeds": ACTIVE_SOURCE_FEEDS,
        "heatmap_rows": heatmap_rows,
        "gap_labels": gap_labels,
        "concentration_labels": concentration_labels,
        "limit": 12,
    }


async def _build_area_context(
    request: Request,
    *,
    area_slug: str,
    limit: int,
    q: str,
    source: str,
) -> dict:
    try:
        area_label, area_cards = await hub_service.fetch_area_papers(area_slug=area_slug, limit=None)
        search_query = q.strip()
        selected_source = source.strip()
        available_sources = _available_sources_for_cards(
            hub_service.database_service.load_cards()
            if hub_service.database_service.has_persisted_papers()
            else area_cards
        )

        if search_query and hub_service.database_service.has_persisted_papers():
            filtered_cards = hub_service.database_service.load_cards()
        else:
            filtered_cards = area_cards

        if selected_source:
            filtered_cards = _filter_cards_by_source(filtered_cards, selected_source)
        match_count = len(filtered_cards)
        if search_query:
            filtered_cards = _filter_cards_by_keyword(filtered_cards, search_query)
            match_count = len(filtered_cards)
            error = None if filtered_cards else f'No papers matched "{search_query}" in this area.'
        else:
            error = None if filtered_cards else "No papers were returned for this area."
        cards = filtered_cards[:limit]
        total_available = len(filtered_cards)
        has_more = total_available > len(cards)
    except Exception as exc:
        area_label = "Unknown area"
        cards = []
        search_query = q.strip()
        selected_source = source.strip()
        available_sources = []
        match_count = 0
        total_available = 0
        has_more = False
        detail = str(exc).strip() or exc.__class__.__name__
        error = f"Unable to load this research area right now: {detail}"

    return {
        "request": request,
        "area_slug": area_slug,
        "area_label": area_label,
        "cards": cards,
        "error": error,
        "active_source_feeds": ACTIVE_SOURCE_FEEDS,
        "limit": limit,
        "search_query": search_query,
        "match_count": match_count,
        "total_available": total_available,
        "has_more": has_more,
        "selected_source": selected_source,
        "available_sources": available_sources,
    }


def _base_context(*, active_page: str, **extra: object) -> dict:
    return {
        "site_nav": SITE_NAV,
        "active_page": active_page,
        "active_source_feeds": ACTIVE_SOURCE_FEEDS,
        **extra,
    }


def _filter_cards_by_keyword(cards, search_query: str):
    needle = " ".join(search_query.lower().split())
    if not needle:
        return cards

    filtered = []
    for card in cards:
        haystack = " ".join(
            [
                card.paper.title,
                " ".join(card.bullets),
            ]
        ).lower()
        if needle in haystack:
            filtered.append(card)
    return filtered


def _filter_cards_by_source(cards, source_filter: str):
    needle = source_filter.strip().lower()
    if not needle:
        return cards
    filtered = []
    for card in cards:
        sources = _source_keys_for_card(card)
        if needle in sources:
            filtered.append(card)
    return filtered


def _available_sources_for_cards(cards) -> list[str]:
    sources: set[str] = set()
    for card in cards:
        sources.update(_source_keys_for_card(card))
    return sorted(sources)


def _source_keys_for_card(card) -> set[str]:
    sources: set[str] = set()
    if card.paper.source_name:
        sources.add(card.paper.source_name.split("·")[0].strip().lower())
    for source in card.paper.merged_from_sources:
        if source:
            sources.add(source.strip().lower())
    return sources


def _build_cards_csv(cards) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "canonical_id",
            "title",
            "authors",
            "published",
            "source_name",
            "source_type",
            "doi",
            "venue",
            "hub_categories",
            "paper_url",
            "pdf_url",
            "bullet_summary",
        ]
    )
    for card in cards:
        writer.writerow(
            [
                card.paper.canonical_id or card.paper.id,
                card.paper.title,
                ", ".join(card.paper.authors),
                card.paper.published,
                card.paper.source_name,
                card.paper.source_type,
                card.paper.doi or "",
                card.paper.venue or "",
                ", ".join(card.paper.hub_categories),
                card.paper.paper_url,
                card.paper.pdf_url or "",
                " | ".join(card.bullets),
            ]
        )
    return output.getvalue()


async def _build_home_research_preview() -> list[dict[str, str]]:
    try:
        result = await hub_service.fetch_latest_papers(limit=3)
    except Exception:
        return HOME_RESEARCH_PREVIEW

    preview: list[dict[str, str]] = []
    for card in result.cards[:3]:
        published = card.paper.published[:10] if card.paper.published else "Recent publication"
        summary = card.bullets[0] if card.bullets else card.paper.summary
        preview.append(
            {
                "title": card.paper.title,
                "summary": summary,
                "meta": f"Published {published}",
                "href": f"/paper?paper_id={quote_plus(card.paper.canonical_id or card.paper.id)}",
            }
        )
    return preview or HOME_RESEARCH_PREVIEW


async def _build_home_trend_preview() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    try:
        result = await hub_service.fetch_gap_snapshot()
    except Exception:
        fallback_preview = [
            {"label": item["label"], "value": item["value"], "count": None, "status": None, "topics": []}
            for item in HOME_GAP_PREVIEW
        ]
        fallback_visual = [
            {"status": "High concentration", "intensity": 1.0},
            {"status": "Emerging / moderate", "intensity": 0.7},
            {"status": "Gap / underexplored", "intensity": 0.45},
        ]
        return fallback_preview, fallback_visual

    status_labels = {
        "High concentration": "Leading research areas",
        "Emerging / moderate": "Building momentum",
        "Gap / underexplored": "Earlier-stage signals",
    }

    grouped_rows: list[dict[str, object]] = []
    for status in ("High concentration", "Emerging / moderate", "Gap / underexplored"):
        rows = [row for row in result.heatmap_rows if row.status == status][:2]
        if not rows:
            continue
        grouped_rows.append(
            {
                "label": status_labels[status],
                "value": ", ".join(row.category for row in rows),
                "count": sum(row.count for row in rows),
                "status": status,
                "topics": [{"label": row.category, "href": f"/areas/{row.slug}"} for row in rows],
                "intensity": max((row.intensity for row in rows), default=0.0),
            }
        )

    if len(grouped_rows) < 3:
        used_categories = {
            topic["label"]
            for group in grouped_rows
            for topic in group["topics"]  # type: ignore[index]
        }
        for row in result.heatmap_rows:
            if row.category in used_categories:
                continue
            grouped_rows.append(
                {
                    "label": f"Top area #{len(grouped_rows) + 1}",
                    "value": row.category,
                    "count": row.count,
                    "status": row.status,
                    "topics": [{"label": row.category, "href": f"/areas/{row.slug}"}],
                    "intensity": row.intensity,
                }
            )
            if len(grouped_rows) == 3:
                break

    preview = grouped_rows[:3]
    for index, item in enumerate(preview, start=1):
        item["label"] = f"Trending areas {index}"
    visual = [
        {
            "status": item["status"],
            "intensity": item["intensity"],
        }
        for item in preview
    ]
    return preview, visual
