import Link from "next/link";

const navItems = [
  { href: "/", label: "Home" },
  { href: "/about", label: "About" },
  { href: "/research", label: "Research" },
  { href: "/taxonomy", label: "Taxonomy" }
];

export function Header() {
  return (
    <header className="site-header">
      <div>
        <Link className="brand-mark" href="/">
          multiagentsecurity.ai
        </Link>
        <p className="brand-subtitle">
          Research, taxonomy, and intelligence for multi-agent security.
        </p>
      </div>
      <nav className="site-nav" aria-label="Primary">
        {navItems.map((item) => (
          <Link key={item.href} href={item.href}>
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
