import Link from "next/link";

import { ArticleCard } from "@/components/research/ArticleCard";
import { TagCard } from "@/components/taxonomy/TagCard";
import { getFeaturedArticles } from "@/lib/queries/articles";
import { getFeaturedTaxonomy } from "@/lib/queries/taxonomy";

export default function HomePage() {
  const articles = getFeaturedArticles();
  const tags = getFeaturedTaxonomy();

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <p className="eyebrow">Research, taxonomy, and intelligence</p>
        <h1>multiagentsecurity.ai</h1>
        <p className="lede">
          A production-oriented platform for tracking multi-agent security research,
          organizing taxonomy, and building a reliable intelligence pipeline.
        </p>
        <div className="button-row">
          <Link className="button button-primary" href="/research">
            Explore research
          </Link>
          <Link className="button" href="/taxonomy">
            View taxonomy
          </Link>
        </div>
      </section>

      <section className="content-section">
        <div className="section-heading">
          <h2>Project intent</h2>
          <p>
            The initial release focuses on a clean frontend, a shared taxonomy,
            and a backend ingestion foundation that can mature without forcing a rewrite.
          </p>
        </div>
        <div className="two-column">
          <div className="panel">
            <h3>Website</h3>
            <p>
              Next.js App Router powers a research-facing site with room for article
              detail pages, filters, and database-backed content later.
            </p>
          </div>
          <div className="panel">
            <h3>Ingestion</h3>
            <p>
              Python source adapters normalize content from arXiv, Crossref, and RSS into
              a common article model for tagging and persistence.
            </p>
          </div>
        </div>
      </section>

      <section className="content-section">
        <div className="section-heading">
          <h2>Featured research</h2>
          <p>Mock records demonstrate the intended presentation model and routing shape.</p>
        </div>
        <div className="card-grid">
          {articles.map((article) => (
            <ArticleCard key={article.slug} article={article} />
          ))}
        </div>
      </section>

      <section className="content-section">
        <div className="section-heading">
          <h2>Featured taxonomy</h2>
          <p>
            Taxonomy definitions begin in code so ingestion and frontend work can share a
            stable vocabulary from day one.
          </p>
        </div>
        <div className="card-grid card-grid-compact">
          {tags.map((tag) => (
            <TagCard key={tag.slug} tag={tag} />
          ))}
        </div>
      </section>
    </div>
  );
}
