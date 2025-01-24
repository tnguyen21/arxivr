import sqlite3, sys, arxiv, logging
from datetime import datetime, timedelta
from typing import List

logging.basicConfig(level=logging.DEBUG)

def init_db(schema_file, db_file):
    db = sqlite3.connect(db_file)
    with open(schema_file, mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()


def scrape_arxiv(category: List[str], db_file: str):
    arxiv_client = arxiv.Client(page_size=1000, delay_seconds=5.0)
    db = sqlite3.connect(db_file)
    cursor = db.cursor()

    search = arxiv.Search(
        query="cat: " + " OR cat: ".join(category),
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    
    last_date = None
    for result in arxiv_client.results(search):
        paper_data = (
            result.title, 
            result.entry_id.split('/')[-1], 
            result.published.isoformat(), 
            result.updated.isoformat(), 
            result.summary, 
            ', '.join(str(author) for author in result.authors),
            ", ".join(result.categories), 
            result.pdf_url, 
            result.entry_id, 
            result.entry_id
        )
        cursor.execute('''
            INSERT INTO papers (
                title, arxiv_id, published, updated, summary, 
                author, category, pdf_link, abstract_link, arxiv_link
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', paper_data)
        last_date = result.published

    db.commit()
    db.close()

if __name__ == '__main__':
    schema_file = sys.argv[1] if len(sys.argv) > 1 else 'schema.sql'
    db_file = sys.argv[2] if len(sys.argv) > 2 else 'papers.db'
    init_db(schema_file, db_file)
    
    cats = ['cs.CL', 'cs.AI', 'cs.MA', 'cs.CV', 'cs.LG', 'cs.RO', 'cs.SY', 'cs.SI', 'cs.HC', 'cs.IR']
    
    scrape_arxiv(
        category=cats,
        db_file=db_file
    )
