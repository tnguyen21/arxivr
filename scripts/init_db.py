import sqlite3, sys, logging, requests, time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List

logging.basicConfig(level=logging.INFO)

ARXIV_EXPORT_URL = "https://export.arxiv.org/api/query?search_query="

def format_date(date: str):
    # Format date to the format of the arxiv query: YYYYMMDDHHMMSS
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


def extract_paper_data(entry):
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

    return (title, arxiv_id, published, updated, summary, 
            authors, categories, pdf_url, abstract_url, arxiv_url)

def scrape_arxiv(category: List[str], start_date: str, end_date: str, db_file: str, max_results: int = 100):
    query = format_arxiv_query(
        category=category,
        start_date=start_date,
        end_date=end_date,
        max_results=10
    )
    start = 0

    response = requests.get(ARXIV_EXPORT_URL + query)
    root = ET.fromstring(response.text)
    total_results_element = root.find('{http://a9.com/-/spec/opensearch/1.1/}totalResults')
    total_results = int(total_results_element.text) if total_results_element is not None else -1
    logging.info(f"total_results: {total_results}")

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
            logging.info(ARXIV_EXPORT_URL + query)
            retries = 0
            papers_to_insert = []  # Collect papers to insert in a batch

            while retries < 3:  # Retry logic for the query
                response = requests.get(ARXIV_EXPORT_URL + query)
                root = ET.fromstring(response.text)

                papers_to_insert = []  # Reset the list for each attempt
                for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                    papers_to_insert.append(extract_paper_data(entry))  # Add paper data to the list

                if papers_to_insert:
                    break  # Exit the retry loop if papers are found

                retries += 1
                logging.warning(f"No papers found, retrying the query... (Attempt {retries}/3)")
                time.sleep(5)  # Wait before retrying

            if not papers_to_insert:
                logging.error(f"Failed to retrieve papers for query: {query}")
                with open('failed_queries.txt', 'a') as failed_file:
                    failed_file.write(f"Failed query: {query}\n")
                start += max_results
                continue  # Go to the next page of the query

            # Insert all papers in one go
            try:
                cursor.executemany('''
                    INSERT INTO papers (
                        title, arxiv_id, published, updated, summary, 
                        author, category, pdf_link, abstract_link, arxiv_link
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', papers_to_insert)
            except Exception as e:
                logging.error(f"Failed to insert paper data for arxiv_id")

            db.commit()
            logging.info(f"papers db has {cursor.execute('SELECT COUNT(*) FROM papers').fetchone()[0]} papers")
            
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


def retry_queries(queries: List[str]):
    db = sqlite3.connect(db_file)
    cursor = db.cursor()

    for query in queries:
        retries = 0
        papers_to_insert = []  # Reset the list for each attempt
        while retries < 3:
            logging.info(f"Attempting query: {query} (Attempt {retries + 1}/3)")
            response = requests.get(ARXIV_EXPORT_URL + query)
            
            root = ET.fromstring(response.text)
            for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                paper_data = extract_paper_data(entry)
                if paper_data:
                    papers_to_insert.append(paper_data)

            if papers_to_insert:
                break  # Exit the retry loop if papers are found

            retries += 1
            logging.warning(f"No papers found, retrying the query... (Attempt {retries}/3)")
            time.sleep(5)  # Wait before retrying

        if not papers_to_insert:
            logging.error(f"Failed to retrieve papers for query: {query}")
            with open('failed_queries.txt', 'a') as failed_file:
                failed_file.write(f"Failed query: {query}\n")
            continue  # Go to the next query

        # Insert all papers in one go
        try:
            cursor.executemany('''
                INSERT INTO papers (
                    title, arxiv_id, published, updated, summary, 
                    author, category, pdf_link, abstract_link, arxiv_link
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', papers_to_insert)
        except Exception as e:
            logging.error(f"Failed to insert paper data")

        db.commit()
        logging.info(f"papers db has {cursor.execute('SELECT COUNT(*) FROM papers').fetchone()[0]} papers")

    db.close()

if __name__ == '__main__':
    schema_file = sys.argv[1] if len(sys.argv) > 1 else 'schema.sql'
    db_file = sys.argv[2] if len(sys.argv) > 2 else 'papers.db'
    # init_db(schema_file, db_file)
    
    start_year = 2022
    end_year = 2024
    cats = ['cs.CL', 'cs.AI', 'cs.MA', 'cs.CV', 'cs.LG', 'cs.RO', 'cs.SY', 'cs.SI', 'cs.HC', 'cs.IR'] 

    # better to query all categories at once
    # since papers have multiple categories; saves on number of queries
    # for year in range(start_year, end_year):
    #     for month in range(0, 12, 3):  # Iterate every 3 months
    #         start_date = format_date(f"{year}-{month + 1:02d}-01")
    #         end_date = format_date(f"{year}-{month + 4:02d}-01") if month + 4 <= 12 else format_date(f"{year + 1}-01-01")
    #         logging.info(f"scraping {start_date} to {end_date}")
    #         scrape_arxiv(
    #             category=cats,
    #             start_date=start_date,
    #             end_date=end_date,
    #             db_file=db_file,
    #             max_results=500
    #         )

    # retry failed queries
    with open('failed_queries.txt', 'r') as f:
        queries = f.readlines()
        queries = [query.strip() for query in queries]  # remove newlines
        formatted_queries = []
        for query in queries:
            # Extract the date range from the query
            date_range = query.split('submittedDate:')[1].split('&')[0]
            formatted_query = f"{query.split('Failed query: ')[1]}&date_range={date_range}"
            formatted_queries.append(formatted_query)
    retry_queries(formatted_queries)

