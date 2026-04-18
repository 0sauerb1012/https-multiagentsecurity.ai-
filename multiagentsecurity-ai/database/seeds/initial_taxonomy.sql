BEGIN;

INSERT INTO tags (slug, label, tag_group, description)
VALUES
    ('prompt-injection', 'Prompt Injection', 'attack', 'Manipulating prompts or instructions to redirect agent behavior.'),
    ('memory-poisoning', 'Memory Poisoning', 'attack', 'Contaminating retained or shared memory to influence later execution.'),
    ('tool-abuse', 'Tool Abuse', 'attack', 'Misusing tool access or tool invocation to exceed intended capabilities.'),
    ('agent-collusion', 'Agent Collusion', 'attack', 'Undesired coordination between agents that amplifies risk or bypasses controls.'),
    ('planner-executor', 'Planner Executor', 'architecture', 'Planning and execution are separated across distinct components or agents.'),
    ('graph-orchestration', 'Graph Orchestration', 'architecture', 'Execution flows through an explicit node and edge graph.'),
    ('swarm', 'Swarm', 'architecture', 'Many agents coordinate in a relatively decentralized pattern.'),
    ('shared-memory', 'Shared Memory', 'architecture', 'Agents collaborate through a common memory or context layer.'),
    ('zero-trust', 'Zero Trust', 'controls', 'Treating components as untrusted until explicitly constrained and verified.'),
    ('trust-scoring', 'Trust Scoring', 'controls', 'Assigning confidence levels to agents, tools, or outputs.'),
    ('policy-enforcement', 'Policy Enforcement', 'controls', 'Applying explicit policy checks to agent actions and outputs.'),
    ('observability', 'Observability', 'controls', 'Capturing telemetry, traces, and audit data for review and detection.')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO categories (slug, label, description)
VALUES
    ('research', 'Research', 'Research papers, notes, and technical analysis.'),
    ('taxonomy', 'Taxonomy', 'Tagging frameworks and category definitions.'),
    ('intelligence', 'Intelligence', 'Threat intelligence and operational reporting.'),
    ('case-studies', 'Case Studies', 'Concrete incidents, examples, and walkthroughs.')
ON CONFLICT (slug) DO NOTHING;

COMMIT;
