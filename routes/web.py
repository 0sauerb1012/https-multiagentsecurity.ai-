from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from services.research_hub import ResearchHubService
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
            {"label": "Research Gaps", "href": "/research-gaps"},
        ],
    },
    {
        "label": "Knowledge",
        "href": "/concepts",
        "children": [
            {"label": "Concepts", "href": "/concepts"},
            {"label": "Tools & Frameworks", "href": "/tools-frameworks"},
            {"label": "Experiments / Demos", "href": "/experiments"},
        ],
    },
    {
        "label": "Signals",
        "href": "/industry-intel",
        "children": [
            {"label": "Industry Intel", "href": "/industry-intel"},
            {"label": "Blog", "href": "/blog"},
        ],
    },
    {
        "label": "About",
        "href": "/about",
        "children": [
            {"label": "Talks / About", "href": "/about"},
        ],
    },
]

HOME_FEATURES = [
    {
        "title": "Research feed",
        "href": "/research-feed",
        "description": "Track the newest multi-agent security papers across scholarly sources, with summaries and source-aware metadata.",
        "eyebrow": "Live research",
    },
    {
        "title": "Research library",
        "href": "/research-library",
        "description": "Organize the core literature by subarea so the hub becomes a working map of the field, not just a stream.",
        "eyebrow": "Structured knowledge",
    },
    {
        "title": "Research gaps",
        "href": "/research-gaps",
        "description": "See where the field is crowded, where it is thin, and where new experiments or reviews would add signal.",
        "eyebrow": "Intelligence layer",
    },
    {
        "title": "Concepts",
        "href": "/concepts",
        "description": "Publish crisp explainers for foundational ideas like prompt injection, trust scoring, and agent identity.",
        "eyebrow": "Knowledge base",
    },
    {
        "title": "Industry intel",
        "href": "/industry-intel",
        "description": "Track incidents, vendor research, ecosystem shifts, and operational lessons outside formal academic publishing.",
        "eyebrow": "Field awareness",
    },
    {
        "title": "Talks / about",
        "href": "/about",
        "description": "Package talks, deck links, and profile material so the site establishes authority as a public research hub.",
        "eyebrow": "Public presence",
    },
]

LIBRARY_TOPICS = [
    {
        "title": "Prompt injection",
        "description": "Injection paths in planning loops, agent memory, tool use, and multi-turn orchestration chains.",
    },
    {
        "title": "Trust and identity",
        "description": "Authentication, dynamic trust scoring, role separation, and identity in agent-to-agent interactions.",
    },
    {
        "title": "Agent-to-agent communication",
        "description": "Messaging protocols, negotiation, shared context, and manipulation risks across autonomous agents.",
    },
    {
        "title": "Orchestration risk",
        "description": "Supervisor vulnerabilities, planner abuse, unsafe delegation, and cascading failure modes in MAS systems.",
    },
    {
        "title": "Memory poisoning",
        "description": "Corrupted context stores, retrieval attacks, long-horizon manipulation, and state pollution.",
    },
    {
        "title": "Governance and policy",
        "description": "Controls, accountability, assurance, safety policy, and operational governance for agent ecosystems.",
    },
    {
        "title": "Benchmarks and evaluation",
        "description": "Threat models, safety benchmarks, evaluation harnesses, and empirical MAS security measurement.",
    },
]

HOME_RESEARCH_PREVIEW = [
    {
        "title": "Prompt injection through delegation chains",
        "summary": "A placeholder slot for the newest papers or summaries touching multi-step compromise, tool misuse, and indirect prompt attacks.",
        "meta": "Latest papers",
    },
    {
        "title": "Trust, identity, and cross-agent verification",
        "summary": "A preview surface for the work converging on dynamic trust scoring, role separation, and secure agent-to-agent interaction.",
        "meta": "Emerging themes",
    },
    {
        "title": "Memory poisoning and long-horizon manipulation",
        "summary": "A modular preview block for papers that connect retrieval, memory persistence, and cumulative system corruption.",
        "meta": "Recent summaries",
    },
]

HOME_GAP_PREVIEW = [
    {"label": "Most concentrated", "value": "Prompt injection, orchestration risk"},
    {"label": "Emerging", "value": "Trust scoring, evaluation benchmarks"},
    {"label": "Needs more coverage", "value": "Agent identity, long-horizon governance"},
]

BLOG_POSTS = [
    {
        "slug": "mapping-the-multi-agent-security-surface",
        "title": "Mapping the multi-agent security surface",
        "date": "2026-04-05",
        "summary": "A framing post on why multi-agent security needs its own research map rather than being treated as a subset of generic LLM safety.",
    },
    {
        "slug": "why-agent-orchestration-changes-the-threat-model",
        "title": "Why agent orchestration changes the threat model",
        "date": "2026-03-22",
        "summary": "An operator-focused look at how planner chains, delegated tools, and memory systems create new coordination risks.",
    },
    {
        "slug": "toward-a-live-research-hub-for-agent-security",
        "title": "Toward a live research hub for agent security",
        "date": "2026-02-18",
        "summary": "Notes on building an intelligence surface that merges papers, concepts, incidents, and practical tooling into one place.",
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
        "summary": "A first-pass explainer for trust calibration between agents, tools, identities, and external services.",
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
        "description": "Curated guardrail stacks, execution policies, and runtime filters for tool-enabled agent systems.",
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
        "description": "Prototype space for testing how unsafe task handoffs propagate risk across agent teams.",
    },
    {
        "title": "Prompt injection replay lab",
        "description": "Future demo surface for replaying historical attack patterns against agent workflows and tool chains.",
    },
    {
        "title": "Trust scoring sandbox",
        "description": "Interactive space for modeling confidence, authorization, and decay across multi-agent interactions.",
    },
]

INDUSTRY_ITEMS = [
    {
        "title": "Vendor research watch",
        "description": "Track model vendors, infrastructure providers, and platform teams publishing new agent-security work.",
        "tag": "Vendor",
    },
    {
        "title": "Incident and failure notes",
        "description": "Capture agent incidents, coordination failures, and lessons from production deployments.",
        "tag": "Incidents",
    },
    {
        "title": "Ecosystem commentary",
        "description": "Placeholder for practitioner perspectives, architecture critiques, and field-building commentary.",
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
        "description": "Flagship talk slot for field framing, threat taxonomy, and emerging design patterns.",
    },
    {
        "title": "Research-driven practitioner briefings",
        "description": "Shorter briefing format for teams evaluating agent orchestration, identity, and runtime control models.",
    },
]


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        _base_context(
            request,
            active_page="/",
            home_features=HOME_FEATURES,
            featured_research=LIBRARY_TOPICS[:3],
            featured_posts=BLOG_POSTS[:2],
            research_preview=HOME_RESEARCH_PREVIEW,
            gap_preview=HOME_GAP_PREVIEW,
            concept_preview=CONCEPT_ARTICLES,
        ),
    )


@router.get("/research-feed", response_class=HTMLResponse)
async def research_feed(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "research_feed.html",
        _base_context(
            request,
            active_page="/research-feed",
            topics=BROAD_AGENTIC_AI_TOPICS,
            active_source_feeds=ACTIVE_SOURCE_FEEDS,
            limit=12,
        ),
    )


@router.get("/feed", response_class=HTMLResponse)
async def get_feed_partial(
    request: Request,
    limit: int = Query(default=12, ge=1, le=20),
) -> HTMLResponse:
    context = await _build_feed_context(request, limit=limit)
    return templates.TemplateResponse("_feed_content.html", context)


@router.get("/research-library", response_class=HTMLResponse)
async def research_library(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "research_library.html",
        _base_context(
            request,
            active_page="/research-library",
            library_topics=LIBRARY_TOPICS,
        ),
    )


@router.get("/research-gaps", response_class=HTMLResponse)
async def research_gaps(request: Request) -> HTMLResponse:
    context = await _build_feed_context(request, limit=12)
    context.update(
        _base_context(
            request,
            active_page="/research-gaps",
        )
    )
    return templates.TemplateResponse("research_gaps.html", context)


@router.get("/blog", response_class=HTMLResponse)
async def blog_index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "blog_index.html",
        _base_context(
            request,
            active_page="/blog",
            posts=BLOG_POSTS,
        ),
    )


@router.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_post(request: Request, slug: str) -> HTMLResponse:
    post = next((item for item in BLOG_POSTS if item["slug"] == slug), BLOG_POSTS[0])
    return templates.TemplateResponse(
        "blog_post.html",
        _base_context(
            request,
            active_page="/blog",
            post=post,
        ),
    )


@router.get("/concepts", response_class=HTMLResponse)
async def concepts_index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "concepts.html",
        _base_context(
            request,
            active_page="/concepts",
            concept_articles=CONCEPT_ARTICLES,
        ),
    )


@router.get("/concepts/{slug}", response_class=HTMLResponse)
async def concept_detail(request: Request, slug: str) -> HTMLResponse:
    article = next((item for item in CONCEPT_ARTICLES if item["slug"] == slug), CONCEPT_ARTICLES[0])
    return templates.TemplateResponse(
        "concept_detail.html",
        _base_context(
            request,
            active_page="/concepts",
            article=article,
        ),
    )


@router.get("/tools-frameworks", response_class=HTMLResponse)
async def tools_frameworks(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "tools_frameworks.html",
        _base_context(
            request,
            active_page="/tools-frameworks",
            tools=TOOLS_AND_FRAMEWORKS,
        ),
    )


@router.get("/experiments", response_class=HTMLResponse)
async def experiments(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "experiments.html",
        _base_context(
            request,
            active_page="/experiments",
            experiments=EXPERIMENTS,
        ),
    )


@router.get("/industry-intel", response_class=HTMLResponse)
async def industry_intel(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "industry_intel.html",
        _base_context(
            request,
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
        "about.html",
        _base_context(
            request,
            active_page="/about",
            talks=TALKS,
        ),
    )


@router.get("/areas/{area_slug}", response_class=HTMLResponse)
async def area_detail(
    request: Request,
    area_slug: str,
    limit: int = Query(default=36, ge=1, le=60),
) -> HTMLResponse:
    try:
        area_label, cards = await hub_service.fetch_area_papers(area_slug=area_slug, limit=limit)
        error = None if cards else "No papers were returned for this area."
    except Exception as exc:
        area_label = "Unknown area"
        cards = []
        detail = str(exc).strip() or exc.__class__.__name__
        error = f"Unable to load this research area right now: {detail}"

    return templates.TemplateResponse(
        "area.html",
        _base_context(
            request,
            active_page="/research-gaps",
            area_label=area_label,
            cards=cards,
            error=error,
            active_source_feeds=ACTIVE_SOURCE_FEEDS,
            limit=limit,
        ),
    )


@router.post("/fetch", response_class=HTMLResponse)
async def fetch_latest_papers(
    request: Request,
    limit: int = Form(default=12),
) -> HTMLResponse:
    context = await _build_feed_context(request, limit=limit)
    context.update(_base_context(request, active_page="/research-feed"))
    return templates.TemplateResponse("research_feed.html", context)


async def _build_feed_context(request: Request, *, limit: int) -> dict:
    try:
        result = await hub_service.fetch_latest_papers(limit=limit)
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
    }


def _base_context(request: Request, *, active_page: str, **extra: object) -> dict:
    return {
        "request": request,
        "site_nav": SITE_NAV,
        "active_page": active_page,
        "active_source_feeds": ACTIVE_SOURCE_FEEDS,
        **extra,
    }
