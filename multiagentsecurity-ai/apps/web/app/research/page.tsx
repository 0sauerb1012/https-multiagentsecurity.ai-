import { ArticleCard } from "@/components/research/ArticleCard";
import { getResearchArticles } from "@/lib/queries/articles";

export default function ResearchPage() {
  const articles = getResearchArticles();

  return (
    <div className="page-stack">
      <section className="hero-panel hero-panel-compact">
        <p className="eyebrow">Research</p>
        <h1>Tracked articles and notes</h1>
        <p className="lede">
          This page uses mock data today, but it is structured to be replaced by live
          query modules once the database is wired in.
        </p>
      </section>

      <section className="content-section">
        <div className="card-grid">
          {articles.map((article) => (
            <ArticleCard key={article.slug} article={article} />
          ))}
        </div>
      </section>
    </div>
  );
}
