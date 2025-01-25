import sqlite3, sys, logging, requests, time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List

logging.basicConfig(level=logging.DEBUG)

ARXIV_EXPORT_URL = "https://export.arxiv.org/api/query?search_query="

def format_date(date: str):
    """
    Format date to the format of the arxiv query:
    YYYYMMDDHHMMSS
    """
    date = datetime.strptime(date, '%Y-%m-%d')
    return date.strftime('%Y%m%d%H%M%S')

def format_arxiv_query(category: List[str], start_date: str, end_date: str, start: int = 0, max_results: int = 100):
    if len(category) == 1:
        query = f"cat:{category[0]}+AND+submittedDate:[{start_date}+TO+{end_date}]&start={start}&max_results={max_results}"
    else:
        query = f"(cat:{category[0]}+OR+" + "+OR+".join([f"cat:{cat}" for cat in category[1:]]) + f")+AND+submittedDate:[{start_date}+TO+{end_date}]&start={start}&max_results={max_results}"
    return query

def init_db(schema_file, db_file):
    db = sqlite3.connect(db_file)
    with open(schema_file, mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()


def scrape_arxiv(category: List[str], start_date: str, end_date: str, db_file: str, max_results: int = 100):
    query = format_arxiv_query(
        category=category,
        start_date=start_date,
        end_date=end_date,
        max_results=max_results
    )
    total_results = 1
    start = 0

    db = sqlite3.connect(db_file)
    cursor = db.cursor()

    try:
        while start < total_results:
            query = format_arxiv_query(
                category=category,
                start_date=start_date,
                end_date=end_date,
                start=start,
                max_results=max_results
            )
            logging.debug(ARXIV_EXPORT_URL + query)
            response = requests.get(ARXIV_EXPORT_URL + query)
            root = ET.fromstring(response.text)
            total_results_element = root.find('{http://a9.com/-/spec/opensearch/1.1/}totalResults')
            total_results = int(total_results_element.text) if total_results_element is not None else -1

            if total_results == -1:
                logging.error(f"Failed to fetch total results for query: {query}")
                break

            logging.info(f"{total_results=}, {start=}, {max_results=}")
            for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                title = entry.find('{http://www.w3.org/2005/Atom}title').text
                arxiv_id = entry.find('{http://www.w3.org/2005/Atom}id').text
                published = entry.find('{http://www.w3.org/2005/Atom}published').text
                updated = entry.find('{http://www.w3.org/2005/Atom}updated').text
                summary = entry.find('{http://www.w3.org/2005/Atom}summary').text
                authors = ", ".join([author.find('{http://www.w3.org/2005/Atom}name').text for author in entry.findall('{http://www.w3.org/2005/Atom}author')])
                categories = ", ".join([category.get('term') for category in entry.findall('{http://www.w3.org/2005/Atom}category')])
                pdf_url = arxiv_id.replace('abs', 'pdf') if arxiv_id else None
                abstract_url = arxiv_id
                arxiv_url = arxiv_id

                paper_data = (
                    title, arxiv_id, published, updated, summary, 
                    authors, categories, pdf_url, abstract_url, arxiv_url
                )
                try:
                    cursor.execute('''
                        INSERT INTO papers (
                            title, arxiv_id, published, updated, summary, 
                            author, category, pdf_link, abstract_link, arxiv_link
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', paper_data)
                except Exception as e:
                    logging.error(f"Failed to insert paper data into database: {e}")
                    with open('log.txt', 'a') as log_file:
                        log_file.write(f"Error inserting paper data: {e}\n")
            db.commit()

            start += max_results
            if start < total_results:
                time.sleep(5)  # Wait for 5 seconds before the next request

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        with open('resume_params.txt', 'w') as resume_file:
            resume_file.write(f"category={category}\n")
            resume_file.write(f"start_date={start_date}\n")
            resume_file.write(f"end_date={end_date}\n")
            resume_file.write(f"start={start}\n")
            resume_file.write(f"max_results={max_results}\n")
            resume_file.write(f"total_results={total_results}\n")
    
    db.close()

if __name__ == '__main__':
    schema_file = sys.argv[1] if len(sys.argv) > 1 else 'schema.sql'
    db_file = sys.argv[2] if len(sys.argv) > 2 else 'papers.db'
    init_db(schema_file, db_file)
    
    start_date = format_date("2021-01-01")
    end_date = format_date("2025-01-23")
    cats = ['cs.CL', 'cs.AI', 'cs.MA', 'cs.CV', 'cs.LG', 'cs.RO', 'cs.SY', 'cs.SI', 'cs.HC', 'cs.IR']    

    scrape_arxiv(
        category=cats,
        start_date=start_date,
        end_date=end_date,
        db_file=db_file,
        max_results=1000
    )
