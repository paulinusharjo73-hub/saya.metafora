import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_metafora_id'

# --- KONFIGURASI PATH VERCEL ---
DATABASE = '/tmp/metafora.db'
UPLOAD_FOLDER = '/tmp/uploads'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- FUNGSI DATABASE ---
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Tabel Artikel
    conn.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_penulis TEXT NOT NULL,
            judul TEXT NOT NULL,
            kategori TEXT NOT NULL,
            konten TEXT NOT NULL,
            gambar TEXT,
            status TEXT DEFAULT 'pending',
            likes INTEGER DEFAULT 0,
            tanggal_buat DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Tabel Komentar
    conn.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL,
            nama TEXT NOT NULL,
            pesan TEXT NOT NULL,
            tanggal_buat DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (article_id) REFERENCES articles (id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- ROUTES USER ---

@app.route('/')
def index():
    query = request.args.get('q')
    conn = get_db_connection()
    if query:
        posts = conn.execute(
            "SELECT * FROM articles WHERE status = 'published' AND (judul LIKE ? OR konten LIKE ?) ORDER BY tanggal_buat DESC",
            ('%' + query + '%', '%' + query + '%')
        ).fetchall()
    else:
        posts = conn.execute("SELECT * FROM articles WHERE status = 'published' ORDER BY tanggal_buat DESC").fetchall()
    conn.close()
    return render_template('index.html', posts=posts, search_query=query)

@app.route('/artikel/<int:id>')
def detail(id):
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM articles WHERE id = ?', (id,)).fetchone()
    comments = conn.execute('SELECT * FROM comments WHERE article_id = ? ORDER BY tanggal_buat DESC', (id,)).fetchall()
    conn.close()
    if post is None:
        return "Artikel tidak ditemukan.", 404
    return render_template('detail.html', post=post, comments=comments)

@app.route('/submit', methods=['POST'])
def submit():
    nama = request.form.get('nama')
    judul = request.form.get('judul')
    kategori = request.form.get('kategori')
    konten = request.form.get('konten')
    file = request.files.get('gambar')
    
    filename = None
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    conn = get_db_connection()
    cursor = conn.cursor()
    # Status 'pending' agar masuk ke menu moderasi dulu
    cursor.execute('''
        INSERT INTO articles (nama_penulis, judul, kategori, konten, gambar, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    ''', (nama, judul, kategori, konten, filename))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/like/<int:id>', methods=['POST', 'GET'])
def like_post(id):
    conn = get_db_connection()
    conn.execute('UPDATE articles SET likes = likes + 1 WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('detail', id=id))

@app.route('/comment/<int:id>', methods=['POST'])
def add_comment(id):
    nama = request.form.get('nama_komentar')
    pesan = request.form.get('pesan_komentar')
    conn = get_db_connection()
    conn.execute('INSERT INTO comments (article_id, nama, pesan) VALUES (?, ?, ?)', (id, nama, pesan))
    conn.commit()
    conn.close()
    return redirect(url_for('detail', id=id))

# --- ROUTES ADMIN ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        # Silakan ganti username & password ini
        if request.form['username'] == 'admin' and request.form['password'] == 'rahasia123':
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Login Gagal!'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    posts = conn.execute("SELECT * FROM articles WHERE status = 'pending'").fetchall()
    conn.close()
    return render_template('admin.html', posts=posts)

@app.route('/admin/verify/<int:id>')
def verify(id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute("UPDATE articles SET status = 'published' WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/delete/<int:id>')
def delete(id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM articles WHERE id = ?', (id,))
    conn.execute('DELETE FROM comments WHERE article_id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# --- EXPORT UNTUK VERCEL ---
app = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
