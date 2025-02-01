from flask import Flask, render_template, g, request, jsonify, redirect, url_for, make_response
import sqlite3, pickle, datetime
# from transformers import AutoProcessor, AutoModel

DATABASE = 'papers.db'
INDEX_FILE = 'index.pkl'
CATEGORIES = ['cs.CL', 'cs.AI', 'cs.MA', 'cs.CV', 'cs.LG', 'cs.RO', 'cs.SY', 'cs.SI', 'cs.HC', 'cs.IR'] 

vector_index, processor, model = None, None, None

def before_app_init():
    global vector_index, processor, model
    with open(INDEX_FILE, 'rb') as f:
        vector_index = pickle.load(f)
    # processor = AutoProcessor.from_pretrained("google/siglip-base-patch16-224")
    # model = AutoModel.from_pretrained("google/siglip-base-patch16-224")

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

    if category:
        papers = db.execute('SELECT id, title, author, summary, categoryabstract, strftime("%F", published) as published FROM papers WHERE category LIKE ? ORDER BY published DESC LIMIT ? OFFSET ?', ('%' + category + '%', per_page, offset)).fetchall()
        total_papers = db.execute('SELECT COUNT(*) as count FROM papers WHERE category LIKE ?', ('%' + category + '%',)).fetchone()['count']
    else:
        papers = db.execute('SELECT id, title, author, summary, category, strftime("%F", published) as published FROM papers ORDER BY published DESC LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
        total_papers = db.execute('SELECT COUNT(*) as count FROM papers').fetchone()['count']

    # Get total count of papers for pagination, considering the category filter
    total_pages = (total_papers + per_page - 1) // per_page  # Ceiling division
    return render_template('index.html', papers=papers, page=page, total_pages=total_pages, has_prev=page > 1, has_next=page < total_pages, categories=CATEGORIES)

@app.route('/about')
def about():
    db = get_db()
    current_papers_count = db.execute('SELECT COUNT(*) as count FROM papers').fetchone()['count']
    earliest_paper_indexed = db.execute('SELECT strftime("%F", MIN(published)) as earliest FROM papers').fetchone()['earliest']
    latest_paper_indexed = db.execute('SELECT strftime("%F", MAX(published)) as latest FROM papers').fetchone()['latest']
    current_time = datetime.datetime.now()
    last_24_hours = current_time - datetime.timedelta(hours=24)
    last_72_hours = current_time - datetime.timedelta(hours=72)
    last_168_hours = current_time - datetime.timedelta(hours=168)

    papers_last_24 = db.execute('SELECT COUNT(*) as count FROM papers WHERE published >= ?', (last_24_hours,)).fetchone()['count']
    papers_last_72 = db.execute('SELECT COUNT(*) as count FROM papers WHERE published >= ?', (last_72_hours,)).fetchone()['count']
    papers_last_168 = db.execute('SELECT COUNT(*) as count FROM papers WHERE published >= ?', (last_168_hours,)).fetchone()['count']
    return render_template('about.html', current_papers_count=current_papers_count, earliest_paper_indexed=earliest_paper_indexed, latest_paper_indexed=latest_paper_indexed, papers_last_24=papers_last_24, papers_last_72=papers_last_72, papers_last_168=papers_last_168)

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

# === Auth Routes ===

@app.route('/login')
def login():
    return render_template('login.html', page_title="Login")

@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('index')))
    response.set_cookie('user_id', '', expires=0)
    response.set_cookie('username', '', expires=0)
    return response

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username')
    db = get_db()
    db.execute('INSERT OR IGNORE INTO users (username) VALUES (?)', (username,))
    db.commit()
    user = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    response = make_response(jsonify({'message': 'Login successful', 'user_id': user['id'], 'username': username}), 200)
    response.set_cookie('user_id', str(user['id']))
    response.set_cookie('username', username)
    return response

# === Paper Routes ===

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
    
    sort = request.args.get('sort', 'date')
    category = request.args.get('category', None)

    if category:
        papers = db.execute('SELECT id, title, author, strftime("%F", published) as published, category, summary FROM papers WHERE id IN (SELECT paper_id FROM user_saved_papers WHERE user_id = ?) AND category LIKE ? ORDER BY published DESC', (user_id, '%' + category + '%')).fetchall()
    else:
        papers = db.execute('SELECT id, title, author, strftime("%F", published) as published, category, summary FROM papers WHERE id IN (SELECT paper_id FROM user_saved_papers WHERE user_id = ?) ORDER BY published DESC', (user_id,)).fetchall()
        papers = [dict(paper) for paper in papers]  # Convert to dict for easier date parsing
        papers.sort(key=lambda x: datetime.datetime.strptime(x['published'], '%Y-%m-%d'))
    if sort == 'date':
        papers.sort(key=lambda x: datetime.datetime.strptime(x['published'], '%Y-%m-%d'))
    elif sort == 'title':
        papers.sort(key=lambda x: x['title'])
    elif sort == 'category':
        papers.sort(key=lambda x: x['category'])
    
    return render_template('saved.html', papers=papers, page_title="Saved Papers", categories=CATEGORIES)

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
