import sqlite3
import sys
import arxiv


def init_db(schema_file, db_file):
    db = sqlite3.connect(db_file)
    with open(schema_file, mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()


def scrape_arxiv(category, max_results=100):
    arxiv_client = arxiv.Client()
    search = arxiv.Search(
        query="cat:cs.CL",
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    
    results = []
    for result in arxiv_client.results(search):
        results.append({
            'title': result.title,
            'arxiv_id': result.entry_id.split('/')[-1],
            'published': result.published,
            'updated': result.updated,
            'summary': result.summary,
            'author': ', '.join(str(author) for author in result.authors),
            'category': category,
            'pdf_link': result.pdf_url,
            'abstract_link': result.entry_id,
            'arxiv_link': result.entry_id
        })
    
    return results

if __name__ == '__main__':
    schema_file = sys.argv[1] if len(sys.argv) > 1 else 'schema.sql'
    db_file = sys.argv[2] if len(sys.argv) > 2 else 'papers.db'
    init_db(schema_file, db_file)

    results = scrape_arxiv('cs.CL')
    db = sqlite3.connect(db_file)
    cursor = db.cursor()
    for result in results:
        cursor.execute('''
            INSERT INTO papers (
                title, arxiv_id, published, updated, summary, 
                author, category, pdf_link, abstract_link, arxiv_link
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result['title'], result['arxiv_id'], result['published'].isoformat(), 
            result['updated'].isoformat(), result['summary'], result['author'],
            result['category'], result['pdf_link'], result['abstract_link'],
            result['arxiv_link']
        ))
    db.commit()
    db.close()