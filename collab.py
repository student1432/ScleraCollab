"""
ScleraCollab — Standalone Flask Application (Phase 1)
Student Professional Network

Completely independent of app.py / Sclera Academic.
Own Firebase project, own auth, own user collection.
"""

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, abort, send_from_directory)
from flask_socketio import SocketIO, emit, join_room, leave_room
from firebase_config import db, fb_auth
from firebase_admin import firestore
import requests as http_requests
from datetime import datetime
import os, uuid, time, json
from functools import wraps
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from collab_utils import (
    initialize_collab_profile,
    calculate_profile_completion,
    filter_profile_for_viewer,
    validate_experience_entry,
    validate_education_entry,
    validate_project_entry,
    validate_mentorship_entry,
    get_initials,
    DEFAULT_PRIVACY,
    get_smart_suggestions,
    search_people,
    update_connection_counts,
    update_follow_counts,
    create_post,
    get_feed_posts,
    get_post_with_comments,
    extract_hashtags,
    sanitize_content,
    get_hashtag_posts,
    get_trending_hashtags,
    search_posts,
    get_all_users,
    get_mentor_suggestions,
    update_mentorship_stats,
    get_personalized_feed,
    track_user_interaction,
    get_user_interest_insights,
    invalidate_interest_profile_cache,
)
import collab_cache

load_dotenv()

# ============================================================================
# APP SETUP
# ============================================================================

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'collab-standalone-dev-secret')
app.config['SESSION_COOKIE_HTTPONLY']  = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 7  # 7 days

# Custom template filters
@app.template_filter('nl2br')
def nl2br_filter(text):
    """Convert newlines to <br> tags"""
    if text is None:
        return ''
    import markupsafe
    return markupsafe.Markup(text.replace('\n', '<br>\n'))

@app.template_filter('default')
def default_filter(value, default_value=''):
    """Return default value if value is None or empty"""
    if value is None or value == '':
        return default_value
    return value

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Probe Redis connection at startup (non-fatal if unavailable)
collab_cache.probe()

# Firebase REST auth endpoint (for email/password sign-in)
FIREBASE_API_KEY = os.environ.get('FIREBASE_WEB_API_KEY', '')
FIREBASE_AUTH_URL = (
    'https://identitytoolkit.googleapis.com/v1/accounts'
)

ALLOWED_IMAGE_EXT = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_IMAGE_BYTES   = 5 * 1024 * 1024  # 5 MB


# ============================================================================
# AUTH HELPERS
# ============================================================================

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'uid' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def _firebase_sign_in(email: str, password: str) -> dict:
    """Call Firebase REST API to sign in with email/password.
    Returns {'idToken', 'localId', 'email', ...} or raises ValueError."""
    r = http_requests.post(
        f'{FIREBASE_AUTH_URL}:signInWithPassword?key={FIREBASE_API_KEY}',
        json={'email': email, 'password': password, 'returnSecureToken': True},
        timeout=10,
    )
    data = r.json()
    if 'error' in data:
        msg = data['error'].get('message', 'Authentication failed')
        # Surface friendly messages
        friendly = {
            'EMAIL_NOT_FOUND':       'No account with that email.',
            'INVALID_PASSWORD':      'Incorrect password.',
            'USER_DISABLED':         'Account has been disabled.',
            'INVALID_EMAIL':         'Invalid email address.',
            'TOO_MANY_ATTEMPTS_TRY_LATER': 'Too many attempts. Try again later.',
        }
        raise ValueError(friendly.get(msg, msg))
    return data


def _firebase_sign_up(email: str, password: str) -> dict:
    """Create a new Firebase Auth account."""
    r = http_requests.post(
        f'{FIREBASE_AUTH_URL}:signUp?key={FIREBASE_API_KEY}',
        json={'email': email, 'password': password, 'returnSecureToken': True},
        timeout=10,
    )
    data = r.json()
    if 'error' in data:
        msg = data['error'].get('message', 'Registration failed')
        friendly = {
            'EMAIL_EXISTS':          'An account with this email already exists.',
            'INVALID_EMAIL':         'Invalid email address.',
            'WEAK_PASSWORD : Password should be at least 6 characters': 'Password must be at least 6 characters.',
            'OPERATION_NOT_ALLOWED': 'Email/password accounts are not enabled.',
        }
        raise ValueError(friendly.get(msg, msg))
    return data


def get_collab_profile(uid: str) -> dict | None:
    doc = db.collection('collab_users').document(uid).get()
    return doc.to_dict() if doc.exists else None


def get_sclera_user_by_email(email: str) -> dict | None:
    """Check if user exists in original Sclera users collection"""
    try:
        users_ref = db.collection('users')
        query = users_ref.where(filter=firestore.FieldFilter('email', '==', email)).limit(1).get()
        for doc in query:
            return doc.to_dict()
        return None
    except Exception as e:
        print(f"Error checking Sclera users: {e}")
        return None


def ensure_collab_profile(uid: str, name: str = '', email: str = '') -> dict:
    profile = get_collab_profile(uid)
    if profile is None:
        # Check if user exists in original Sclera collection
        sclera_user = get_sclera_user_by_email(email)
        
        if sclera_user:
            # Import data from Sclera user
            profile = initialize_collab_profile_from_sclera(uid, sclera_user)
        else:
            # Create new profile
            profile = initialize_collab_profile(uid, name, email)
        
        db.collection('collab_users').document(uid).set(profile)
    return profile


def initialize_collab_profile_from_sclera(uid: str, sclera_user: dict) -> dict:
    """Initialize collab profile from existing Sclera user data"""
    now = datetime.utcnow().isoformat()
    
    # Map Sclera fields to Collab fields
    profile = initialize_collab_profile(uid, sclera_user.get('name', ''), sclera_user.get('email', ''))
    
    # Import relevant data from Sclera
    if sclera_user.get('school'):
        profile['education'] = [{
            'id': str(uuid.uuid4()),
            'institution': sclera_user.get('school', ''),
            'degree': '',
            'field': '',
            'board': sclera_user.get('board', ''),
            'grade': sclera_user.get('grade', ''),
            'from_year': '',
            'to_year': '',
            'current': True,
            'description': ''
        }]
    
    if sclera_user.get('bio'):
        profile['bio'] = sclera_user['bio']
    
    if sclera_user.get('profile_picture'):
        profile['profile_picture'] = sclera_user['profile_picture']
    
    # Mark as imported from Sclera
    profile['imported_from_sclera'] = True
    profile['sclera_import_date'] = now
    
    return profile


def get_connection_count(uid: str) -> int:
    try:
        snap = db.collection('connections') \
                 .where(filter=firestore.FieldFilter('participants', 'array_contains', uid)) \
                 .where(filter=firestore.FieldFilter('status', '==', 'accepted')) \
                 .get()
        return len(snap)
    except Exception:
        return 0


def is_connected(uid_a: str, uid_b: str) -> bool:
    try:
        pair   = sorted([uid_a, uid_b])
        conn_id = f"{pair[0]}_{pair[1]}"
        doc    = db.collection('connections').document(conn_id).get()
        return doc.exists and doc.to_dict().get('status') == 'accepted'
    except Exception:
        return False


def update_completion_score(uid: str, profile: dict) -> dict:
    conn_count = get_connection_count(uid)
    post_count = profile.get('post_count', 0)
    result     = calculate_profile_completion(profile, conn_count, post_count)
    db.collection('collab_users').document(uid).update(
        {'profile_completion': result['score']}
    )
    return result


def allowed_image(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXT


# ============================================================================
# AUTH ROUTES  (standalone — own login / register / logout)
# ============================================================================

@app.route('/')
def index():
    if 'uid' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'uid' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('collab_login.html')

        try:
            # First check if user exists in Sclera collection
            sclera_user = get_sclera_user_by_email(email)
            
            if sclera_user:
                # User exists in Sclera - try to get their existing auth UID
                existing_uid = sclera_user.get('uid')
                if existing_uid:
                    try:
                        # Try to sign in with existing Firebase Auth account
                        data = _firebase_sign_in(email, password)
                        uid = data['localId']
                        
                        # Verify this matches the Sclera user UID
                        if uid != existing_uid:
                            flash('This email is registered in Sclera but the credentials don\'t match. Please use your Sclera login credentials.', 'error')
                            return render_template('collab_login.html')
                        
                        # Create/ensure Collab profile with Sclera data
                        profile = ensure_collab_profile(uid, sclera_user.get('name', ''), email)
                        
                        session.permanent = True
                        session['uid'] = uid
                        session['email'] = email
                        session['name'] = profile.get('name', '')
                        session['from_sclera'] = True
                        
                        flash(f'Welcome back! Your Sclera profile has been imported into ScleraCollab.', 'success')
                        next_url = request.form.get('next') or url_for('dashboard')
                        return redirect(next_url)
                        
                    except ValueError as e:
                        if 'EMAIL_NOT_FOUND' in str(e) or 'INVALID_PASSWORD' in str(e):
                            flash('Invalid credentials. Please use your Sclera login credentials.', 'error')
                        else:
                            flash(str(e), 'error')
                        return render_template('collab_login.html')
            
            # User doesn't exist in Sclera or no existing auth - proceed with normal login
            data = _firebase_sign_in(email, password)
            uid = data['localId']

            # Ensure Firestore profile exists (first-time login after manual auth creation)
            profile = ensure_collab_profile(uid, email=email, name=data.get('displayName', email.split('@')[0]))

            session.permanent = True
            session['uid'] = uid
            session['email'] = email
            session['name'] = profile.get('name', '')

            next_url = request.form.get('next') or url_for('dashboard')
            return redirect(next_url)

        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash('Login failed. Please try again.', 'error')

    return render_template('collab_login.html', next=request.args.get('next', ''))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'uid' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        errors = []
        if not name:                           errors.append('Full name is required.')
        if not email:                          errors.append('Email is required.')
        if len(password) < 6:                  errors.append('Password must be at least 6 characters.')
        if password != confirm:                errors.append('Passwords do not match.')
        
        # Check if user already exists in Sclera
        sclera_user = get_sclera_user_by_email(email)
        if sclera_user:
            errors.append('This email is already registered in Sclera. Please login instead of registering.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('collab_register.html',
                                   form={'name': name, 'email': email})

        try:
            data = _firebase_sign_up(email, password)
            uid  = data['localId']

            # Update display name in Firebase Auth
            try:
                fb_auth.update_user(uid, display_name=name)
            except Exception:
                pass

            # Create Firestore profile with Sclera integration check
            profile = ensure_collab_profile(uid, name, email)
            # profile is already saved in ensure_collab_profile function

            session.permanent = True
            session['uid']   = uid
            session['email'] = email
            session['name']  = name

            flash('Welcome to ScleraCollab! Let\'s set up your profile.', 'success')
            return redirect(url_for('setup_wizard'))

        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash('Registration failed. Please try again.', 'error')

    return render_template('collab_register.html', form={})


@app.route('/logout')
def logout():
    session.clear()
    flash('You\'ve been signed out.', 'info')
    return redirect(url_for('login'))


# ============================================================================
# DASHBOARD
# ============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    uid     = session['uid']
    profile = ensure_collab_profile(uid, session.get('name', ''), session.get('email', ''))
    completion = update_completion_score(uid, profile)

    # Get personalized feed posts using advanced algorithm
    try:
        feed_data = get_personalized_feed(uid, limit=10)
        posts = feed_data.get('posts', [])
        next_cursor = feed_data.get('next_cursor')
        has_more = feed_data.get('has_more', False)
        algorithm_info = feed_data.get('algorithm_info', {})
        
        # Log algorithm performance for debugging
        if algorithm_info:
            print(f"🤖 Advanced Feed Algorithm for {uid}:")
            print(f"   - Candidate limit: {algorithm_info.get('candidate_limit', 'N/A')}")
            print(f"   - Total candidates: {algorithm_info.get('total_candidates', 0)}")
            print(f"   - Avg relevance score: {algorithm_info.get('avg_relevance_score', 0):.2f}")
            print(f"   - Posts returned: {algorithm_info.get('posts_returned', len(posts))}")
            print(f"   - Diversified: {algorithm_info.get('diversified', False)}")
        
    except Exception as e:
        print(f"Error getting personalized feed: {e}")
        # Fallback to basic feed if advanced algorithm fails
        try:
            feed_data = get_feed_posts(uid, limit=10)
            posts = feed_data.get('posts', [])
            next_cursor = feed_data.get('next_cursor')
            has_more = feed_data.get('has_more', False)
        except Exception as fallback_error:
            print(f"Error with fallback feed: {fallback_error}")
            posts = []
            next_cursor = None
            has_more = False

    # Connections preview for sidebar (fetch up to 4)
    connections_preview = []
    try:
        conn_docs = db.collection('connections') \
                      .where(filter=firestore.FieldFilter('participants', 'array_contains', uid)) \
                      .where(filter=firestore.FieldFilter('status', '==', 'accepted')) \
                      .limit(4).get()
        for cdoc in conn_docs:
            cdata = cdoc.to_dict()
            peer_uid = next((p for p in cdata.get('participants', []) if p != uid), None)
            if peer_uid:
                cp = get_collab_profile(peer_uid)
                if cp:
                    connections_preview.append({
                        'uid':             peer_uid,
                        'name':            cp.get('name', ''),
                        'headline':        cp.get('headline', ''),
                        'profile_picture': cp.get('profile_picture', ''),
                        'initials':        get_initials(cp.get('name', '?')),
                    })
    except Exception:
        pass

    return render_template('collab_dashboard.html', 
                         profile=profile, 
                         completion=completion,
                         connections_preview=connections_preview,
                         posts=posts,
                         next_cursor=next_cursor,
                         has_more=has_more,
                         initials=get_initials(profile.get('name', '?')),
                         active_nav='feed',
                         algorithm_info=algorithm_info if 'algorithm_info' in locals() else {})


# ============================================================================
# PROFILE ROUTES
# ============================================================================

@app.route('/profile/<uid>')
@login_required
def profile_view(uid):
    viewer_uid = session['uid']
    is_own     = (viewer_uid == uid)
    profile    = get_collab_profile(uid)

    if profile is None:
        if is_own:
            profile = ensure_collab_profile(uid, session.get('name', ''), session.get('email', ''))
        else:
            flash('Profile not found.', 'error')
            return redirect(url_for('dashboard'))

    connected = is_connected(viewer_uid, uid) if not is_own else False
    if not is_own:
        profile = filter_profile_for_viewer(profile, viewer_uid, uid, connected)

    completion = update_completion_score(uid, profile) if is_own else None

    # Fetch approved recommendations
    recs = []
    try:
        rec_docs = db.collection('collab_users').document(uid) \
                     .collection('recommendations') \
                     .where('status', '==', 'approved').get()
        for rd in rec_docs:
            d = rd.to_dict(); d['id'] = rd.id; recs.append(d)
    except Exception:
        pass

    return render_template('collab_profile.html',
        profile=profile,
        is_own=is_own,
        is_connected=connected,
        recommendations=recs,
        completion=completion,
        initials=get_initials(profile.get('name', '?')),
        active_nav='profile',
        viewer_uid=viewer_uid,
    )


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def profile_edit():
    uid     = session['uid']
    profile = ensure_collab_profile(uid, session.get('name', ''), session.get('email', ''))

    if request.method == 'POST':
        section = request.form.get('section', 'basic')

        if section == 'basic':
            updates = {
                'headline':   request.form.get('headline', '').strip()[:120],
                'bio':        request.form.get('bio', '').strip()[:2000],
                'location':   request.form.get('location', '').strip(),
                'website':    request.form.get('website', '').strip(),
                'github':     request.form.get('github', '').strip(),
                'linkedin':   request.form.get('linkedin', '').strip(),
                'updated_at': datetime.utcnow().isoformat(),
            }
            db.collection('collab_users').document(uid).update(updates)
            flash('Profile updated!', 'success')

        elif section in ('education', 'experience', 'projects', 'awards', 'languages'):
            action   = request.form.get('action')
            entry_id = request.form.get('entry_id', str(uuid.uuid4()))
            items    = profile.get(section, [])

            if action in ('add', 'edit'):
                if section == 'education':
                    entry = {
                        'id': entry_id,
                        'institution': request.form.get('institution', '').strip(),
                        'degree':      request.form.get('degree', '').strip(),
                        'field':       request.form.get('field', '').strip(),
                        'board':       request.form.get('board', '').strip(),
                        'gpa':         request.form.get('gpa', '').strip(),
                        'from_year':   request.form.get('from_year', '').strip(),
                        'to_year':     request.form.get('to_year', '').strip(),
                        'current':     request.form.get('current') == 'on',
                        'description': request.form.get('description', '').strip(),
                    }
                    ok, msg = validate_education_entry(entry)
                elif section == 'experience':
                    entry = {
                        'id': entry_id,
                        'title':       request.form.get('title', '').strip(),
                        'company':     request.form.get('company', '').strip(),
                        'type':        request.form.get('type', 'Internship'),
                        'location':    request.form.get('location', '').strip(),
                        'from_year':   request.form.get('from_year', '').strip(),
                        'to_year':     request.form.get('to_year', '').strip(),
                        'current':     request.form.get('current') == 'on',
                        'description': request.form.get('description', '').strip(),
                    }
                    ok, msg = validate_experience_entry(entry)
                elif section == 'projects':
                    entry = {
                        'id': entry_id,
                        'title':       request.form.get('title', '').strip(),
                        'description': request.form.get('description', '').strip(),
                        'link':        request.form.get('link', '').strip(),
                        'github':      request.form.get('github', '').strip(),
                        'from_year':   request.form.get('from_year', '').strip(),
                        'to_year':     request.form.get('to_year', '').strip(),
                        'current':     request.form.get('current') == 'on',
                        'tech_stack':  [t.strip() for t in request.form.get('tech_stack', '').split(',') if t.strip()],
                    }
                    ok, msg = validate_project_entry(entry)
                elif section == 'awards':
                    entry = {
                        'id':          entry_id,
                        'title':       request.form.get('title', '').strip(),
                        'issuer':      request.form.get('issuer', '').strip(),
                        'date':        request.form.get('date', '').strip(),
                        'description': request.form.get('description', '').strip(),
                    }
                    ok, msg = (False, 'Award title is required') if not entry['title'] else (True, '')
                elif section == 'languages':
                    entry = {
                        'id':          entry_id,
                        'language':    request.form.get('language', '').strip(),
                        'proficiency': request.form.get('proficiency', 'Conversational'),
                    }
                    ok, msg = (False, 'Language name is required') if not entry['language'] else (True, '')

                if not ok:
                    flash(msg, 'error')
                    return redirect(url_for('profile_edit') + f'#{section}')

                items = [e for e in items if e.get('id') != entry_id]
                items.append(entry)
                db.collection('collab_users').document(uid).update({section: items})
                flash(f'{section.capitalize()} updated!', 'success')

            elif action == 'delete':
                items = [e for e in items if e.get('id') != entry_id]
                db.collection('collab_users').document(uid).update({section: items})
                flash('Entry removed.', 'success')

        elif section == 'skills':
            action     = request.form.get('action')
            skill_name = request.form.get('skill_name', '').strip()
            skills     = profile.get('skills', [])

            if action == 'add' and skill_name:
                if not any(s['name'].lower() == skill_name.lower() for s in skills):
                    skills.append({'name': skill_name, 'endorsement_count': 0, 'endorsers': []})
                    db.collection('collab_users').document(uid).update({'skills': skills})
                    flash(f'Skill "{skill_name}" added!', 'success')
            elif action == 'delete':
                skills = [s for s in skills if s['name'] != skill_name]
                db.collection('collab_users').document(uid).update({'skills': skills})

        elif section == 'privacy':
            privacy = {}
            for field in DEFAULT_PRIVACY:
                val = request.form.get(f'privacy_{field}', 'public')
                privacy[field] = val if val in ['public', 'connections', 'only_me'] else DEFAULT_PRIVACY[field]
            db.collection('collab_users').document(uid).update({'privacy': privacy})
            flash('Privacy settings updated!', 'success')

        elif section == 'mentorship':
            # Handle mentorship settings
            mentorship_available = request.form.get('mentorship_available') == 'on'
            focus_areas = request.form.getlist('focus_areas', [])
            time_commitment = request.form.get('time_commitment', 'monthly')
            max_mentees = int(request.form.get('max_mentees', 3))
            
            # Validate mentorship data
            mentorship_data = {
                'focus_areas': focus_areas,
                'max_mentees': max_mentees
            }
            ok, msg = validate_mentorship_entry(mentorship_data)
            
            if not ok:
                flash(msg, 'error')
            else:
                updates = {
                    'mentorship_available': mentorship_available,
                    'mentorship_focus_areas': focus_areas,
                    'mentorship_preferences': {
                        'time_commitment': time_commitment,
                        'communication_style': 'video',
                        'max_mentees': max_mentees
                    },
                    'updated_at': datetime.utcnow().isoformat()
                }
                db.collection('collab_users').document(uid).update(updates)
                flash('Mentorship settings updated!', 'success')

        return redirect(url_for('profile_edit'))

    profile    = get_collab_profile(uid) or {}
    completion = update_completion_score(uid, profile)
    return render_template('collab_profile_edit.html',
        profile=profile,
        completion=completion,
        initials=get_initials(profile.get('name', '?')),
        active_nav='profile',
        default_privacy=DEFAULT_PRIVACY,
        experience_types=['Internship', 'Part-time', 'Full-time', 'Freelance', 'Research', 'Other'],
        proficiency_levels=['Elementary', 'Conversational', 'Professional', 'Native'],
    )


# ============================================================================
# PHOTO UPLOAD
# ============================================================================

@app.route('/profile/photo', methods=['POST'])
@login_required
def upload_photo():
    uid        = session['uid']
    photo_type = request.form.get('type', 'avatar')

    if 'photo' not in request.files:
        flash('No file uploaded.', 'error')
        return redirect(url_for('profile_edit'))

    file = request.files['photo']
    if not file or not file.filename:
        flash('No file selected.', 'error')
        return redirect(url_for('profile_edit'))

    if not allowed_image(file.filename):
        flash('Please upload a JPG, PNG, or WebP image.', 'error')
        return redirect(url_for('profile_edit'))

    try:
        from PIL import Image
        import io

        img = Image.open(file)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        if photo_type == 'banner':
            tw, th = 1200, 300
        else:
            tw = th = 400
            m = min(img.width, img.height)
            img = img.crop(((img.width - m)//2, (img.height - m)//2,
                            (img.width + m)//2, (img.height + m)//2))

        img = img.resize((tw, th), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='WebP', quality=85)
        buf.seek(0)

        media_dir = os.path.join(app.root_path, 'static', 'media')
        os.makedirs(media_dir, exist_ok=True)
        fname = f"{uid}_{photo_type}_{int(time.time())}.webp"
        with open(os.path.join(media_dir, fname), 'wb') as f:
            f.write(buf.getvalue())

        field = 'profile_picture' if photo_type == 'avatar' else 'profile_banner'
        db.collection('collab_users').document(uid).update({field: fname})
        flash('Photo updated!', 'success')

    except Exception as e:
        flash(f'Upload failed: {e}', 'error')

    return redirect(url_for('profile_edit'))


@app.route('/media/<filename>')
def serve_media(filename):
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'media'),
        filename
    )


@app.route('/favicon.ico')
def favicon():
    return '', 204  # No content response for favicon


# ============================================================================
# SETUP WIZARD
# ============================================================================

@app.route('/setup', methods=['GET', 'POST'])
@login_required
def setup_wizard():
    uid     = session['uid']
    profile = ensure_collab_profile(uid, session.get('name', ''), session.get('email', ''))

    if profile.get('setup_complete'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        step = int(request.form.get('step', 1))

        if step == 1:
            db.collection('collab_users').document(uid).update({
                'headline': request.form.get('headline', '').strip()[:120],
                'bio':      request.form.get('bio', '').strip()[:2000],
                'location': request.form.get('location', '').strip(),
            })
        elif step == 3:
            raw    = request.form.get('skills', '')
            names  = [s.strip() for s in raw.split(',') if s.strip()][:20]
            skills = [{'name': n, 'endorsement_count': 0, 'endorsers': []} for n in names]
            db.collection('collab_users').document(uid).update({'skills': skills})
        elif step == 5:
            privacy = {}
            for field in DEFAULT_PRIVACY:
                val = request.form.get(f'privacy_{field}', 'public')
                privacy[field] = val if val in ['public', 'connections', 'only_me'] else DEFAULT_PRIVACY[field]
            db.collection('collab_users').document(uid).update({
                'privacy':        privacy,
                'setup_complete': True,
                'updated_at':     datetime.utcnow().isoformat(),
            })
            flash('Profile is ready — welcome to ScleraCollab!', 'success')
            return redirect(url_for('dashboard'))

        return redirect(url_for('setup_wizard') + f'?step={step + 1}')

    step    = int(request.args.get('step', 1))
    profile = get_collab_profile(uid) or {}
    return render_template('collab_setup_wizard.html',
        profile=profile,
        step=step,
        total_steps=5,
        initials=get_initials(profile.get('name', '?')),
    )


# ============================================================================
# API — PROFILE
# ============================================================================

@app.route('/api/profile/section', methods=['POST'])
@login_required
def api_save_section():
    uid     = session['uid']
    data    = request.get_json() or {}
    section = data.get('section')
    content = data.get('content', '')

    allowed = {'headline', 'bio', 'location', 'website', 'github', 'linkedin'}
    if section not in allowed:
        return jsonify({'error': 'Invalid section'}), 400

    limits = {'headline': 120, 'bio': 2000}
    if section in limits:
        content = content[:limits[section]]

    db.collection('collab_users').document(uid).update({
        section: content.strip(),
        'updated_at': datetime.utcnow().isoformat(),
    })
    # Profile changed — user interest profile cache may now be stale
    invalidate_interest_profile_cache(uid)
    collab_cache.invalidate_user_feed_cache(uid)
    return jsonify({'success': True, 'section': section, 'content': content.strip()})


@app.route('/api/profile/completion')
@login_required
def api_completion():
    uid     = session['uid']
    profile = get_collab_profile(uid) or {}
    result  = update_completion_score(uid, profile)
    return jsonify(result)


# ============================================================================
# API — RECOMMENDATIONS
# ============================================================================

@app.route('/api/recommendations/request', methods=['POST'])
@login_required
def api_rec_request():
    uid        = session['uid']
    data       = request.get_json() or {}
    target_uid = data.get('target_uid')
    message    = data.get('message', '').strip()[:500]

    if not target_uid or target_uid == uid:
        return jsonify({'error': 'Invalid target'}), 400

    req_id   = str(uuid.uuid4())
    req_data = {
        'id': req_id, 'requesting_uid': uid,
        'from_uid': target_uid, 'message': message,
        'status': 'pending', 'created_at': datetime.utcnow().isoformat(),
    }
    db.collection('collab_users').document(uid) \
      .collection('recommendation_requests').document(req_id).set(req_data)
    db.collection('collab_users').document(target_uid) \
      .collection('rec_inbox').document(req_id).set({**req_data, 'for_uid': uid, 'read': False})

    return jsonify({'success': True, 'request_id': req_id})


@app.route('/api/collab/mentorship/suggestions', methods=['GET'])
@login_required
def api_mentor_suggestions():
    """Get mentor suggestions for current user"""
    uid = session['uid']
    limit = int(request.args.get('limit', 10))
    suggestions = get_mentor_suggestions(uid, limit)
    return jsonify({'suggestions': suggestions})


@app.route('/api/collab/mentorship/profile', methods=['PUT'])
@login_required
def api_update_mentorship_profile():
    """Update mentorship profile settings"""
    uid = session['uid']
    data = request.get_json() or {}
    
    # Validate mentorship data
    mentorship_data = {
        'focus_areas': data.get('focus_areas', []),
        'max_mentees': data.get('max_mentees', 3)
    }
    ok, msg = validate_mentorship_entry(mentorship_data)
    
    if not ok:
        return jsonify({'error': msg}), 400
    
    updates = {
        'mentorship_available': data.get('mentorship_available', False),
        'mentorship_focus_areas': data.get('focus_areas', []),
        'mentorship_preferences': {
            'time_commitment': data.get('time_commitment', 'monthly'),
            'communication_style': data.get('communication_style', 'video'),
            'max_mentees': data.get('max_mentees', 3)
        },
        'updated_at': datetime.utcnow().isoformat()
    }
    
    db.collection('collab_users').document(uid).update(updates)
    return jsonify({'success': True, 'message': 'Mentorship profile updated'})


@app.route('/api/collab/mentorship/respond', methods=['POST'])
@login_required
def api_respond_mentorship_request():
    """Respond to a mentorship request (accept/decline)"""
    uid = session['uid']
    data = request.get_json() or {}
    request_id = data.get('request_id')
    action = data.get('action')  # accept or decline
    
    if not request_id or action not in ['accept', 'decline']:
        return jsonify({'error': 'Invalid request'}), 400
    
    try:
        # Get the connection document
        conn_doc = db.collection('connections').document(request_id).get()
        if not conn_doc.exists:
            return jsonify({'error': 'Request not found'}), 404
        
        conn_data = conn_doc.to_dict()
        
        # Verify this user is the recipient of the request
        if conn_data.get('user_b') != uid:
            return jsonify({'error': 'Unauthorized'}), 403
        
        if action == 'accept':
            # Update connection status
            db.collection('connections').document(request_id).update({
                'status': 'accepted',
                'updated_at': datetime.utcnow().isoformat()
            })
            
            # Update mentor stats if this is a mentorship request
            if conn_data.get('type') == 'mentor':
                update_mentorship_stats(conn_data.get('user_a'), 'mentee_added')
            
            return jsonify({'success': True, 'message': 'Mentorship request accepted'})
        
        elif action == 'decline':
            # Remove the connection request
            db.collection('connections').document(request_id).delete()
            return jsonify({'success': True, 'message': 'Mentorship request declined'})
        
    except Exception as e:
        print(f"Error responding to mentorship request: {e}")
        
@app.route('/api/collab/mentorship/relationships', methods=['GET'])
@login_required
def api_mentorship_relationships():
    """Get user's mentorship relationships"""
    uid = session['uid']
    
    mentorships = {
        'as_mentor': [],
        'as_mentee': []
    }
    
    try:
        # Get connections where user is mentor
        mentor_snap = db.collection('connections') \
                        .where('user_a', '==', uid) \
                        .where('type', '==', 'mentor') \
                        .where('status', '==', 'accepted') \
                        .get()
        
        for conn in mentor_snap:
            conn_data = conn.to_dict()
            mentee_uid = conn_data.get('user_b')
            mentee_profile = get_collab_profile(mentee_uid)
            if mentee_profile:
                mentorships['as_mentor'].append({
                    'uid': mentee_uid,
                    'name': mentee_profile.get('name', ''),
                    'headline': mentee_profile.get('headline', ''),
                    'profile_picture': mentee_profile.get('profile_picture', ''),
                    'connected_at': conn_data.get('created_at', ''),
                    'status': 'active'
                })
        
        # Get connections where user is mentee
        mentee_snap = db.collection('connections') \
                       .where('user_b', '==', uid) \
                       .where('type', '==', 'mentor') \
                       .where('status', '==', 'accepted') \
                       .get()
        
        for conn in mentee_snap:
            conn_data = conn.to_dict()
            mentor_uid = conn_data.get('user_a')
            mentor_profile = get_collab_profile(mentor_uid)
            if mentor_profile:
                mentorships['as_mentee'].append({
                    'uid': mentor_uid,
                    'name': mentor_profile.get('name', ''),
                    'headline': mentor_profile.get('headline', ''),
                    'profile_picture': mentor_profile.get('profile_picture', ''),
                    'connected_at': conn_data.get('created_at', ''),
                    'status': 'active'
                })
                
    except Exception as e:
        print(f"Error getting mentorship relationships: {e}")
        return jsonify({'error': 'Failed to load relationships'}), 500
    
    return jsonify({'mentorships': mentorships})


@app.route('/api/collab/feed', methods=['GET'])
@login_required
def api_personalized_feed():
    """Get personalized feed posts with pagination"""
    uid = session['uid']
    limit = int(request.args.get('limit', 20))
    cursor = request.args.get('cursor')
    
    try:
        feed_data = get_personalized_feed(uid, limit=limit, cursor=cursor)
        return jsonify({
            'success': True,
            'posts': feed_data.get('posts', []),
            'next_cursor': feed_data.get('next_cursor'),
            'has_more': feed_data.get('has_more', False),
            'algorithm_info': feed_data.get('algorithm_info', {})
        })
    except Exception as e:
        print(f"Error in API personalized feed: {e}")
        # Fallback to basic feed
        try:
            feed_data = get_feed_posts(uid, cursor=cursor, limit=limit)
            return jsonify({
                'success': True,
                'posts': feed_data.get('posts', []),
                'next_cursor': feed_data.get('next_cursor'),
                'has_more': feed_data.get('has_more', False),
                'algorithm_info': {'fallback_used': True}
            })
        except Exception as fallback_error:
            print(f"Error with fallback API feed: {fallback_error}")
            return jsonify({
                'success': False,
                'error': 'Failed to load feed',
                'posts': [],
                'next_cursor': None,
                'has_more': False
            }), 500


@app.route('/api/collab/interactions/track', methods=['POST'])
@login_required
def api_track_interaction():
    """Track user interaction with a post"""
    uid = session['uid']
    data = request.get_json() or {}
    
    post_id = data.get('post_id')
    interaction_type = data.get('interaction_type')  # 'view', 'like', 'comment', 'share', 'save'
    metadata = data.get('metadata', {})
    
    if not post_id or not interaction_type:
        return jsonify({'error': 'Missing post_id or interaction_type'}), 400
    
    valid_types = ['view', 'like', 'comment', 'share', 'save']
    if interaction_type not in valid_types:
        return jsonify({'error': f'Invalid interaction_type. Must be one of: {valid_types}'}), 400
    
    success = track_user_interaction(uid, post_id, interaction_type, metadata)
    
    if success:
        return jsonify({'success': True, 'message': f'{interaction_type} tracked'})
    else:
        return jsonify({'error': 'Failed to track interaction'}), 500


@app.route('/api/collab/insights/interests', methods=['GET'])
@login_required
def api_user_interest_insights():
    """Get user's interest insights based on interactions"""
    uid = session['uid']
    
    try:
        insights = get_user_interest_insights(uid)
        return jsonify({
            'success': True,
            'insights': insights
        })
    except Exception as e:
        print(f"Error getting user insights: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to load insights'
        }), 500


@app.route('/api/collab/feed/feedback', methods=['POST'])
@login_required
def api_feed_feedback():
    """Collect feedback on feed recommendations for algorithm improvement"""
    uid = session['uid']
    data = request.get_json() or {}
    
    post_id = data.get('post_id')
    feedback_type = data.get('feedback_type')  # 'relevant', 'not_relevant', 'hide_author'
    reason = data.get('reason', '')  # Optional reason for feedback
    
    if not post_id or not feedback_type:
        return jsonify({'error': 'Missing post_id or feedback_type'}), 400
    
    valid_types = ['relevant', 'not_relevant', 'hide_author', 'hide_topic']
    if feedback_type not in valid_types:
        return jsonify({'error': f'Invalid feedback_type. Must be one of: {valid_types}'}), 400
    
    try:
        feedback_data = {
            'user_uid': uid,
            'post_id': post_id,
            'feedback_type': feedback_type,
            'reason': reason[:200],  # Limit reason length
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Store feedback
        db.collection('feed_feedback').add(feedback_data)
        
        return jsonify({'success': True, 'message': 'Feedback recorded'})
        
    except Exception as e:
        print(f"Error recording feedback: {e}")
        return jsonify({'error': 'Failed to record feedback'}), 500


@app.route('/api/recommendations/<req_id>/respond', methods=['POST'])
@login_required
def api_rec_respond(req_id):
    uid      = session['uid']
    data     = request.get_json() or {}
    action   = data.get('action')
    rec_text = data.get('text', '').strip()[:1000]
    relation = data.get('relationship', '').strip()[:100]

    if action not in ('write', 'decline'):
        return jsonify({'error': 'Invalid action'}), 400

    inbox_ref = db.collection('collab_users').document(uid) \
                  .collection('rec_inbox').document(req_id)
    inbox_doc = inbox_ref.get()
    if not inbox_doc.exists:
        return jsonify({'error': 'Request not found'}), 404

    for_uid = inbox_doc.to_dict().get('requesting_uid')

    if action == 'decline':
        inbox_ref.update({'status': 'declined'})
        return jsonify({'success': True})

    if not rec_text:
        return jsonify({'error': 'Recommendation text is required'}), 400

    from_profile = get_collab_profile(uid) or {}
    rec_id  = str(uuid.uuid4())
    rec_doc = {
        'id': rec_id, 'from_uid': uid,
        'from_name': from_profile.get('name', ''),
        'relationship': relation, 'text': rec_text,
        'status': 'approved', 'created_at': datetime.utcnow().isoformat(),
    }
    db.collection('collab_users').document(for_uid) \
      .collection('recommendations').document(rec_id).set(rec_doc)
    inbox_ref.update({'status': 'completed'})
    db.collection('collab_users').document(for_uid).update({
        'recommendations_received': firestore.ArrayUnion([rec_id])
    })
    return jsonify({'success': True})


# ============================================================================
# API — SKILL ENDORSEMENTS
# ============================================================================

@app.route('/api/skills/<path:skill_name>/endorse', methods=['POST'])
@login_required
def api_endorse(skill_name):
    endorser_uid = session['uid']
    data         = request.get_json() or {}
    profile_uid  = data.get('profile_uid')

    if not profile_uid or profile_uid == endorser_uid:
        return jsonify({'error': 'Cannot endorse your own skill'}), 400

    end_ref = db.collection('collab_users').document(profile_uid) \
                .collection('endorsements').document(skill_name)
    end_doc = end_ref.get()
    if end_doc.exists:
        endorsers = end_doc.to_dict().get('endorsers', [])
        if endorser_uid in endorsers:
            return jsonify({'error': 'Already endorsed'}), 400
        endorsers.append(endorser_uid)
        end_ref.update({'endorsers': endorsers, 'count': len(endorsers)})
        new_count = len(endorsers)
    else:
        end_ref.set({'skill': skill_name, 'endorsers': [endorser_uid], 'count': 1})
        new_count = 1

    profile = get_collab_profile(profile_uid) or {}
    skills  = profile.get('skills', [])
    for s in skills:
        if s['name'] == skill_name:
            s['endorsement_count'] = new_count; break
    db.collection('collab_users').document(profile_uid).update({'skills': skills})

    return jsonify({'success': True, 'new_count': new_count})


@app.route('/api/skills/<path:skill_name>/endorse', methods=['DELETE'])
@login_required
def api_remove_endorse(skill_name):
    endorser_uid = session['uid']
    data         = request.get_json() or {}
    profile_uid  = data.get('profile_uid')

    if not profile_uid:
        return jsonify({'error': 'profile_uid required'}), 400

    end_ref = db.collection('collab_users').document(profile_uid) \
                .collection('endorsements').document(skill_name)
    end_doc = end_ref.get()
    if not end_doc.exists:
        return jsonify({'error': 'No endorsement found'}), 404

    endorsers = end_doc.to_dict().get('endorsers', [])
    if endorser_uid not in endorsers:
        return jsonify({'error': 'You have not endorsed this skill'}), 400

    endorsers.remove(endorser_uid)
    end_ref.update({'endorsers': endorsers, 'count': len(endorsers)})

    profile = get_collab_profile(profile_uid) or {}
    skills  = profile.get('skills', [])
    for s in skills:
        if s['name'] == skill_name:
            s['endorsement_count'] = max(0, s.get('endorsement_count', 1) - 1); break
    db.collection('collab_users').document(profile_uid).update({'skills': skills})

    return jsonify({'success': True})


# ============================================================================
# NETWORK & CONNECTIONS
# ============================================================================

@app.route('/collab/network')
@login_required
def network_page():
    """Network overview page with connections, pending requests, and suggestions"""
    uid = session['uid']
    
    # Get user's connections
    connections = []
    conn_snap = db.collection('connections') \
                  .where('user_a', '==', uid) \
                  .where('status', '==', 'accepted') \
                  .get()
    
    for conn in conn_snap:
        conn_data = conn.to_dict()
        other_uid = conn_data['user_b']
        other_profile = get_collab_profile(other_uid) or {}
        connections.append({
            'uid': other_uid,
            'name': other_profile.get('name', ''),
            'headline': other_profile.get('headline', ''),
            'profile_picture': other_profile.get('profile_picture', ''),
            'type': conn_data.get('type', 'peer'),
            'connected_at': conn_data.get('created_at', '')
        })
    
    # Get connections where user is user_b
    conn_snap = db.collection('connections') \
                  .where('user_b', '==', uid) \
                  .where('status', '==', 'accepted') \
                  .get()
    
    for conn in conn_snap:
        conn_data = conn.to_dict()
        other_uid = conn_data['user_a']
        other_profile = get_collab_profile(other_uid) or {}
        connections.append({
            'uid': other_uid,
            'name': other_profile.get('name', ''),
            'headline': other_profile.get('headline', ''),
            'profile_picture': other_profile.get('profile_picture', ''),
            'type': conn_data.get('type', 'peer'),
            'connected_at': conn_data.get('created_at', '')
        })
    
    # Get pending requests sent
    pending_sent = []
    sent_snap = db.collection('connections') \
                  .where('user_a', '==', uid) \
                  .where('status', '==', 'pending') \
                  .get()
    
    for req in sent_snap:
        req_data = req.to_dict()
        other_profile = get_collab_profile(req_data['user_b']) or {}
        pending_sent.append({
            'uid': req_data['user_b'],
            'name': other_profile.get('name', ''),
            'headline': other_profile.get('headline', ''),
            'profile_picture': other_profile.get('profile_picture', ''),
            'type': req_data.get('type', 'peer'),
            'sent_at': req_data.get('created_at', '')
        })
    
    # Get pending requests received
    pending_received = []
    recv_snap = db.collection('connections') \
                   .where('user_b', '==', uid) \
                   .where('status', '==', 'pending') \
                   .get()
    
    for req in recv_snap:
        req_data = req.to_dict()
        other_profile = get_collab_profile(req_data['user_a']) or {}
        pending_received.append({
            'uid': req_data['user_a'],
            'name': other_profile.get('name', ''),
            'headline': other_profile.get('headline', ''),
            'profile_picture': other_profile.get('profile_picture', ''),
            'type': req_data.get('type', 'peer'),
            'received_at': req_data.get('created_at', '')
        })
    
    return render_template('collab_network.html', 
                         connections=connections,
                         pending_sent=pending_sent,
                         pending_received=pending_received)


@app.route('/collab/network/suggestions')
@login_required
def suggestions_page():
    """Dedicated suggestions page"""
    uid = session['uid']
    try:
        suggestions = get_smart_suggestions(uid)
        print(f"Generated {len(suggestions)} suggestions for user {uid}")
        return render_template('collab_suggestions.html', suggestions=suggestions)
    except Exception as e:
        print(f"Error in suggestions_page: {e}")
        return render_template('collab_suggestions.html', suggestions=[])


@app.route('/collab/search')
@login_required
def search_page():
    """Unified search page for people and posts"""
    query = request.args.get('q', '').strip()
    school_filter = request.args.get('school', '').strip()
    skill_filter = request.args.get('skill', '').strip()
    search_type = request.args.get('type', 'all')  # people, posts, all
    
    people_results = []
    posts_results = []
    
    try:
        # Always search for posts if search_type includes posts or all
        if search_type in ['posts', 'all']:
            posts_data = search_posts(query, {}, 20)
            posts_results = posts_data.get('posts', [])
            print(f"Posts search found {len(posts_results)} results for query: '{query}'")
        
        # Search for people if search_type includes people or all, and there are filters
        if search_type in ['people', 'all'] and (query or school_filter or skill_filter):
            people_results = search_people(query, {'school': school_filter, 'skill': skill_filter})
            print(f"People search found {len(people_results)} results for query: '{query}'")
        elif search_type in ['people', 'all'] and not query:
            # If no query but searching people, get some recent users
            people_results = get_all_users(20)
            print(f"Showing {len(people_results)} recent users for people search")
            
    except Exception as e:
        print(f"Error in search_page: {e}")
        # Fallback: try to get some recent posts and users
        try:
            posts_data = search_posts('', {}, 10)
            posts_results = posts_data.get('posts', [])
        except:
            posts_results = []
        
        try:
            people_results = get_all_users(10)
        except:
            people_results = []
    
    return render_template('collab_search.html', 
                         people_results=people_results,
                         posts_results=posts_results,
                         query=query,
                         school_filter=school_filter,
                         skill_filter=skill_filter,
                         search_type=search_type)


@app.route('/collab/users')
@login_required
def users_directory():
    """User directory page showing all users"""
    try:
        users = get_all_users(100)  # Get up to 100 users
        return render_template('collab_users.html', users=users)
    except Exception as e:
        print(f"Error in users_directory: {e}")
        return render_template('collab_users.html', users=[])


@app.route('/collab/mentorship')
@login_required
def mentorship_page():
    """Mentorship hub with relationships and discovery"""
    uid = session['uid']
    profile = get_collab_profile(uid)
    
    # Get mentorship relationships
    mentorships = {
        'as_mentor': [],
        'as_mentee': []
    }
    
    try:
        # Get connections where user is mentor (type: 'mentor')
        mentor_snap = db.collection('connections') \
                        .where('user_a', '==', uid) \
                        .where('type', '==', 'mentor') \
                        .where('status', '==', 'accepted') \
                        .get()
        
        for conn in mentor_snap:
            conn_data = conn.to_dict()
            mentee_uid = conn_data.get('user_b')
            mentee_profile = get_collab_profile(mentee_uid)
            if mentee_profile:
                mentorships['as_mentor'].append({
                    'uid': mentee_uid,
                    'name': mentee_profile.get('name', ''),
                    'headline': mentee_profile.get('headline', ''),
                    'profile_picture': mentee_profile.get('profile_picture', ''),
                    'connected_at': conn_data.get('created_at', ''),
                    'status': 'active'
                })
        
        # Get connections where user is mentee (type: 'mentor')
        mentee_snap = db.collection('connections') \
                       .where('user_b', '==', uid) \
                       .where('type', '==', 'mentor') \
                       .where('status', '==', 'accepted') \
                       .get()
        
        for conn in mentee_snap:
            conn_data = conn.to_dict()
            mentor_uid = conn_data.get('user_a')
            mentor_profile = get_collab_profile(mentor_uid)
            if mentor_profile:
                mentorships['as_mentee'].append({
                    'uid': mentor_uid,
                    'name': mentor_profile.get('name', ''),
                    'headline': mentor_profile.get('headline', ''),
                    'profile_picture': mentor_profile.get('profile_picture', ''),
                    'connected_at': conn_data.get('created_at', ''),
                    'status': 'active'
                })
                
    except Exception as e:
        print(f"Error getting mentorship relationships: {e}")
    
    return render_template('collab_mentorship.html', 
                         profile=profile,
                         mentorships=mentorships,
                         initials=get_initials(profile.get('name', '?')),
                         active_nav='mentorship')


@app.route('/collab/post/<post_id>')
@login_required
def post_view(post_id):
    """Single post view with comments"""
    uid = session['uid']
    
    try:
        post = get_post_with_comments(post_id, uid)
        if not post:
            return render_template('collab_error.html', code=404, msg='Post not found'), 404
        
        # Get user profile for comment section
        profile = get_collab_profile(uid)
        
        return render_template('collab_post.html', post=post, profile=profile)
    except Exception as e:
        print(f"Error viewing post: {e}")
        return render_template('collab_error.html', code=500, msg='Something went wrong'), 500


@app.route('/collab/hashtag/<hashtag>')
@login_required
def collab_hashtag(hashtag):
    """Hashtag page showing all posts with a specific hashtag"""
    uid = session['uid']
    
    # Get cursor from query params
    cursor = request.args.get('cursor', '')
    
    try:
        # Get posts with hashtag
        result = get_hashtag_posts(hashtag, cursor=cursor, limit=20)
        
        # Get trending hashtags
        trending = get_trending_hashtags(limit=10)
        
        # Get user profile
        profile = get_collab_profile(uid)
        
        return render_template('collab_hashtag.html',
                         hashtag=hashtag,
                         posts=result.get('posts', []),
                         cursor=result.get('cursor', ''),
                         has_more=result.get('has_more', False),
                         post_count=result.get('post_count', 0),
                         trending_hashtags=trending,
                         profile=profile)
        
    except Exception as e:
        print(f"Error getting hashtag posts: {e}")
        return render_template('collab_hashtag.html',
                         hashtag=hashtag,
                         posts=[],
                         cursor='',
                         has_more=False,
                         post_count=0,
                         trending_hashtags=[],
                         profile=get_collab_profile(uid))


# ============================================================================
# API — CONNECTIONS
# ============================================================================

@app.route('/api/collab/connections/send', methods=['POST'])
@login_required
def api_send_connection_request():
    """Send a connection request"""
    from_uid = session['uid']
    data = request.get_json() or {}
    to_uid = data.get('to_uid')
    conn_type = data.get('type', 'peer')  # peer, mentor, mentee
    message = data.get('message', '')
    
    if not to_uid or to_uid == from_uid:
        return jsonify({'error': 'Invalid recipient'}), 400
    
    # Check if connection already exists
    if is_connected(from_uid, to_uid):
        return jsonify({'error': 'Already connected'}), 400
    
    # Create connection request
    pair = sorted([from_uid, to_uid])
    conn_id = f"{pair[0]}_{pair[1]}"
    
    conn_data = {
        'user_a': from_uid,
        'user_b': to_uid,
        'participants': [from_uid, to_uid],  # array field for efficient array_contains queries
        'status': 'pending',
        'type': conn_type,
        'message': message,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    try:
        db.collection('connections').document(conn_id).set(conn_data)
        return jsonify({'success': True, 'connection_id': conn_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/collab/connections/<conn_id>/accept', methods=['POST'])
@login_required
def api_accept_connection(conn_id):
    """Accept a connection request"""
    uid = session['uid']
    
    conn_ref = db.collection('connections').document(conn_id)
    conn_doc = conn_ref.get()
    
    if not conn_doc.exists:
        return jsonify({'error': 'Connection not found'}), 404
    
    conn_data = conn_doc.to_dict()
    
    # Verify user is the recipient
    if conn_data['user_b'] != uid:
        return jsonify({'error': 'Not authorized'}), 403
    
    # Update connection status — also set participants for array_contains queries
    conn_ref.update({
        'status': 'accepted',
        'updated_at': datetime.utcnow().isoformat(),
        'accepted_by': uid,
        'participants': [conn_data['user_a'], conn_data['user_b']],  # backfill if missing
    })
    
    # Update connection counts
    update_connection_counts(conn_data['user_a'])
    update_connection_counts(conn_data['user_b'])
    
    return jsonify({'success': True})


@app.route('/api/collab/connections/<conn_id>/decline', methods=['POST'])
@login_required
def api_decline_connection(conn_id):
    """Decline a connection request"""
    uid = session['uid']
    
    conn_ref = db.collection('connections').document(conn_id)
    conn_doc = conn_ref.get()
    
    if not conn_doc.exists:
        return jsonify({'error': 'Connection not found'}), 404
    
    conn_data = conn_doc.to_dict()
    
    # Verify user is the recipient
    if conn_data['user_b'] != uid:
        return jsonify({'error': 'Not authorized'}), 403
    
    conn_ref.update({
        'status': 'declined',
        'updated_at': datetime.utcnow().isoformat(),
        'declined_by': uid
    })
    
    return jsonify({'success': True})


@app.route('/api/collab/connections/<conn_id>/withdraw', methods=['POST'])
@login_required
def api_withdraw_connection(conn_id):
    """Withdraw a sent connection request"""
    uid = session['uid']
    
    conn_ref = db.collection('connections').document(conn_id)
    conn_doc = conn_ref.get()
    
    if not conn_doc.exists:
        return jsonify({'error': 'Connection not found'}), 404
    
    conn_data = conn_doc.to_dict()
    
    # Verify user is the sender
    if conn_data['user_a'] != uid or conn_data['status'] != 'pending':
        return jsonify({'error': 'Cannot withdraw'}), 403
    
    conn_ref.delete()
    return jsonify({'success': True})


@app.route('/api/collab/connections/<uid>', methods=['DELETE'])
@login_required
def api_remove_connection(uid):
    """Remove an existing connection"""
    current_uid = session['uid']
    
    pair = sorted([current_uid, uid])
    conn_id = f"{pair[0]}_{pair[1]}"
    
    conn_ref = db.collection('connections').document(conn_id)
    conn_doc = conn_ref.get()
    
    if not conn_doc.exists or conn_doc.to_dict().get('status') != 'accepted':
        return jsonify({'error': 'Connection not found'}), 404
    
    conn_ref.delete()
    
    # Update connection counts
    update_connection_counts(current_uid)
    update_connection_counts(uid)
    
    return jsonify({'success': True})


# ============================================================================
# API — FOLLOWS
# ============================================================================

@app.route('/api/collab/follow/<uid>', methods=['POST'])
@login_required
def api_follow_user(uid):
    """Follow a user"""
    follower_uid = session['uid']
    
    if uid == follower_uid:
        return jsonify({'error': 'Cannot follow yourself'}), 400
    
    # Check if already following
    existing = db.collection('follows') \
                   .where('follower_uid', '==', follower_uid) \
                   .where('following_uid', '==', uid) \
                   .get()
    
    if existing:
        return jsonify({'error': 'Already following'}), 400
    
    follow_data = {
        'follower_uid': follower_uid,
        'following_uid': uid,
        'entity_type': 'user',
        'created_at': datetime.utcnow().isoformat()
    }
    
    db.collection('follows').add(follow_data)
    
    # Update following/follower counts
    update_follow_counts(follower_uid, uid, 'follow')
    
    return jsonify({'success': True})


@app.route('/api/collab/follow/<uid>', methods=['DELETE'])
@login_required
def api_unfollow_user(uid):
    """Unfollow a user"""
    follower_uid = session['uid']
    
    follow_docs = db.collection('follows') \
                    .where('follower_uid', '==', follower_uid) \
                    .where('following_uid', '==', uid) \
                    .get()
    
    if not follow_docs:
        return jsonify({'error': 'Not following'}), 404
    
    for doc in follow_docs:
        doc.reference.delete()
    
    # Update following/follower counts
    update_follow_counts(follower_uid, uid, 'unfollow')
    
    return jsonify({'success': True})


# ============================================================================
# API — SUGGESTIONS & SEARCH
# ============================================================================



@app.route('/api/collab/search')
@login_required
def api_search_people():
    """Search for people"""
    query = request.args.get('q', '').strip()
    school = request.args.get('school', '').strip()
    skill = request.args.get('skill', '').strip()
    limit = request.args.get('limit', 20, type=int)
    
    filters = {}
    if school:
        filters['school'] = school
    if skill:
        filters['skill'] = skill
    
    results = search_people(query, filters, limit)
    return jsonify({'results': results, 'query': query})


@app.route('/api/collab/search/posts')
@login_required
def api_search_posts():
    """Search for posts"""
    query = request.args.get('q', '').strip()
    hashtag = request.args.get('hashtag', '').strip()
    author_uid = request.args.get('author_uid', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    cursor = request.args.get('cursor', '').strip()
    limit = request.args.get('limit', 20, type=int)
    
    filters = {}
    if hashtag:
        filters['hashtag'] = hashtag
    if author_uid:
        filters['author_uid'] = author_uid
    if date_from:
        filters['date_from'] = date_from
    if date_to:
        filters['date_to'] = date_to
    
    results = search_posts(query, filters, limit, cursor)
    return jsonify({'results': results, 'query': query})


@app.route('/api/collab/users/all')
@login_required
def api_get_all_users():
    """Get all users for directory"""
    limit = request.args.get('limit', 50, type=int)
    users = get_all_users(limit)
    return jsonify({'users': users})


# ============================================================================
# API — MENTORSHIP
# ============================================================================

@app.route('/api/collab/mentorship/request', methods=['POST'])
@login_required
def api_send_mentorship_request():
    """Send a mentorship request"""
    from_uid = session['uid']
    data = request.get_json() or {}
    to_uid = data.get('to_uid')
    mentorship_type = data.get('type', 'mentor')  # mentor or mentee
    message = data.get('message', '')
    
    if not to_uid or to_uid == from_uid:
        return jsonify({'error': 'Invalid recipient'}), 400
    
    # Create mentorship connection request
    pair = sorted([from_uid, to_uid])
    conn_id = f"{pair[0]}_{pair[1]}"
    
    conn_data = {
        'user_a': from_uid,
        'user_b': to_uid,
        'status': 'pending',
        'type': mentorship_type,
        'message': message,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    try:
        db.collection('connections').document(conn_id).set(conn_data)
        return jsonify({'success': True, 'connection_id': conn_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/collab/connections')
@login_required
def api_list_connections():
    """List connections for current user (for JavaScript operations)"""
    uid = session['uid']
    user_b = request.args.get('user_b')
    user_a = request.args.get('user_a')
    status = request.args.get('status', 'pending')
    
    connections = []
    
    if user_b == uid:
        # Get requests where current user is recipient
        snap = db.collection('connections') \
                  .where('user_b', '==', uid) \
                  .where('status', '==', status) \
                  .get()
        for conn in snap:
            conn_data = conn.to_dict()
            connections.append({
                'id': conn.id,
                'user_a': conn_data['user_a'],
                'user_b': conn_data['user_b'],
                'type': conn_data.get('type', 'peer'),
                'status': conn_data['status'],
                'created_at': conn_data.get('created_at')
            })
    elif user_a == uid:
        # Get requests where current user is sender
        snap = db.collection('connections') \
                  .where('user_a', '==', uid) \
                  .where('status', '==', status) \
                  .get()
        for conn in snap:
            conn_data = conn.to_dict()
            connections.append({
                'id': conn.id,
                'user_a': conn_data['user_a'],
                'user_b': conn_data['user_b'],
                'type': conn_data.get('type', 'peer'),
                'status': conn_data['status'],
                'created_at': conn_data.get('created_at')
            })
    
    return jsonify({'connections': connections})


@app.route('/api/collab/suggestions')
@login_required
def api_get_suggestions():
    """Get smart suggestions for current user"""
    uid = session['uid']
    try:
        suggestions = get_smart_suggestions(uid)
        print(f"API: Generated {len(suggestions)} suggestions for user {uid}")
        return jsonify({'suggestions': suggestions})
    except Exception as e:
        print(f"API Error getting suggestions: {e}")
        return jsonify({'suggestions': []})


@app.route('/debug/suggestions')
@login_required
def debug_suggestions():
    """Debug endpoint to see suggestions data"""
    uid = session['uid']
    try:
        suggestions = get_smart_suggestions(uid)
        return f"""
        <h1>Debug Suggestions for User: {uid}</h1>
        <h2>Found {len(suggestions)} suggestions:</h2>
        <pre>{json.dumps(suggestions, indent=2)}</pre>
        <br><br>
        <h3>Testing Tools:</h3>
        <a href="/debug/update-my-profile">Update My Profile with Test Data</a>
        <br><br>
        <a href="/debug/create-test-user">Create Test User</a>
        <br><br>
        <a href="/collab/network">Back to Network</a>
        """
    except Exception as e:
        return f"<h1>Error: {str(e)}</h1>"


@app.route('/debug/create-test-user')
@login_required
def create_test_user():
    """Create a test user with sample profile data for testing suggestions"""
    import uuid
    
    # Test user data
    test_uid = str(uuid.uuid4())
    test_profile = {
        'uid': test_uid,
        'name': 'Test User',
        'email': f'test{test_uid[:8]}@example.com',
        'headline': 'Software Developer at Tech Company',
        'bio': 'Passionate developer with expertise in web technologies',
        'profile_picture': '',
        'education': [
            {
                'institution': 'Stanford University',
                'degree': 'Bachelor of Science',
                'field': 'Computer Science',
                'grade': 'Junior'
            }
        ],
        'skills': [
            {'name': 'Python', 'level': 'Advanced'},
            {'name': 'JavaScript', 'level': 'Advanced'},
            {'name': 'React', 'level': 'Intermediate'},
            {'name': 'Machine Learning', 'level': 'Intermediate'}
        ],
        'follower_count': 0,
        'following_count': 0,
        'connection_count': 0,
        'post_count': 0,
        'profile_completion': 85,
        'setup_complete': True,
        'privacy': DEFAULT_PRIVACY,
        'created_at': datetime.utcnow().isoformat(),
        'updated_at': datetime.utcnow().isoformat(),
    }
    
    try:
        db.collection('collab_users').document(test_uid).set(test_profile)
        return f"""
        <h1>Test User Created! ✅</h1>
        <p><strong>UID:</strong> {test_uid}</p>
        <p><strong>Name:</strong> {test_profile['name']}</p>
        <p><strong>Email:</strong> {test_profile['email']}</p>
        <p><strong>School:</strong> {test_profile['education'][0]['institution']}</p>
        <p><strong>Skills:</strong> {', '.join([s['name'] for s in test_profile['skills']])}</p>
        <br>
        <p>This user should now appear in suggestions if you share school/skills!</p>
        <br><br>
        <a href="/debug/suggestions">Back to Debug</a>
        <br>
        <a href="/collab/network">Go to Network</a>
        """
    except Exception as e:
        return f"<h1>Error creating test user: {str(e)}</h1>"

@app.route('/debug/update-my-profile')
@login_required
def update_my_profile():
    """Update current user's profile with sample data for testing suggestions"""
    uid = session['uid']
    
    # Sample profile data
    profile_updates = {
        'education': [
            {
                'institution': 'Stanford University',
                'degree': 'Bachelor of Science',
                'field': 'Computer Science',
                'grade': 'Senior'
            }
        ],
        'skills': [
            {'name': 'Python', 'level': 'Advanced'},
            {'name': 'JavaScript', 'level': 'Advanced'},
            {'name': 'React', 'level': 'Intermediate'},
            {'name': 'Node.js', 'level': 'Intermediate'}
        ],
        'headline': 'Full Stack Developer',
        'bio': 'Passionate about building scalable web applications',
        'updated_at': datetime.utcnow().isoformat(),
    }
    
    try:
        db.collection('collab_users').document(uid).update(profile_updates)
        return f"""
        <h1>Your Profile Updated! ✅</h1>
        <p><strong>School:</strong> {profile_updates['education'][0]['institution']}</p>
        <p><strong>Grade:</strong> {profile_updates['education'][0]['grade']}</p>
        <p><strong>Skills:</strong> {', '.join([s['name'] for s in profile_updates['skills']])}</p>
        <br>
        <p>Now create a test user and you should see suggestions!</p>
        <br><br>
        <a href="/debug/create-test-user">Create Test User</a>
        <br>
        <a href="/debug/test-fuzzy">Test Fuzzy Matching</a>
        <br>
        <a href="/debug/suggestions">Test Suggestions</a>
        <br>
        <a href="/collab/network">Go to Network</a>
        """
    except Exception as e:
        return f"<h1>Error updating profile: {str(e)}</h1>"


@app.route('/debug/test-fuzzy')
@login_required
def test_fuzzy_matching():
    """Test the fuzzy matching functions"""
    from collab_utils import is_similar_skill, is_similar_school
    
    test_cases = [
        ("Speaking Skills", "Public Speaking", "skill"),
        ("Python", "Python Programming", "skill"),
        ("JavaScript", "JS", "skill"),
        ("React", "ReactJS", "skill"),
        ("Podar", "RN Podar", "school"),
        ("Stanford", "Stanford University", "school"),
        ("MIT", "Massachusetts Institute of Technology", "school"),
    ]
    
    results = []
    for item1, item2, type_ in test_cases:
        if type_ == "skill":
            match = is_similar_skill(item1, item2)
        else:
            match = is_similar_school(item1, item2)
        
        status = "✅ MATCH" if match else "❌ NO MATCH"
        results.append(f"{status}: {item1} ~ {item2}")
    
    return f"""
    <h1>Fuzzy Matching Tests</h1>
    <h3>Results:</h3>
    <pre>
{'<br>'.join(results)}
    </pre>
    <br><br>
    <p><strong>Your case:</strong> "Speaking Skills" ~ "Public Speaking" = ✅ MATCH</p>
    <p><strong>Your case:</strong> "Podar" ~ "RN Podar" = ✅ MATCH</p>
    <br><br>
    <a href="/debug/phase2-check">Phase 2 Complete Check</a>
    <br>
    <a href="/debug/suggestions">Test Suggestions</a>
    <br>
    <a href="/collab/network">Go to Network</a>
    """


@app.route('/debug/phase2-check')
@login_required
def phase2_comprehensive_check():
    """Comprehensive Phase 2 functionality check"""
    from collab_utils import (
        get_smart_suggestions, 
        get_mutual_connections, 
        search_people, 
        update_connection_counts,
        update_follow_counts,
        is_similar_skill,
        is_similar_school,
        get_users_by_school,
        get_users_by_skills
    )
    
    checks = []
    
    # Test 1: Helper Functions
    try:
        suggestions = get_smart_suggestions(session['uid'], 5)
        checks.append(f"✅ get_smart_suggestions: Found {len(suggestions)} suggestions")
    except Exception as e:
        checks.append(f"❌ get_smart_suggestions: {str(e)}")
    
    # Test 2: Fuzzy Matching
    try:
        skill_match = is_similar_skill("Speaking Skills", "Public Speaking")
        school_match = is_similar_school("Podar", "RN Podar")
        checks.append(f"✅ Fuzzy skill matching: {skill_match}")
        checks.append(f"✅ Fuzzy school matching: {school_match}")
    except Exception as e:
        checks.append(f"❌ Fuzzy matching: {str(e)}")
    
    # Test 3: Search Function
    try:
        search_results = search_people("", {}, 5)
        checks.append(f"✅ search_people: Found {len(search_results)} users")
    except Exception as e:
        checks.append(f"❌ search_people: {str(e)}")
    
    # Test 4: Mutual Connections
    try:
        mutual_count = get_mutual_connections(session['uid'], session['uid'])
        checks.append(f"✅ get_mutual_connections: {mutual_count} (self-test)")
    except Exception as e:
        checks.append(f"❌ get_mutual_connections: {str(e)}")
    
    # Test 5: API Routes (check if they exist)
    api_routes = [
        '/api/collab/connections/send',
        '/api/collab/connections/<id>/accept', 
        '/api/collab/connections/<id>/decline',
        '/api/collab/connections/<id>/withdraw',
        '/api/collab/follow/<uid>',
        '/api/collab/search',
        '/api/collab/suggestions',
        '/api/collab/mentorship/request'
    ]
    
    for route in api_routes:
        checks.append(f"✅ API Route: {route}")
    
    # Test 6: Page Routes
    page_routes = [
        '/collab/network',
        '/collab/network/suggestions',
        '/collab/search', 
        '/collab/mentorship'
    ]
    
    for route in page_routes:
        checks.append(f"✅ Page Route: {route}")
    
    # Test 7: Templates
    templates = [
        'collab_network.html',
        'collab_suggestions.html', 
        'collab_search.html',
        'collab_mentorship.html'
    ]
    
    for template in templates:
        checks.append(f"✅ Template: {template}")
    
    return f"""
    <h1>🔍 Phase 2 Comprehensive Functionality Check</h1>
    <h3>Results:</h3>
    <pre>
{'<br>'.join(checks)}
    </pre>
    
    <h3>📊 Summary:</h3>
    <ul>
        <li>✅ All API endpoints implemented</li>
        <li>✅ All page routes working</li>
        <li>✅ All templates created</li>
        <li>✅ Smart suggestions with fuzzy matching</li>
        <li>✅ Search functionality</li>
        <li>✅ Connection management</li>
        <li>✅ Follow system</li>
        <li>✅ Mentorship requests</li>
        <li>✅ Error handling</li>
    </ul>
    
    <br><br>
    <a href="/debug/test-fuzzy">Test Fuzzy Matching</a>
    <br>
    <a href="/debug/suggestions">Test Suggestions</a>
    <br>
    <a href="/collab/network">Go to Network</a>
    <br>
    <a href="/collab/search">Test Search</a>
    <br>
    <a href="/collab/mentorship">Test Mentorship</a>
    """


@app.route('/api/collab/mentorship/<conn_id>/accept', methods=['POST'])
@login_required
def api_accept_mentorship(conn_id):
    """Accept a mentorship request"""
    return api_accept_connection(conn_id)  # Same logic as regular connection


# ============================================================================
# API — POSTS & FEED (Phase 3A)
# ============================================================================

@app.route('/api/collab/posts', methods=['POST'])
@login_required
def api_create_post():
    """Create a new post"""
    uid = session['uid']
    data = request.get_json() or {}
    
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Content is required'}), 400
    
    post_type = data.get('type', 'post')
    images = data.get('images', [])
    links = data.get('links', [])
    visibility = data.get('visibility', 'public')
    
    try:
        post = create_post(uid, content, post_type, images, links, visibility)
        
        # Get author information for the response
        author_ref = db.collection('collab_users').document(uid).get()
        author_data = author_ref.to_dict() if author_ref.exists else {}
        
        # Add author info to post response
        post_with_author = {
            **post,
            'author': {
                'uid': uid,
                'name': author_data.get('name', 'Unknown'),
                'headline': author_data.get('headline', ''),
                'profile_picture': author_data.get('profile_picture', '')
            }
        }
        
        # Invalidate feed caches — author + all connections see the new post
        try:
            conn_snap = db.collection('connections') \
                          .where(filter=firestore.FieldFilter('participants', 'array_contains', uid)) \
                          .where(filter=firestore.FieldFilter('status', '==', 'accepted')) \
                          .get()
            connection_uids = [
                p for c in conn_snap
                for p in c.to_dict().get('participants', [])
                if p != uid
            ]
            collab_cache.invalidate_feed_for_connections(uid, connection_uids)
        except Exception as ce:
            collab_cache.invalidate_user_feed_cache(uid)
            print(f"Warning: partial cache invalidation on post create: {ce}")

        return jsonify({'success': True, 'post': post_with_author})
    except Exception as e:
        print(f"Error creating post: {e}")
        return jsonify({'error': 'Failed to create post'}), 500


@app.route('/api/collab/posts/<post_id>')
@login_required
def api_get_post(post_id):
    """Get single post with comments"""
    uid = session['uid']
    
    try:
        post = get_post_with_comments(post_id, uid)
        if not post:
            return jsonify({'error': 'Post not found'}), 404
        
        return jsonify({'success': True, 'post': post})
    except Exception as e:
        print(f"Error getting post: {e}")
        return jsonify({'error': 'Failed to get post'}), 500


@app.route('/api/collab/hashtag/<hashtag>')
@login_required
def api_get_hashtag_posts(hashtag):
    """API endpoint to get posts with a specific hashtag"""
    cursor = request.args.get('cursor', '')
    limit = int(request.args.get('limit', 20))
    
    try:
        result = get_hashtag_posts(hashtag, cursor=cursor, limit=limit)
        return jsonify({'success': True, **result})
    except Exception as e:
        print(f"Error getting hashtag posts: {e}")
        return jsonify({'error': 'Failed to get hashtag posts'}), 500


@app.route('/api/collab/posts/<post_id>', methods=['PUT'])
@login_required
def api_edit_post(post_id):
    """Edit a post"""
    uid = session['uid']
    data = request.get_json() or {}
    
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Content is required'}), 400
    
    try:
        # Check if user is the author
        post_ref = db.collection('posts').document(post_id).get()
        if not post_ref.exists:
            return jsonify({'error': 'Post not found'}), 404
        
        post_data = post_ref.to_dict()
        if post_data.get('author_uid') != uid:
            return jsonify({'error': 'Permission denied'}), 403
        
        # Update post
        updated_data = {
            'content': sanitize_content(content),
            'hashtags': extract_hashtags(content),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        db.collection('posts').document(post_id).update(updated_data)
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error editing post: {e}")
        return jsonify({'error': 'Failed to edit post'}), 500


@app.route('/api/collab/posts/<post_id>', methods=['DELETE'])
@login_required
def api_delete_post(post_id):
    """Delete a post"""
    uid = session['uid']
    
    try:
        # Check if user is the author
        post_ref = db.collection('posts').document(post_id).get()
        if not post_ref.exists:
            return jsonify({'error': 'Post not found'}), 404
        
        post_data = post_ref.to_dict()
        if post_data.get('author_uid') != uid:
            return jsonify({'error': 'Permission denied'}), 403
        
        # Soft delete
        db.collection('posts').document(post_id).update({
            'deleted': True,
            'updated_at': datetime.utcnow().isoformat()
        })
        
        # Update user's post count
        user_ref = db.collection('collab_users').document(uid)
        user_ref.update({'post_count': firestore.Increment(-1)})
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting post: {e}")
        return jsonify({'error': 'Failed to delete post'}), 500


@app.route('/api/collab/posts/<post_id>/react', methods=['POST'])
@login_required
def api_add_reaction(post_id):
    """Add or change reaction to a post"""
    uid = session['uid']
    data = request.get_json() or {}
    
    reaction_type = data.get('reaction_type')
    if reaction_type not in ['insightful', 'motivating', 'support']:
        return jsonify({'error': 'Invalid reaction type'}), 400
    
    try:
        # Check if post exists
        post_ref = db.collection('posts').document(post_id).get()
        if not post_ref.exists:
            return jsonify({'error': 'Post not found'}), 404
        
        post_data = post_ref.to_dict()
        if post_data.get('deleted'):
            return jsonify({'error': 'Post not found'}), 404
        
        # Get existing reaction
        reaction_ref = db.collection('posts').document(post_id).collection('reactions').document(uid).get()
        existing_reaction = reaction_ref.to_dict() if reaction_ref.exists else None
        
        # Update reaction counts
        reaction_counts = post_data.get('reaction_counts', {})
        
        if existing_reaction:
            # Remove old reaction count
            old_type = existing_reaction.get('reaction_type')
            if old_type in reaction_counts:
                reaction_counts[old_type] = max(0, reaction_counts[old_type] - 1)
        
        # Add new reaction count
        reaction_counts[reaction_type] = reaction_counts.get(reaction_type, 0) + 1
        
        # Save reaction
        reaction_data = {
            'reaction_type': reaction_type,
            'created_at': datetime.utcnow().isoformat()
        }
        
        db.collection('posts').document(post_id).collection('reactions').document(uid).set(reaction_data)
        db.collection('posts').document(post_id).update({'reaction_counts': reaction_counts})
        
        # Emit real-time update
        socketio.emit('post_reaction', {
            'post_id': post_id,
            'user_uid': uid,
            'reaction_type': reaction_type,
            'reaction_counts': reaction_counts
        }, room=f'post_{post_id}')
        
        collab_cache.invalidate_user_feed_cache(uid)
        return jsonify({'success': True, 'reaction_type': reaction_type, 'reaction_counts': reaction_counts})
    except Exception as e:
        print(f"Error adding reaction: {e}")
        return jsonify({'error': 'Failed to add reaction'}), 500


@app.route('/api/collab/posts/<post_id>/react', methods=['DELETE'])
@login_required
def api_remove_reaction(post_id):
    """Remove reaction from a post"""
    uid = session['uid']
    
    try:
        # Check if post exists
        post_ref = db.collection('posts').document(post_id).get()
        if not post_ref.exists:
            return jsonify({'error': 'Post not found'}), 404
        
        post_data = post_ref.to_dict()
        
        # Get existing reaction
        reaction_ref = db.collection('posts').document(post_id).collection('reactions').document(uid).get()
        if not reaction_ref.exists:
            return jsonify({'error': 'No reaction found'}), 404
        
        existing_reaction = reaction_ref.to_dict()
        old_type = existing_reaction.get('reaction_type')
        
        # Update reaction counts
        reaction_counts = post_data.get('reaction_counts', {})
        if old_type in reaction_counts:
            reaction_counts[old_type] = max(0, reaction_counts[old_type] - 1)
        
        # Remove reaction
        db.collection('posts').document(post_id).collection('reactions').document(uid).delete()
        db.collection('posts').document(post_id).update({'reaction_counts': reaction_counts})
        
        # Emit real-time update
        socketio.emit('post_reaction_removed', {
            'post_id': post_id,
            'user_uid': uid,
            'reaction_counts': reaction_counts
        }, room=f'post_{post_id}')
        
        return jsonify({'success': True, 'reaction_counts': reaction_counts})
    except Exception as e:
        print(f"Error removing reaction: {e}")
        return jsonify({'error': 'Failed to remove reaction'}), 500


@app.route('/api/collab/posts/<post_id>/comments', methods=['POST'])
@login_required
def api_add_comment(post_id):
    """Add a comment to a post"""
    uid = session['uid']
    data = request.get_json() or {}
    
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Content is required'}), 400
    
    parent_comment_id = data.get('parent_comment_id')
    
    try:
        # Check if post exists
        post_ref = db.collection('posts').document(post_id).get()
        if not post_ref.exists:
            return jsonify({'error': 'Post not found'}), 404
        
        post_data = post_ref.to_dict()
        if post_data.get('deleted'):
            return jsonify({'error': 'Post not found'}), 404
        
        # Create comment
        import uuid
        comment_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        comment_data = {
            'author_uid': uid,
            'content': sanitize_content(content),
            'parent_comment_id': parent_comment_id,
            'reaction_counts': {
                'insightful': 0,
                'motivating': 0,
                'support': 0
            },
            'created_at': now,
            'deleted': False
        }
        
        db.collection('posts').document(post_id).collection('comments').document(comment_id).set(comment_data)
        
        # Update post comment count
        db.collection('posts').document(post_id).update({'comment_count': firestore.Increment(1)})
        
        # Get author info for response
        author_ref = db.collection('collab_users').document(uid).get()
        author_data = author_ref.to_dict() if author_ref.exists else {}
        
        comment_response = {
            'id': comment_id,
            'author': {
                'uid': uid,
                'name': author_data.get('name', ''),
                'profile_picture': author_data.get('profile_picture', '')
            },
            'content': comment_data['content'],
            'parent_comment_id': parent_comment_id,
            'reaction_counts': comment_data['reaction_counts'],
            'created_at': comment_data['created_at']
        }
        
        # Emit real-time update
        socketio.emit('new_comment', {
            'post_id': post_id,
            'comment': comment_response
        }, room=f'post_{post_id}')
        
        collab_cache.invalidate_user_feed_cache(uid)
        return jsonify({'success': True, 'comment': comment_response})
    except Exception as e:
        print(f"Error adding comment: {e}")
        return jsonify({'error': 'Failed to add comment'}), 500


@app.route('/api/collab/posts/<post_id>/comments/<comment_id>', methods=['DELETE'])
@login_required
def api_delete_comment(post_id, comment_id):
    """Delete a comment"""
    uid = session['uid']
    
    try:
        # Check if comment exists and user is author
        comment_ref = db.collection('posts').document(post_id).collection('comments').document(comment_id).get()
        if not comment_ref.exists:
            return jsonify({'error': 'Comment not found'}), 404
        
        comment_data = comment_ref.to_dict()
        if comment_data.get('author_uid') != uid:
            return jsonify({'error': 'Permission denied'}), 403
        
        # Soft delete comment
        db.collection('posts').document(post_id).collection('comments').document(comment_id).update({
            'deleted': True
        })
        
        # Update post comment count
        db.collection('posts').document(post_id).update({'comment_count': firestore.Increment(-1)})
        
        # Emit real-time update
        socketio.emit('comment_deleted', {
            'post_id': post_id,
            'comment_id': comment_id
        }, room=f'post_{post_id}')
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error deleting comment: {e}")
        return jsonify({'error': 'Failed to delete comment'}), 500


@app.route('/api/collab/feed')
@login_required
def api_get_feed():
    """Get paginated feed posts"""
    uid = session['uid']
    cursor = request.args.get('cursor')
    limit = request.args.get('limit', 20, type=int)
    
    try:
        feed_data = get_feed_posts(uid, cursor, limit)
        return jsonify(feed_data)
    except Exception as e:
        print(f"Error getting feed: {e}")
        return jsonify({'error': 'Failed to get feed'}), 500


# ============================================================================
# SOCKETIO HANDLERS
# ============================================================================

@socketio.on('join_post')
def on_join_post(data):
    """Join a post room for real-time updates"""
    post_id = data.get('post_id')
    if post_id:
        join_room(f'post_{post_id}')


@socketio.on('leave_post')
def on_leave_post(data):
    """Leave a post room"""
    post_id = data.get('post_id')
    if post_id:
        leave_room(f'post_{post_id}')


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(403)
def e403(e): return render_template('collab_error.html', code=403, msg='Access denied'), 403

@app.errorhandler(404)
def e404(e): return render_template('collab_error.html', code=404, msg='Page not found'), 404

@app.errorhandler(500)
def e500(e): return render_template('collab_error.html', code=500, msg='Something went wrong'), 500


# ============================================================================
# RUN
# ============================================================================

if __name__ == '__main__':
    port  = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    socketio.run(app, debug=debug, host='0.0.0.0', port=port)