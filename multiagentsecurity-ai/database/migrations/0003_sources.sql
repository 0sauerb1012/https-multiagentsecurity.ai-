BEGIN;

CREATE TABLE IF NOT EXISTS categories (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS article_categories (
    article_id BIGINT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    category_id BIGINT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (article_id, category_id)
);

INSERT INTO categories (slug, label, description)
VALUES
    ('research', 'Research', 'Research papers, notes, and technical analysis.'),
    ('taxonomy', 'Taxonomy', 'Tagging frameworks and category definitions.'),
    ('intelligence', 'Intelligence', 'Threat intelligence and operational reporting.')
ON CONFLICT (slug) DO NOTHING;

COMMIT;
