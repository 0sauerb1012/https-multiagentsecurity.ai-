from app.services.zotero_rdf import parse_zotero_rdf


def test_parse_zotero_rdf_extracts_basic_metadata() -> None:
    rdf_text = b"""<?xml version="1.0"?>
<rdf:RDF
  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:dcterms="http://purl.org/dc/terms/"
  xmlns:bib="http://purl.org/net/biblio#"
  xmlns:foaf="http://xmlns.com/foaf/0.1/"
  xmlns:link="http://purl.org/rss/1.0/modules/link/">
  <bib:Article rdf:about="#item_1">
    <dc:title>Graph Methods for Drug Discovery</dc:title>
    <dc:creator>
      <foaf:Person>
        <foaf:givenName>Jane</foaf:givenName>
        <foaf:surname>Smith</foaf:surname>
      </foaf:Person>
    </dc:creator>
    <dc:date>2024</dc:date>
    <dc:subject>knowledge graphs</dc:subject>
    <dcterms:abstract>Studies graph methods for candidate ranking in drug discovery.</dcterms:abstract>
    <link:link rdf:resource="https://example.org/paper"/>
  </bib:Article>
</rdf:RDF>
"""
    entries = parse_zotero_rdf(rdf_text, filename="library.rdf")

    assert len(entries) == 1
    entry = entries[0]
    assert entry.paper.title == "Graph Methods for Drug Discovery"
    assert entry.paper.authors == ["Jane Smith"]
    assert entry.paper.summary.startswith("Studies graph methods")
    assert entry.paper.paper_url == "https://example.org/paper"
    assert entry.paper.primary_category == "knowledge graphs"
    assert "Abstract: Studies graph methods" in entry.text
