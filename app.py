from flask import Flask, render_template, g, request, jsonify, redirect, url_for, make_response
import sqlite3

app = Flask(__name__)

DATABASE = 'papers.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.route('/')
def index():
    db = get_db()
    papers = db.execute('SELECT * FROM papers ORDER BY published DESC LIMIT 10').fetchall()
    return render_template('index.html', papers=papers)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/login')
def login():
    return render_template('login.html')

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

@app.route('/papers/saved')
def saved():
    user_id = request.cookies.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    db = get_db()
    papers = db.execute('SELECT * FROM papers WHERE id IN (SELECT paper_id FROM user_saved_papers WHERE user_id = ?)', (user_id,)).fetchall()
    return render_template('saved.html', papers=papers)

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()