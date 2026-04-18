export type TaxonomyTag = {
  slug: string;
  label: string;
  description: string;
  group: string;
};

type TaxonomyGroup = {
  key: string;
  title: string;
  description: string;
  tags: TaxonomyTag[];
};

const taxonomyGroups: TaxonomyGroup[] = [
  {
    key: "attack",
    title: "Attack tags",
    description: "Threat patterns and abuse modes relevant to multi-agent systems.",
    tags: [
      {
        slug: "prompt-injection",
        label: "Prompt injection",
        description: "Instructions are manipulated to redirect agent behavior or bypass constraints.",
        group: "Attack"
      },
      {
        slug: "memory-poisoning",
        label: "Memory poisoning",
        description: "Shared memory or retained context is corrupted to shape later agent behavior.",
        group: "Attack"
      }
    ]
  },
  {
    key: "architecture",
    title: "Architecture tags",
    description: "Common orchestration patterns and system designs.",
    tags: [
      {
        slug: "planner-executor",
        label: "Planner executor",
        description: "A planning component delegates work to one or more execution agents.",
        group: "Architecture"
      },
      {
        slug: "shared-memory",
        label: "Shared memory",
        description: "Agents collaborate through a common state or long-lived context layer.",
        group: "Architecture"
      }
    ]
  },
  {
    key: "controls",
    title: "Controls tags",
    description: "Defensive controls and governance patterns.",
    tags: [
      {
        slug: "zero-trust",
        label: "Zero trust",
        description: "Components are treated as untrusted until explicitly verified and constrained.",
        group: "Controls"
      },
      {
        slug: "observability",
        label: "Observability",
        description: "Execution traces, telemetry, and auditability support detection and review.",
        group: "Controls"
      }
    ]
  }
];

export function getFeaturedTaxonomy() {
  return taxonomyGroups.flatMap((group) => group.tags).slice(0, 3);
}

export function getTaxonomyGroups() {
  return taxonomyGroups;
}

// TODO: load shared taxonomy definitions from packages/taxonomy or the database.
