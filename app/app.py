'''
Semantic Retrieval System API
'''
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from datetime import datetime, timedelta, timezone
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import os
import re
import secrets
import uuid

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'postgresql://system:password@localhost:5432/system'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


def now_utc():
    return datetime.now(timezone.utc)


# Database Models

class User(db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)


class Session(db.Model):
    __tablename__ = 'sessions'

    session_id = db.Column(db.String(64), primary_key=True)
    session_exp = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: now_utc() + timedelta(days=1)
    )
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)


class Document(db.Model):
    __tablename__ = 'documents'

    document_id = db.Column(db.String(36), primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    status = db.Column(db.String(32), nullable=False, default='processing')
    page_count = db.Column(db.Integer, nullable=True)
    file_path = db.Column(db.String(512), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)


class ParagraphChunk(db.Model):
    __tablename__ = 'paragraph_chunks'

    chunk_id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.Text, nullable=False, default='[]')
    document_id = db.Column(db.String(36), db.ForeignKey('documents.document_id'), nullable=False)


# Helpers

def get_session_user():
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return None, (jsonify(error="Missing or invalid token"), 401)

    session_token = auth_header.split(' ', 1)[1]
    session = db.session.query(Session).filter_by(session_id=session_token).first()

    if not session:
        return None, (jsonify(error="Invalid credentials"), 401)

    if session.session_exp and session.session_exp < now_utc():
        return None, (jsonify(error="Session expired"), 401)

    user = db.session.query(User).filter_by(user_id=session.user_id).first()
    if not user:
        return None, (jsonify(error="Invalid credentials"), 401)

    return user, None


def split_text_into_chunks(text: str, max_chars: int = 900):
    text = text.replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text).strip()

    if not text:
        return []

    rough_paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks = []

    for paragraph in rough_paragraphs:
        if len(paragraph) <= max_chars:
            chunks.append(paragraph)
            continue

        sentences = re.split(r'(?<=[.!?])\s+', paragraph)
        current = ''

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if not current:
                current = sentence
            elif len(current) + 1 + len(sentence) <= max_chars:
                current += ' ' + sentence
            else:
                chunks.append(current)
                current = sentence

        if current:
            chunks.append(current)

    return chunks


def extract_pdf_text_and_page_count(filepath: str):
    reader = PdfReader(filepath)
    pages = reader.pages
    page_count = len(pages)

    all_text = []
    for page in pages:
        page_text = page.extract_text() or ''
        if page_text.strip():
            all_text.append(page_text)

    return '\n\n'.join(all_text), page_count


# API Endpoints

@app.route('/auth/signup', methods=['POST'])
def create_user():
    data = request.get_json() or {}

    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if username == '' or password == '':
        return jsonify(error="Username or password is empty"), 400

    existing_user = db.session.query(User).filter_by(username=username).first()
    if existing_user:
        return jsonify(error="Username already exists"), 409

    try:
        user = User(
            username=username,
            password=generate_password_hash(password)
        )

        db.session.add(user)
        db.session.commit()

        return jsonify(
            message="User created successfully",
            user_id=user.user_id
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify(error=str(e)), 500


@app.route('/auth/login', methods=['POST'])
def login_user():
    data = request.get_json() or {}

    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    get_user = db.session.query(User).filter_by(username=username).first()

    if not get_user or not check_password_hash(get_user.password, password):
        return jsonify(error="Invalid credentials"), 401

    session_token = secrets.token_urlsafe(24)

    session = Session(
        session_id=session_token,
        user_id=get_user.user_id,
        session_exp=now_utc() + timedelta(days=1)
    )

    db.session.add(session)
    db.session.commit()

    return jsonify(
        token=session_token,
        user_id=get_user.user_id
    ), 200


@app.route('/documents', methods=['POST'])
def upload_document():
    user, error_response = get_session_user()
    if error_response:
        return error_response

    if 'file' not in request.files:
        return jsonify(error="No file uploaded"), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify(error="Empty filename"), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify(error="Only PDF files are allowed"), 400

    document_id = str(uuid.uuid4())
    original_filename = secure_filename(file.filename)
    stored_filename = f"{document_id}_{original_filename}"
    filepath = os.path.join(UPLOAD_FOLDER, stored_filename)

    file.save(filepath)

    document = Document(
        document_id=document_id,
        filename=original_filename,
        status='processing',
        page_count=None,
        file_path=filepath,
        user_id=user.user_id
    )

    db.session.add(document)
    db.session.commit()

    try:
        extracted_text, page_count = extract_pdf_text_and_page_count(filepath)
        chunks = split_text_into_chunks(extracted_text)

        for chunk_text in chunks:
            db.session.add(
                ParagraphChunk(
                    text=chunk_text,
                    embedding='[]',
                    document_id=document_id
                )
            )

        document.status = 'ready'
        document.page_count = page_count
        db.session.commit()

    except Exception as exc:
        document.status = 'failed'
        db.session.commit()
        return jsonify(
            error="PDF processing failed",
            details=str(exc),
            document_id=document_id
        ), 500

    return jsonify(
        message="PDF uploaded, processing started",
        document_id=document_id,
        status=document.status
    ), 202


@app.route('/documents', methods=['GET'])
def list_documents():
    user, error_response = get_session_user()
    if error_response:
        return error_response

    documents = (
        db.session.query(Document)
        .filter_by(user_id=user.user_id)
        .order_by(Document.upload_date.desc())
        .all()
    )

    response = []
    for document in documents:
        response.append({
            "document_id": document.document_id,
            "filename": document.filename,
            "upload_date": document.upload_date.isoformat().replace('+00:00', 'Z'),
            "status": document.status,
            "page_count": document.page_count
        })

    return jsonify(response), 200


@app.route('/documents/<document_id>', methods=['DELETE'])
def delete_document(document_id):
    user, error_response = get_session_user()
    if error_response:
        return error_response

    document = (
        db.session.query(Document)
        .filter_by(document_id=document_id, user_id=user.user_id)
        .first()
    )

    if not document:
        return jsonify(error="Document not found or not owned by user"), 404

    db.session.query(ParagraphChunk).filter_by(document_id=document_id).delete()

    if document.file_path and os.path.exists(document.file_path):
        os.remove(document.file_path)

    db.session.delete(document)
    db.session.commit()

    return jsonify(
        message="Document and all associated data deleted",
        document_id=document_id
    ), 200


@app.route('/search', methods=['GET'])
def search_documents():
    user, error_response = get_session_user()
    if error_response:
        return error_response

    query = (request.args.get('q') or '').strip()
    if not query:
        return jsonify(error="Missing search query"), 400

    user_documents = (
        db.session.query(Document)
        .filter_by(user_id=user.user_id, status='ready')
        .all()
    )

    if not user_documents:
        return jsonify([]), 200

    document_map = {doc.document_id: doc for doc in user_documents}
    document_ids = list(document_map.keys())

    chunks = (
        db.session.query(ParagraphChunk)
        .filter(ParagraphChunk.document_id.in_(document_ids))
        .all()
    )

    if not chunks:
        return jsonify([]), 200

    chunk_texts = [chunk.text for chunk in chunks]
    chunk_doc_ids = [chunk.document_id for chunk in chunks]

    vectorizer = TfidfVectorizer(stop_words='english')
    matrix = vectorizer.fit_transform(chunk_texts + [query])

    chunk_vectors = matrix[:-1]
    query_vector = matrix[-1]

    scores = cosine_similarity(query_vector, chunk_vectors)[0]

    ranked = sorted(
        zip(chunk_texts, chunk_doc_ids, scores),
        key=lambda item: item[2],
        reverse=True
    )[:5]

    results = []
    for text, document_id, score in ranked:
        document = document_map[document_id]
        clipped_score = max(0.0, min(1.0, float(score)))

        results.append({
            "text": text,
            "score": round(clipped_score, 3),
            "document_id": document_id,
            "filename": document.filename
        })

    return jsonify(results), 200


# Database initialization
with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)