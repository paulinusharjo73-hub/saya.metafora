import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_metafora_id'

# --- KONFIGURASI ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'metafora.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')

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
    conn.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_penulis TEXT NOT NULL,
            judul TEXT NOT NULL,
            kategori TEXT NOT NULL,
            konten TEXT NOT NULL,
            gambar TEXT,
            status TEXT DEFAULT 'published',
            tanggal_buat DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# --- ROUTES ---

@app.route('/')
def index():
    """Menampilkan artikel dengan fitur Pencarian"""
    query = request.args.get('q') # Menangkap input dari kolom pencarian
    conn = get_db_connection()
    
    if query:
        # Mencari artikel yang judul atau kontennya mirip dengan kata kunci
        posts = conn.execute(
            "SELECT * FROM articles WHERE status = 'published' AND (judul LIKE ? OR konten LIKE ?) ORDER BY tanggal_buat DESC",
            ('%' + query + '%', '%' + query + '%')
        ).fetchall()
    else:
        # Tampilan normal jika tidak ada pencarian
        posts = conn.execute("SELECT * FROM articles WHERE status = 'published' ORDER BY tanggal_buat DESC").fetchall()
    
    conn.close()
    
    # Inisialisasi session agar tidak error di HTML
    if 'my_articles' not in session:
        session['my_articles'] = []
        
    return render_template('index.html', posts=posts, search_query=query)

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
    cursor.execute('''
        INSERT INTO articles (nama_penulis, judul, kategori, konten, gambar, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (nama, judul, kategori, konten, filename, 'published'))
    
    new_id = cursor.lastrowid 
    conn.commit()
    conn.close()

    # LOGIKA KEPEMILIKAN
    if 'my_articles' not in session:
        session['my_articles'] = []
    
    my_list = list(session['my_articles'])
    my_list.append(new_id)
    session['my_articles'] = my_list
    
    return redirect(url_for('index'))

@app.route('/artikel/<int:id>')
def detail(id):
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM articles WHERE id = ?', (id,)).fetchone()
    conn.close()
    if post is None:
        return "Artikel tidak ditemukan.", 404
    return render_template('detail.html', post=post)

@app.route('/delete/<int:id>')
def delete(id):
    is_owner = id in session.get('my_articles', [])
    is_admin = session.get('is_admin', False)

    if not is_owner and not is_admin:
        return "Akses Ditolak: Anda bukan pemilik artikel ini!", 403
        
    conn = get_db_connection()
    post = conn.execute('SELECT gambar FROM articles WHERE id = ?', (id,)).fetchone()
    
    if post and post['gambar']:
        img_path = os.path.join(app.config['UPLOAD_FOLDER'], post['gambar'])
        if os.path.exists(img_path):
            try:
                os.remove(img_path)
            except:
                pass
            
    conn.execute('DELETE FROM articles WHERE id = ?', (id,))
    conn.commit()
    conn.close()

    if is_owner:
        my_list = list(session['my_articles'])
        if id in my_list:
            my_list.remove(id)
            session['my_articles'] = my_list

    return redirect(url_for('index'))

if __name__ == '__main__':
    # Menjalankan inisialisasi database saat aplikasi dimulai
    init_db()
    
    # Mengambil PORT dari environment variable (penting untuk hosting)
    # Jika tidak ada, default ke port 5000
    port = int(os.environ.get("PORT", 5000))
    
    # host='0.0.0.0' membuat web bisa diakses dari luar server hosting
    # debug=False sebaiknya dimatikan saat sudah online (Production)
    app.run(host='0.0.0.0', port=port, debug=False)