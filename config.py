import os

class Config:
        SECRET_KEY = 'konspekt-drop-super-secret-key'
        SQLALCHEMY_DATABASE_URI = 'sqlite:///konspekt.db'
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
        MAX_CONTENT_LENGTH = 16 * 1024 * 1024

        # --- НОВЫЕ СТРОКИ ДЛЯ COOKIE ---
        SESSION_COOKIE_SECURE = True  # Передавать куки только по HTTPS
        SESSION_COOKIE_HTTPONLY = True  # Запретить доступ к куки через JS
        SESSION_COOKIE_SAMESITE = 'Lax'  # Защита от CSRF-атак