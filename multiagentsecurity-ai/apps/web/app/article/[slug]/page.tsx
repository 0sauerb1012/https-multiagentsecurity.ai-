import { notFound } from "next/navigation";

import { getArticleBySlug } from "@/lib/queries/articles";

type ArticlePageProps = {
  params: Promise<{ slug: string }>;
};

export default async function ArticlePage({ params }: ArticlePageProps) {
  const { slug } = await params;
  const article = getArticleBySlug(slug);

  if (!article) {
    notFound();
  }

  return (
    <div className="page-stack">
      <section className="hero-panel hero-panel-compact">
        <p className="eyebrow">{article.source}</p>
        <h1>{article.title}</h1>
        <p className="lede">{article.summary}</p>
      </section>

      <section className="content-section">
        <div className="detail-meta">
          <span>{article.publishedAt}</span>
          <span>{article.category}</span>
          <span>{article.tags.join(", ")}</span>
        </div>
        <div className="prose-block">
          <p>
            This route is a placeholder for a future article detail experience backed by
            the primary database. It currently renders mock content so navigation,
            metadata, and layout decisions can be made early.
          </p>
          <p>
            TODO: replace this section with stored article content, source metadata,
            related research links, and structured citations.
          </p>
        </div>
      </section>
    </div>
  );
}
