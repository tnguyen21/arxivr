from flask import Flask, render_template, g, request, jsonify, redirect, url_for, make_response
import sqlite3
from datetime import datetime

app = Flask(__name__)

DATABASE = 'papers.db'
CATEGORIES = ['cs.CL', 'cs.AI', 'cs.MA', 'cs.CV', 'cs.LG', 'cs.RO', 'cs.SY', 'cs.SI', 'cs.HC', 'cs.IR'] 

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
    offset = (page - 1) * per_page
    
    papers = db.execute('SELECT * FROM papers ORDER BY published DESC LIMIT ? OFFSET ?', (per_page, offset)).fetchall()
    
    # Format the published date for each paper
    papers = [dict(paper) for paper in papers]
    for paper in papers:
        paper['published'] = datetime.strptime(paper['published'], '%Y-%m-%dT%H:%M:%S%z').strftime('%d %b %Y')
    
    # Get total count of papers for pagination
    total_papers = db.execute('SELECT COUNT(*) as count FROM papers').fetchone()['count']
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

@app.route('/papers/save', methods=['POST'])
def save_paper():
    data = request.get_json()
    user_id = data.get('user_id')
    paper_id = data.get('paper_id')
    print("DEBUG", user_id, paper_id)
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