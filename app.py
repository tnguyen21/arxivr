from flask import Flask, render_template, g, request, jsonify, redirect, url_for, make_response
import sqlite3, pickle
from transformers import AutoProcessor, AutoModel
from datetime import datetime

DATABASE = 'papers.db'
INDEX_FILE = 'index.pkl'
CATEGORIES = ['cs.CL', 'cs.AI', 'cs.MA', 'cs.CV', 'cs.LG', 'cs.RO', 'cs.SY', 'cs.SI', 'cs.HC', 'cs.IR'] 

vector_index, processor, model = None, None, None

def before_app_init():
    global vector_index, processor, model
    with open(INDEX_FILE, 'rb') as f:
        vector_index = pickle.load(f)
    processor = AutoProcessor.from_pretrained("google/siglip-base-patch16-224")
    model = AutoModel.from_pretrained("google/siglip-base-patch16-224")

before_app_init()

app = Flask(__name__)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.route('/')
def index():
    db = get_db()
    per_page = 10  # Number of papers per page
    page = request.args.get('page', 1, type=int)  # Get the page number from the query parameters
    category = request.args.get('category', None)
    offset = (page - 1) * per_page

    # TODO figure out better scheme and indexes to make this faster if we need to
    if category:
        papers = db.execute('SELECT * FROM papers WHERE category LIKE ? ORDER BY published DESC LIMIT ? OFFSET ?', ('%' + category + '%', per_page, offset)).fetchall()
        total_papers = db.execute('SELECT COUNT(*) as count FROM papers WHERE category LIKE ?', ('%' + category + '%',)).fetchone()['count']
    else:
        papers = db.execute('SELECT * FROM papers ORDER BY published DESC LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
        total_papers = db.execute('SELECT COUNT(*) as count FROM papers').fetchone()['count']
    
    # TODO this will slow down the page load; should just have nicely formatted dates in the database
    # Format the published date for each paper
    papers = [dict(paper) for paper in papers]
    for paper in papers:
        paper['published'] = datetime.strptime(paper['published'], '%Y-%m-%dT%H:%M:%S%z').strftime('%d %b %Y')
    
    # Get total count of papers for pagination, considering the category filter
    total_pages = (total_papers + per_page - 1) // per_page  # Ceiling division
    return render_template('index.html', papers=papers, page=page, total_pages=total_pages, has_prev=page > 1, has_next=page < total_pages, categories=CATEGORIES)

@app.route('/about')
def about():
    return render_template('about.html', page_title="About")

@app.route('/login')
def login():
    return render_template('login.html', page_title="Login")

@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('index')))
    response.set_cookie('user_id', '', expires=0)
    return response

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username')
    db = get_db()
    db.execute('INSERT OR IGNORE INTO users (username) VALUES (?)', (username,))
    db.commit()
    user = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    return jsonify({'message': 'Login successful', 'user_id': user['id']}), 200

@app.route('/papers/<int:paper_id>')
def paper(paper_id):
    global vector_index
    db = get_db()
    paper = db.execute('SELECT * FROM papers WHERE id = ?', (paper_id,)).fetchone()
    vec = vector_index.get_items([paper_id])
    # TODO figure out how to nicely render distances in template
    # TODO do we want to do a simpler BM25 or TF-IDF search instead to initially get similar papers?, then use the vector index for the final results?
    ids, _ = vector_index.knn_query(vec, k=10)
    similar_papers = db.execute(f"SELECT * FROM papers WHERE id IN ({','.join(map(str, ids[0]))})").fetchall()
    return render_template('paper.html', paper=paper, similar_papers=similar_papers, page_title="Paper")

@app.route('/papers/save', methods=['POST'])
def save_paper():
    data = request.get_json()
    user_id = data.get('user_id')
    paper_id = data.get('paper_id')
    db = get_db()
    db.execute('INSERT INTO user_saved_papers (user_id, paper_id) VALUES (?, ?)', (user_id, paper_id))
    db.commit()
    return jsonify({'message': 'Paper saved successfully'}), 200

@app.route('/papers/unsave', methods=['POST'])
def unsave_paper():
    data = request.get_json()
    user_id = data.get('user_id')
    paper_id = data.get('paper_id')
    db = get_db()
    
    # Check if the paper exists before attempting to delete
    result = db.execute('DELETE FROM user_saved_papers WHERE user_id = ? AND paper_id = ?', (user_id, paper_id))
    db.commit()
    
    if result.rowcount > 0:
        return jsonify({'message': 'Paper unsaved successfully'}), 200
    else:
        return jsonify({'message': 'Paper not found or already unsaved'}), 404

@app.route('/papers/saved')
def saved():
    user_id = request.cookies.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    db = get_db()
    papers = db.execute('SELECT * FROM papers WHERE id IN (SELECT paper_id FROM user_saved_papers WHERE user_id = ?)', (user_id,)).fetchall()
    return render_template('saved.html', papers=papers, page_title="Saved Papers")

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()