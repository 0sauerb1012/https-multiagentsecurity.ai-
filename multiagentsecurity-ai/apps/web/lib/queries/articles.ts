export type ResearchArticle = {
  slug: string;
  title: string;
  summary: string;
  source: string;
  publishedAt: string;
  category: string;
  tags: string[];
};

const mockArticles: ResearchArticle[] = [
  {
    slug: "multi-agent-risk-taxonomy-draft",
    title: "Toward a Working Taxonomy for Multi-Agent Security Failures",
    summary:
      "A draft framing for attack surfaces, coordination risks, and operational controls in agentic systems.",
    source: "Internal note",
    publishedAt: "2026-04-10",
    category: "Taxonomy",
    tags: ["prompt-injection", "agent-collusion", "observability"]
  },
  {
    slug: "planner-executor-control-boundaries",
    title: "Planner-Executor Systems and Control Boundary Drift",
    summary:
      "Mock research content describing how orchestration design shapes trust, access, and review points.",
    source: "Crossref",
    publishedAt: "2026-04-05",
    category: "Architecture",
    tags: ["planner-executor", "policy-enforcement", "trust-scoring"]
  },
  {
    slug: "shared-memory-poisoning-notes",
    title: "Shared Memory Poisoning in Cooperative Agent Workflows",
    summary:
      "Placeholder analysis of how shared context and memory layers create persistence and contamination risk.",
    source: "arXiv",
    publishedAt: "2026-03-29",
    category: "Threats",
    tags: ["memory-poisoning", "shared-memory", "zero-trust"]
  }
];

export function getFeaturedArticles() {
  return mockArticles.slice(0, 2);
}

export function getResearchArticles() {
  return mockArticles;
}

export function getArticleBySlug(slug: string) {
  return mockArticles.find((article) => article.slug === slug);
}

// TODO: replace mock functions with database-backed implementations in this module.
