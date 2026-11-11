import os
import uuid
from datetime import datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Subject, Note, NoteView  # <--- ВОТ ОНА
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from werkzeug.middleware.proxy_fix import ProxyFix

from supabase import create_client, Client

app = Flask(__name__)
app.config.from_object(Config)

# Настройка доверия к прокси (для HTTPS)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Подключение к облаку Supabase Storage
supabase: Client = create_client(app.config.get('SUPABASE_URL'), app.config.get('SUPABASE_KEY'))


@app.before_request
def enforce_https():
    if not request.is_secure and not app.debug:
        url = request.url.replace("http://", "https://", 1)
        return redirect(url, code=301)


def enforce_https():
    if not request.is_secure and not app.debug:
        url = request.url.replace("http://", "https://", 1)
        return redirect(url, code=301)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
@app.before_request
def check_blocked_user():
    if current_user.is_authenticated and current_user.is_blocked:
        logout_user()
        flash('Ваш аккаунт заблокирован администратором', 'error')
        return redirect(url_for('login'))
def init_db():
    with app.app_context():
        db.create_all()
        if Subject.query.count() == 0:
            subjects = [
                'Биология', 'География', 'Индивидуальный проект',
                'Иностранный язык (английский язык)', 'Информатика', 'История',
                'Литература', 'Математика', 'Обществознание',
                'Основы безопасности и защиты Родины', 'Русский язык', 'Физика',
                'Физическая культура', 'Химия', 'Основы анализа и визуализации данных',
                'Основы применения искусственного интеллекта и нейронных сетей в профессиональной деятельности',
                'Основы проектного менеджмента в области аналитики и эксплуатации ИС',
                'Основы цифровых процессов, обработки данных и тестирования',
                'Основы эксплуатации и сопровождения информационных хранилищ',
                'Практическая подготовка по технологии выполнения работ по профессии Техник'
            ]
            for name in subjects:
                db.session.add(Subject(name=name))
            db.session.commit()

        if User.query.filter_by(role='admin').count() == 0:
            admin = User(username='dexldeft', password_hash=generate_password_hash('96749674'), role='admin')
            db.session.add(admin)
            db.session.commit()

@app.route('/')
def index():
    subjects = Subject.query.all()
    return render_template('index.html', subjects=subjects)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            if user.is_blocked:
                flash('Аккаунт заблокирован администратором', 'error')
            else:
                if user and check_password_hash(user.password_hash, password):
                    if user.is_blocked:
                        flash('Аккаунт заблокирован администратором', 'error')
                    else:
                        # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
                        remember = True if request.form.get('remember') else False
                        login_user(user, remember=remember)
                        # -----------------------
                        return redirect(url_for('index'))
                return redirect(url_for('index'))
        else:
            flash('Неверное имя или пароль', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm = request.form.get('password_confirm')

        if len(username) < 3:
            flash('Имя пользователя — минимум 3 символа', 'error')
        elif len(password) < 4:
            flash('Пароль — минимум 4 символа', 'error')
        elif password != confirm:
            flash('Пароли не совпадают', 'error')
        elif User.query.filter_by(username=username).first():
            flash('Это имя уже занято', 'error')
        else:
            new_user = User(username=username, password_hash=generate_password_hash(password))
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('index'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/subject/<int:subject_id>')
def subject_page(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    notes = Note.query.filter_by(subject_id=subject_id, status='approved').all()
    return render_template('subject.html', subject=subject, notes=notes)

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create_note():
    subjects = Subject.query.all()

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        subject_id = request.form.get('subject_id')
        file = request.files.get('file')

        if not title or not subject_id or not file or file.filename == '':
            flash('Заполните все обязательные поля и прикрепите файл', 'error')
            return redirect(url_for('create_note'))

        allowed = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg'}
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

        if ext not in allowed:
            flash('Недопустимый формат файла. Разрешено: PDF, DOC, DOCX, PNG, JPG', 'error')
            return redirect(url_for('create_note'))

        # Загружаем файл в облако Supabase Storage
        file_content = file.read()
        unique_filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"

        supabase.storage.from_('notes_files').upload(
            path=unique_filename,
            file=file_content,
            file_options={"content-type": file.content_type}
        )

        # Получаем публичную ссылку на файл
        file_url = supabase.storage.from_('notes_files').get_public_url(unique_filename)

        new_note = Note(
            title=title,
            description=description,
            file_path=file_url,  # <--- ИСПРАВЛЕНО: сохраняем ссылку
            file_original_name=file.filename,  # <--- ИСПРАВЛЕНО: сохраняем оригинальное имя
            subject_id=subject_id,
            author_id=current_user.id,
            status='pending'
        )
        db.session.add(new_note)
        db.session.commit()

        flash('Конспект успешно загружен и отправлен на проверку!', 'success')
        return redirect(url_for('index'))

    return render_template('create_post.html', subjects=subjects)

@app.route('/cabinet')
@login_required
def cabinet():
    my_notes = Note.query.filter_by(author_id=current_user.id).order_by(Note.created_at.desc()).all()

    viewed_notes = Note.query.join(NoteView).filter(
        NoteView.user_id == current_user.id,
        Note.author_id != current_user.id
    ).order_by(NoteView.viewed_at.desc()).limit(50).all()

    return render_template('cabinet.html', my_notes=my_notes, viewed_notes=viewed_notes)

@app.route('/note/<int:note_id>')
def view_note(note_id):
    note = Note.query.get_or_404(note_id)

    if note.status != 'approved':
        if not current_user.is_authenticated or (current_user.id != note.author_id and current_user.role != 'admin'):
            flash('У вас нет доступа к этому конспекту', 'error')
            return redirect(url_for('index'))

    if current_user.is_authenticated and current_user.id != note.author_id:
        existing_view = NoteView.query.filter_by(user_id=current_user.id, note_id=note.id).first()
        if existing_view:
            existing_view.viewed_at = datetime.now(timezone.utc)
        else:
            new_view = NoteView(user_id=current_user.id, note_id=note.id)
            db.session.add(new_view)
        db.session.commit()

    return render_template('note.html', note=note)

from flask import send_from_directory

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/delete_note/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.author_id == current_user.id:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], note.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.delete(note)
        db.session.commit()
        flash('Конспект удален', 'success')
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin_panel():
    if current_user.role != 'admin':
        flash('Доступ запрещен', 'error')
        return redirect(url_for('index'))

    pending_notes = Note.query.filter_by(status='pending').order_by(Note.created_at.desc()).all()
    return render_template('admin.html', notes=pending_notes)

@app.route('/admin/approve/<int:note_id>', methods=['POST'])
@login_required
def admin_approve(note_id):
    if current_user.role == 'admin':
        note = Note.query.get_or_404(note_id)
        note.status = 'approved'
        db.session.commit()
        flash('Конспект одобрен!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/reject/<int:note_id>', methods=['POST'])
@login_required
def admin_reject(note_id):
    if current_user.role == 'admin':
        note = Note.query.get_or_404(note_id)
        note.status = 'rejected'
        note.reject_reason = request.form.get('reason', 'Без указания причины')
        db.session.commit()
        flash('Конспект отклонен', 'error')
    return redirect(url_for('admin_panel'))

@app.route('/note/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)

    if note.author_id != current_user.id:
        flash('Вы не можете редактировать чужой конспект', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        subject_id = request.form.get('subject_id')

        if not title or not subject_id:
            flash('Тема и предмет обязательны', 'error')
            return redirect(url_for('edit_note', note_id=note.id))

        note.title = title
        note.description = description
        note.subject_id = subject_id
        note.status = 'pending'
        note.reject_reason = None
        note.updated_at = datetime.now(timezone.utc)

        db.session.commit()
        flash('Конспект обновлен и снова отправлен на проверку', 'success')
        return redirect(url_for('view_note', note_id=note.id))

    subjects = Subject.query.all()
    return render_template('edit_note.html', note=note, subjects=subjects)

@app.route('/admin/notes')
@login_required
def admin_all_notes():
    if current_user.role != 'admin': return redirect(url_for('index'))
    all_notes = Note.query.order_by(Note.created_at.desc()).all()
    return render_template('admin.html', all_notes=all_notes)

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin': return redirect(url_for('index'))
    users = User.query.all()
    return render_template('admin.html', users=users)

@app.route('/admin/delete_note/<int:note_id>', methods=['POST'])
@login_required
def admin_delete_note(note_id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    note = Note.query.get_or_404(note_id)

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], note.file_path)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(note)
    db.session.commit()
    flash('Пост удален администратором', 'success')
    return redirect(url_for('admin_all_notes'))

@app.route('/admin/toggle_block/<int:user_id>', methods=['POST'])
@login_required
def admin_toggle_block(user_id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    if user.id != current_user.id:  # Нельзя заблокировать себя
        user.is_blocked = not user.is_blocked
        db.session.commit()
        flash(f'Статус пользователя {user.username} изменен', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)

    if user.id != current_user.id:
        for note in user.notes:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], note.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)

        db.session.delete(user)
        db.session.commit()
        flash(f'Пользователь {user.username} удален', 'success')
    return redirect(url_for('admin_users'))
# Вызываем создание базы прямо при загрузке приложения
init_db()

if __name__ == '__main__':
    app.run(debug=True)