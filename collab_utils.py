"""
ScleraCollab Utilities (Standalone)
- Profile completion scoring
- Privacy helpers
- Profile schema initialiser
"""

from datetime import datetime, timedelta
import os
import uuid
import bleach
import re
import base64
import json
from firebase_config import db
from firebase_admin import firestore
import collab_cache


# ============================================================================
# AI SEMANTIC MATCHING (Sentence Transformers)
# ============================================================================
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    AI_AVAILABLE = True
    print("✅ Sentence Transformers loaded successfully")
except ImportError as e:
    AI_AVAILABLE = False
    print(f"⚠️  AI semantic matching not available: {e}")
    print("   Install with: pip install sentence-transformers scikit-learn numpy")

# HF token (optional — raises rate limit from ~1k to ~30k req/day for HF Inference API)
HF_TOKEN = os.environ.get('HF_TOKEN')
if HF_TOKEN:
    try:
        # Authenticate the HF Hub so model downloads are fast and authenticated
        from huggingface_hub import login as hf_login
        hf_login(token=HF_TOKEN, add_to_git_credential=False)
        print("✅ Hugging Face authenticated")
    except Exception:
        pass  # huggingface_hub may not be installed; sentence-transformers still works

# ── Topic labels for zero-shot classification ─────────────────────────────────
# These are LABELS for a classifier, not keyword buckets.
# The sentence-transformers model understands them semantically, so a post about
# "backpropagation gradients" correctly maps to "machine learning / AI" even
# though those exact words aren't in the label.
STUDENT_TOPIC_LABELS = [
    "programming and software development",
    "web development and frontend",
    "mobile app development",
    "data science and analytics",
    "machine learning and artificial intelligence",
    "career advice, jobs, and internships",
    "academic studies and exam preparation",
    "UI/UX and product design",
    "entrepreneurship and startups",
    "academic research and papers",
    "professional networking",
    "project showcase and demo",
    "mathematics and algorithms",
    "cloud computing and DevOps",
    "cybersecurity",
    "finance and economics",
    "biology, medicine, and health",
    "physics and engineering",
    "social sciences and humanities",
    "arts and creative work",
]

# Pre-encoded label embeddings (populated lazily, once, in-process)
_label_embeddings = None

# Global model instance (lazy loading)
_model = None
_embeddings_cache = {}
_cache_expiry = {}

def get_model():
    """Get or initialize sentence transformer model"""
    global _model
    if _model is None and AI_AVAILABLE:
        try:
            print("🤖 Loading AI model...")
            start_time = time.time()
            _model = SentenceTransformer('all-MiniLM-L6-v2', timeout=60)
            if time.time() - start_time > 30:
                print("⚠️  AI model loading took longer than expected")
            print("✅ AI Model loaded: all-MiniLM-L6-v2")
        except Exception as e:
            print(f"❌ Failed to load AI model: {e}")
            print("⚠️  Continuing without AI features...")
            _model = None
    return _model


def get_label_embeddings():
    """Return pre-encoded embeddings for STUDENT_TOPIC_LABELS (computed once).

    Encoding 20 short strings takes ~5ms after the model is loaded.
    They are cached in the module-level _label_embeddings variable so
    subsequent calls are instant.
    """
    global _label_embeddings
    if _label_embeddings is not None:
        return _label_embeddings
    model = get_model()
    if model is None:
        return None
    try:
        # Encode as natural sentences so the model understands them as descriptions
        sentences = [f"This post is about {label}" for label in STUDENT_TOPIC_LABELS]
        _label_embeddings = model.encode(sentences, convert_to_numpy=True)
        return _label_embeddings
    except Exception as e:
        print(f"❌ Failed to encode topic labels: {e}")
        return None


def classify_topics_semantic(text: str, top_k: int = 3, threshold: float = 0.22) -> list:
    """Zero-shot topic classification using sentence-transformers.

    Replaces the hardcoded keyword-bucket approach.  Works for any topic
    because the model understands semantic meaning — 'neurotech', 'UPSC prep',
    'design thinking' all map to the right labels without any keywords.

    Args:
        text:      Post content (first 512 chars used for performance).
        top_k:     Maximum number of topics to return.
        threshold: Minimum cosine similarity to include a label.
    """
    if not AI_AVAILABLE or not text:
        return []
    model = get_model()
    label_embs = get_label_embeddings()
    if model is None or label_embs is None:
        return []
    try:
        text_emb = model.encode([text[:512]], convert_to_numpy=True)
        sims = cosine_similarity(text_emb, label_embs)[0]
        results = [
            (STUDENT_TOPIC_LABELS[i], float(sims[i]))
            for i in range(len(STUDENT_TOPIC_LABELS))
            if sims[i] >= threshold
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        return [label for label, _ in results[:top_k]]
    except Exception as e:
        print(f"classify_topics_semantic error: {e}")
        return []


def classify_topics_keyword(text: str) -> list:
    """Keyword fallback when AI is unavailable.

    Broader than the original: uses partial-word matching so 'ML' matches
    'machine learning', 'dev' matches 'developer'/'DevOps', etc.
    Maps to the same STUDENT_TOPIC_LABELS vocabulary so scores are consistent.
    """
    t = text.lower()
    found = []
    patterns = {
        "programming and software development":   ['code', 'coding', 'program', 'developer', 'software', 'github', 'debug', 'function', 'class', 'object'],
        "web development and frontend":           ['web', 'html', 'css', 'javascript', 'react', 'vue', 'angular', 'frontend', 'backend', 'api', 'dom'],
        "mobile app development":                 ['mobile', 'android', 'ios', 'flutter', 'swift', 'kotlin', 'app store', 'playstore'],
        "data science and analytics":             ['data', 'analytics', 'pandas', 'numpy', 'visualization', 'dashboard', 'tableau', 'excel', 'csv'],
        "machine learning and artificial intelligence": ['ml', 'ai ', ' ai,', 'neural', 'deep learn', 'model', 'train', 'dataset', 'pytorch', 'tensorflow', 'llm', 'gpt'],
        "career advice, jobs, and internships":   ['job', 'career', 'internship', 'placement', 'interview', 'resume', 'hire', 'offer letter', 'recruit'],
        "academic studies and exam preparation":  ['study', 'exam', 'test', 'semester', 'college', 'school', 'learn', 'lecture', 'assignment', 'marks', 'grade'],
        "UI/UX and product design":               ['ui', 'ux', 'design', 'figma', 'wireframe', 'prototype', 'user experience', 'interface'],
        "entrepreneurship and startups":          ['startup', 'business', 'entrepreneur', 'founder', 'venture', 'product market', 'mvp', 'pitch'],
        "academic research and papers":           ['research', 'paper', 'thesis', 'experiment', 'publish', 'journal', 'citation', 'arxiv'],
        "mathematics and algorithms":             ['math', 'algorithm', 'complexity', 'proof', 'calculus', 'linear algebra', 'probability', 'statistics'],
        "cloud computing and DevOps":             ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'devops', 'ci/cd', 'deploy', 'cloud'],
        "cybersecurity":                          ['security', 'hack', 'ctf', 'vulnerability', 'penetration', 'encrypt', 'cyber'],
        "finance and economics":                  ['finance', 'stock', 'invest', 'economy', 'market', 'trading', 'budget', 'banking'],
    }
    for label, keywords in patterns.items():
        if any(kw in t for kw in keywords):
            found.append(label)
    return found[:4]


def get_cached_embedding(text: str):
    """Get cached embedding or compute new one"""
    if not AI_AVAILABLE or not text:
        return None
    
    cache_key = text.lower().strip()
    now = datetime.utcnow()
    
    # Check cache
    if cache_key in _embeddings_cache:
        cached_time = _cache_expiry.get(cache_key)
        if cached_time and now - cached_time < timedelta(hours=24):
            return _embeddings_cache[cache_key]
    
    # Compute new embedding
    model = get_model()
    if model is None:
        return None
    
    try:
        embedding = model.encode([text])[0]
        
        # Cache it
        _embeddings_cache[cache_key] = embedding
        _cache_expiry[cache_key] = now
        
        # Clean old cache entries periodically
        if len(_embeddings_cache) > 1000:
            clean_cache()
        
        return embedding
    except Exception as e:
        print(f"❌ Failed to compute embedding: {e}")
        return None

def clean_cache():
    """Clean expired cache entries"""
    now = datetime.utcnow()
    expired_keys = []
    
    for key, expiry_time in _cache_expiry.items():
        if now - expiry_time > timedelta(hours=24):
            expired_keys.append(key)
    
    for key in expired_keys:
        _embeddings_cache.pop(key, None)
        _cache_expiry.pop(key, None)

def get_semantic_matches(query: str, candidates: list, threshold: float = 0.3) -> list:
    """Get semantic matches using AI instead of hardcoded mapping"""
    if not AI_AVAILABLE or not query or not candidates:
        return []
    
    model = get_model()
    if model is None:
        return []
    
    try:
        # Encode query once
        query_embedding = model.encode([query], convert_to_tensor=True)
        
        # Batch encode candidates for efficiency
        if len(candidates) > 0:
            candidate_embeddings = model.encode(candidates, convert_to_tensor=True)
            
            # Calculate similarities
            similarities = cosine_similarity(query_embedding, candidate_embeddings)[0]
            
            # Return candidates with similarity scores above threshold
            scored_candidates = []
            for i, similarity in enumerate(similarities):
                if similarity > threshold:
                    scored_candidates.append({
                        'text': candidates[i],
                        'score': float(similarity)
                    })
            
            # Sort by similarity score
            scored_candidates.sort(key=lambda x: x['score'], reverse=True)
            return scored_candidates
        
        return []
    except Exception as e:
        print(f"❌ Semantic matching failed: {e}")
        return []

def is_similar_skill_ai(skill1: str, skill2: str, threshold: float = 0.7) -> bool:
    """AI-powered skill similarity matching"""
    if not skill1 or not skill2 or not AI_AVAILABLE:
        return False
    
    try:
        model = get_model()
        if model is None:
            return False
        
        embeddings = model.encode([skill1, skill2])
        similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        
        return similarity >= threshold
    except Exception as e:
        print(f"❌ AI skill matching failed: {e}")
        return False

def is_similar_school_ai(school1: str, school2: str, threshold: float = 0.8) -> bool:
    """AI-powered school name similarity matching"""
    if not school1 or not school2 or not AI_AVAILABLE:
        return False
    
    try:
        model = get_model()
        if model is None:
            return False
        
        embeddings = model.encode([school1, school2])
        similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        
        return similarity >= threshold
    except Exception as e:
        print(f"❌ AI school matching failed: {e}")
        return False

# ============================================================================
# PROFILE COMPLETION SCORING
# ============================================================================

COMPLETION_WEIGHTS = {
    'photo':              {'points': 10, 'label': 'Add a profile photo',         'section': 'photo'},
    'headline':           {'points': 10, 'label': 'Add a headline',               'section': 'basic'},
    'bio':                {'points': 10, 'label': 'Write a bio',                  'section': 'basic'},
    'education':          {'points': 15, 'label': 'Add your education',           'section': 'education'},
    'skills_min_3':       {'points': 10, 'label': 'Add at least 3 skills',        'section': 'skills'},
    'experience_or_proj': {'points': 15, 'label': 'Add experience or a project',  'section': 'experience'},
    'connections_min_5':  {'points': 10, 'label': 'Connect with 5 people',        'section': None},
    'first_post':         {'points': 10, 'label': 'Share your first post',        'section': None},
    'recommendation':     {'points': 10, 'label': 'Get a recommendation',         'section': None},
    'languages':          {'points': 5,  'label': 'Add languages you speak',      'section': 'languages'},
    'volunteer_or_award': {'points': 5,  'label': 'Add volunteer work or awards', 'section': 'volunteer'},
}

COMPLETION_MILESTONES = [
    {'threshold': 0,   'label': 'Starter',      'color': '#6b7280'},
    {'threshold': 30,  'label': 'Beginner',     'color': '#6b7280'},
    {'threshold': 50,  'label': 'Intermediate', 'color': '#f59e0b'},
    {'threshold': 70,  'label': 'Advanced',     'color': '#3b82f6'},
    {'threshold': 90,  'label': 'Expert',       'color': '#8b5cf6'},
    {'threshold': 100, 'label': 'All-Star',     'color': '#22c55e'},
]


def calculate_profile_completion(profile: dict, connection_count: int = 0,
                                  post_count: int = 0) -> dict:
    completed, missing = [], []
    checks = {
        'photo':              bool(profile.get('profile_picture')),
        'headline':           bool(str(profile.get('headline', '')).strip()),
        'bio':                bool(str(profile.get('bio', '')).strip()),
        'education':          bool(profile.get('education')),
        'skills_min_3':       len(profile.get('skills', [])) >= 3,
        'experience_or_proj': bool(profile.get('experience') or profile.get('projects')),
        'connections_min_5':  connection_count >= 5,
        'first_post':         post_count >= 1,
        'recommendation':     bool(profile.get('recommendations_received')),
        'languages':          bool(profile.get('languages')),
        'volunteer_or_award': bool(profile.get('volunteer') or profile.get('awards')),
    }
    total_score = 0
    for key, done in checks.items():
        info = COMPLETION_WEIGHTS[key]
        if done:
            completed.append(key)
            total_score += info['points']
        else:
            missing.append({'key': key, **info})

    milestone = COMPLETION_MILESTONES[0]
    for m in COMPLETION_MILESTONES:
        if total_score >= m['threshold']:
            milestone = m

    return {
        'score': min(total_score, 100),
        'milestone': milestone['label'],
        'milestone_color': milestone['color'],
        'completed': completed,
        'missing': missing,
        'next_action': missing[0] if missing else None,
    }


# ============================================================================
# PRIVACY
# ============================================================================

DEFAULT_PRIVACY = {
    'profile_picture': 'public',
    'headline':        'public',
    'bio':             'public',
    'education':       'public',
    'experience':      'connections',
    'projects':        'public',
    'skills':          'public',
    'volunteer':       'public',
    'awards':          'public',
    'languages':       'public',
    'publications':    'connections',
    'contact_info':    'connections',
    'recommendations': 'public',
}


def get_visibility(privacy: dict, section: str, viewer_uid: str,
                   profile_uid: str, is_connection: bool) -> bool:
    if viewer_uid == profile_uid:
        return True
    level = privacy.get(section, DEFAULT_PRIVACY.get(section, 'public'))
    if level == 'public':      return True
    if level == 'connections': return is_connection
    return False  # only_me


def filter_profile_for_viewer(profile: dict, viewer_uid: str,
                               profile_uid: str, is_connection: bool) -> dict:
    privacy = profile.get('privacy', DEFAULT_PRIVACY)
    always_visible = [
        'uid', 'name', 'headline', 'profile_picture', 'profile_banner',
        'follower_count', 'following_count', 'connection_count',
        'profile_completion', 'location', 'website', 'github', 'linkedin',
    ]
    filtered = {}
    for key, val in profile.items():
        if key in always_visible:
            filtered[key] = val
        elif get_visibility(privacy, key, viewer_uid, profile_uid, is_connection):
            filtered[key] = val
        else:
            filtered[key] = None
    return filtered


# ============================================================================
# PROFILE SCHEMA
# ============================================================================

def initialize_collab_profile(uid: str, name: str, email: str) -> dict:
    """Creates a blank collab_users document for a brand-new user."""
    now = datetime.utcnow().isoformat()
    return {
        'uid': uid,
        'name': name,
        'email': email,
        'headline': '',
        'bio': '',
        'profile_picture': None,
        'profile_banner': None,
        'location': '',
        'website': '',
        'github': '',
        'linkedin': '',
        'education': [],
        'experience': [],
        'volunteer': [],
        'projects': [],
        'publications': [],
        'patents': [],
        'awards': [],
        'languages': [],
        'certifications': [],
        'skills': [],
        'follower_count': 0,
        'following_count': 0,
        'connection_count': 0,
        'post_count': 0,
        'recommendations_received': [],
        'profile_completion': 0,
        'setup_complete': False,
        'privacy': DEFAULT_PRIVACY.copy(),
        'mentorship_available': False,
        'mentorship_focus_areas': [],
        'mentorship_preferences': {
            'time_commitment': 'monthly',
            'communication_style': 'video',
            'max_mentees': 3
        },
        'mentorship_stats': {
            'total_mentees': 0,
            'active_mentees': 0,
            'completed_mentorships': 0,
            'average_rating': 0
        },
        'created_at': now,
        'updated_at': now,
    }


# ============================================================================
# VALIDATORS
# ============================================================================

def validate_experience_entry(data: dict) -> tuple:
    if not data.get('title'):   return False, 'Job title is required'
    if not data.get('company'): return False, 'Company/Organization is required'
    return True, ''

def validate_education_entry(data: dict) -> tuple:
    if not data.get('institution'): return False, 'Institution name is required'
    return True, ''

def validate_project_entry(data: dict) -> tuple:
    if not data.get('title'): return False, 'Project title is required'
    return True, ''

def validate_mentorship_entry(data: dict) -> tuple:
    """Validate mentorship profile data"""
    focus_areas = data.get('focus_areas', [])
    if len(focus_areas) > 3:
        return False, 'Maximum 3 focus areas allowed'
    
    valid_focus_areas = [
        'Academic Subjects', 'Career Guidance', 'College Applications',
        'Exam Preparation', 'Skill Development', 'Programming',
        'Business & Entrepreneurship', 'Design & Creative', 'Science & Research',
        'Language Learning', 'Personal Development', 'Technology'
    ]
    
    for area in focus_areas:
        if area not in valid_focus_areas:
            return False, f'Invalid focus area: {area}'
    
    max_mentees = data.get('max_mentees', 3)
    try:
        max_mentees = int(max_mentees)
        if max_mentees < 1 or max_mentees > 10:
            return False, 'Maximum mentees must be between 1 and 10'
    except ValueError:
        return False, 'Invalid maximum mentees value'
    
    return True, ''


# ============================================================================
# DISPLAY HELPERS
# ============================================================================

def get_initials(name: str) -> str:
    parts = name.strip().split()
    if not parts:        return '?'
    if len(parts) == 1:  return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


# ============================================================================
# FUZZY MATCHING HELPERS
# ============================================================================

def is_similar_skill(skill1: str, skill2: str) -> bool:
    """AI-powered skill similarity with fallback to traditional matching"""
    if not skill1 or not skill2:
        return False
    
    # Try AI matching first
    try:
        if is_similar_skill_ai(skill1, skill2):
            return True
    except Exception as e:
        print(f"❌ AI skill matching failed: {e}")
    
    # Fallback to traditional exact/partial matching
    return traditional_skill_matching(skill1, skill2)

def traditional_skill_matching(skill1: str, skill2: str) -> bool:
    """Fallback skill matching logic"""
    skill1_lower = skill1.lower().strip()
    skill2_lower = skill2.lower().strip()
    
    # Exact match
    if skill1_lower == skill2_lower:
        return True
    
    # Partial match (one contains the other)
    if skill1_lower in skill2_lower or skill2_lower in skill1_lower:
        return len(min(skill1_lower, skill2_lower, key=len)) >= 3
    
    # Check if they share common words
    words1 = skill1_lower.split()
    words2 = skill2_lower.split()
    
    common_words = set(words1) & set(words2)
    if common_words and len(common_words) >= 1:
        return True
    
    return False


def is_similar_school(school1: str, school2: str) -> bool:
    """AI-powered school similarity with fallback to traditional matching"""
    # Handle non-string inputs
    if not isinstance(school1, str) or not isinstance(school2, str):
        return False
    
    # Try AI matching first
    try:
        if is_similar_school_ai(school1, school2):
            return True
    except Exception as e:
        print(f"❌ AI school matching failed: {e}")
    
    # Fallback to traditional matching
    return traditional_school_matching(school1, school2)

def traditional_school_matching(school1: str, school2: str) -> bool:
    """Fallback school matching logic"""
    school1_lower = school1.lower().strip()
    school2_lower = school2.lower().strip()
    
    # Skip empty strings
    if not school1_lower or not school2_lower:
        return False
    
    # Exact match
    if school1_lower == school2_lower:
        return True
    
    # Common school name variations and abbreviations
    school_mappings = {
        'podar': ['rn podar', 'r.n. podar', 'podar school', 'podar international'],
        'stanford': ['stanford university', 'stanford uni'],
        'mit': ['massachusetts institute of technology', 'massachusetts institute'],
        'harvard': ['harvard university', 'harvard uni'],
        'berkeley': ['uc berkeley', 'university of california berkeley'],
        'ucla': ['university of california los angeles'],
        'nyu': ['new york university'],
        'iit': ['indian institute of technology', 'iit delhi', 'iit bombay', 'iit madras'],
        'oxford': ['oxford university', 'university of oxford'],
        'cambridge': ['cambridge university', 'university of cambridge'],
        'yale': ['yale university'],
        'princeton': ['princeton university'],
    }
    
    # Check mappings
    for base_school, variations in school_mappings.items():
        if base_school in school1_lower and base_school in school2_lower:
            return True
        if any(var in school1_lower for var in variations) and any(var in school2_lower for var in variations):
            return True
    
    # Check for partial matches (one contains the other)
    if school1_lower in school2_lower or school2_lower in school1_lower:
        # Only if the shorter name is substantial
        shorter = min(school1_lower, school2_lower, key=len)
        if len(shorter) >= 4:
            return True
    
    # Check for common words
    words1 = school1_lower.split()
    words2 = school2_lower.split()
    
    common_words = set(words1) & set(words2)
    if common_words and len(common_words) >= 1:
        return True
    
    return False


# ============================================================================
# NETWORK & CONNECTION HELPERS
# ============================================================================

def get_smart_suggestions(uid: str, limit: int = 20) -> list:
    """Generate smart suggestions for a user based on mutual connections, school, skills"""
    suggestions = []
    
    print(f"Getting suggestions for user: {uid}")
    
    # Get user's profile for context
    user_profile = db.collection('collab_users').document(uid).get()
    if not user_profile.exists:
        print(f"User {uid} not found")
        return suggestions
    
    user_data = user_profile.to_dict()
    # Extract schools properly - handle both string and dict formats
    user_schools = []
    for edu in user_data.get('education', []):
        if isinstance(edu, str):
            if edu.strip():
                user_schools.append(edu.strip())
        elif isinstance(edu, dict):
            school = edu.get('institution', '')
            if isinstance(school, str) and school.strip():
                user_schools.append(school.strip())
            # Also check if the dict itself contains school-like data
            elif 'board' in edu or 'grade' in edu:
                # This might be a malformed education entry from migration
                pass
    
    user_skills = [skill.get('name', '') for skill in user_data.get('skills', [])]
    user_grade = None
    for edu in user_data.get('education', []):
        if isinstance(edu, dict) and edu.get('grade'):
            user_grade = edu.get('grade')
            break
    
    # Get existing connections to exclude
    existing_connections = set()
    conn_snap = db.collection('connections') \
                  .where('user_a', '==', uid) \
                  .where('status', 'in', ['pending', 'accepted']) \
                  .get()
    for conn in conn_snap:
        existing_connections.add(conn.to_dict().get('user_b'))
    
    conn_snap = db.collection('connections') \
                  .where('user_b', '==', uid) \
                  .where('status', 'in', ['pending', 'accepted']) \
                  .get()
    for conn in conn_snap:
        existing_connections.add(conn.to_dict().get('user_a'))
    
    # Get all potential candidates (limit to avoid performance issues)
    all_users = db.collection('collab_users').limit(100).get()
    print(f"Found {len(all_users)} total users in database")
    
    for user_doc in all_users:
        candidate_uid = user_doc.id
        if candidate_uid == uid or candidate_uid in existing_connections:
            continue
        
        candidate_data = user_doc.to_dict()
        score = 0
        reasons = []
        
        print(f"Evaluating candidate: {candidate_uid} - {candidate_data.get('name', 'Unknown')}")
        
        # Mutual connections scoring
        mutual_count = get_mutual_connections(uid, candidate_uid)
        if mutual_count > 0:
            score += mutual_count * 3
            reasons.append(f"{mutual_count} mutual connection{'s' if mutual_count > 1 else ''}")
            print(f"  +{mutual_count * 3} points: {mutual_count} mutual connections")
        
        # Same school scoring (with fuzzy matching)
        candidate_schools = []
        for edu in candidate_data.get('education', []):
            if isinstance(edu, str):
                if edu.strip():
                    candidate_schools.append(edu.strip())
            elif isinstance(edu, dict):
                school = edu.get('institution', '')
                if isinstance(school, str) and school.strip():
                    candidate_schools.append(school.strip())
                # Handle malformed education entries
                elif 'board' in edu or 'grade' in edu:
                    # Skip malformed entries that don't have school names
                    pass
        
        print(f"  User schools: {user_schools}")
        print(f"  Candidate schools: {candidate_schools}")
        for school in user_schools:
            for candidate_school in candidate_schools:
                if school and candidate_school and is_similar_school(school, candidate_school):
                    score += 5
                    reasons.append("Same school")
                    print(f"  +5 points: Same school ({school} ~ {candidate_school})")
                    break
            if score > 0:  # Already found a match
                break
        
        # Shared skills scoring (with fuzzy matching)
        candidate_skills = [skill.get('name', '') for skill in candidate_data.get('skills', [])]
        print(f"  User skills: {user_skills}")
        print(f"  Candidate skills: {candidate_skills}")
        
        # Fuzzy skill matching
        shared_skills = set()
        for user_skill in user_skills:
            for candidate_skill in candidate_skills:
                if user_skill.lower() == candidate_skill.lower():
                    shared_skills.add(user_skill)
                elif is_similar_skill(user_skill, candidate_skill):
                    shared_skills.add(f"{user_skill} ~ {candidate_skill}")
        
        if shared_skills:
            score += len(shared_skills) * 2
            reasons.append(f"{len(shared_skills)} shared skill{'s' if len(shared_skills) > 1 else ''}")
            print(f"  +{len(shared_skills) * 2} points: {len(shared_skills)} shared skills ({', '.join(shared_skills)})")
        
        # Same grade scoring
        candidate_grade = None
        for edu in candidate_data.get('education', []):
            if isinstance(edu, dict) and edu.get('grade'):
                candidate_grade = edu.get('grade')
                break
        print(f"  User grade: {user_grade}, Candidate grade: {candidate_grade}")
        if user_grade and candidate_grade and user_grade == candidate_grade:
            score += 1
            reasons.append("Same grade")
            print(f"  +1 point: Same grade ({user_grade})")
        
        print(f"  Final score: {score}, Reasons: {reasons}")
        
        if score > 0:
            suggestions.append({
                'uid': candidate_uid,
                'name': candidate_data.get('name', ''),
                'headline': candidate_data.get('headline', ''),
                'profile_picture': candidate_data.get('profile_picture', ''),
                'score': score,
                'reasons': reasons[:2],  # Limit to top 2 reasons
                'mutual_connections': mutual_count
            })
        else:
            print(f"  ❌ Skipped: Score 0 (no matching criteria)")
    
    # Sort by score and return top suggestions
    suggestions.sort(key=lambda x: x['score'], reverse=True)
    final_suggestions = suggestions[:limit]
    print(f"Returning {len(final_suggestions)} suggestions")
    return final_suggestions


def get_mutual_connections(uid_a: str, uid_b: str) -> int:
    """Count mutual connections between two users"""
    try:
        # Get connections for user A
        conn_a = set()
        snap = db.collection('connections') \
                 .where('user_a', '==', uid_a) \
                 .where('status', '==', 'accepted') \
                 .get()
        for conn in snap:
            conn_a.add(conn.to_dict().get('user_b'))
        
        snap = db.collection('connections') \
                 .where('user_b', '==', uid_a) \
                 .where('status', '==', 'accepted') \
                 .get()
        for conn in snap:
            conn_a.add(conn.to_dict().get('user_a'))
        
        # Get connections for user B
        conn_b = set()
        snap = db.collection('connections') \
                 .where('user_a', '==', uid_b) \
                 .where('status', '==', 'accepted') \
                 .get()
        for conn in snap:
            conn_b.add(conn.to_dict().get('user_b'))
        
        snap = db.collection('connections') \
                 .where('user_b', '==', uid_b) \
                 .where('status', '==', 'accepted') \
                 .get()
        for conn in snap:
            conn_b.add(conn.to_dict().get('user_a'))
        
        # Return intersection
        return len(conn_a & conn_b)
    except Exception as e:
        print(f"Error getting mutual connections: {e}")
        return 0


def search_people(query: str, filters: dict = {}, limit: int = 20) -> list:
    """Search for people by name, school, skills"""
    results = []
    
    # Get all users (in production, this should use proper search indexing)
    users_snap = db.collection('collab_users').limit(limit * 3).get()
    
    for user_doc in users_snap:
        user_data = user_doc.to_dict()
        uid = user_doc.id
        
        # Skip if no name
        name = user_data.get('name', '').lower()
        if not name:
            continue
        
        match_score = 0
        match_reasons = []
        
        # Name matching
        if query and query.lower() in name:
            match_score += 10
            match_reasons.append("Name match")
        
        # School filter
        if filters.get('school'):
            schools = [edu.get('institution', '').lower() for edu in user_data.get('education', [])]
            if filters['school'].lower() in str(schools):
                match_score += 5
                match_reasons.append("School match")
        
        # Skill filter
        if filters.get('skill'):
            skills = [skill.get('name', '').lower() for skill in user_data.get('skills', [])]
            if filters['skill'].lower() in str(skills):
                match_score += 3
                match_reasons.append("Skill match")
        
        # General query matching in headline/bio
        if query and query.lower() not in name:
            headline = user_data.get('headline', '').lower()
            bio = user_data.get('bio', '').lower()
            if query.lower() in headline:
                match_score += 2
                match_reasons.append("Headline match")
            elif query.lower() in bio:
                match_score += 1
                match_reasons.append("Bio match")
        
        if match_score > 0:
            results.append({
                'uid': uid,
                'name': user_data.get('name', ''),
                'headline': user_data.get('headline', ''),
                'profile_picture': user_data.get('profile_picture', ''),
                'match_score': match_score,
                'match_reasons': match_reasons,
                'education': user_data.get('education', [])[:1],  # First education only
                'skills': user_data.get('skills', [])[:3]  # Top 3 skills
            })
    
    # Sort by match score
    results.sort(key=lambda x: x['match_score'], reverse=True)
    return results[:limit]


def update_connection_counts(uid: str):
    """Update connection count in user profile"""
    try:
        count = 0
        snap = db.collection('connections') \
                 .where('user_a', '==', uid) \
                 .where('status', '==', 'accepted') \
                 .get()
        count += len(snap)
        
        snap = db.collection('connections') \
                 .where('user_b', '==', uid) \
                 .where('status', '==', 'accepted') \
                 .get()
        count += len(snap)
        
        db.collection('collab_users').document(uid).update({
            'connection_count': count,
            'updated_at': datetime.utcnow().isoformat()
        })
    except Exception:
        pass


def update_follow_counts(follower_uid: str, following_uid: str, action: str):
    """Update follower/following counts"""
    try:
        if action == 'follow':
            # Increment following count for follower
            db.collection('collab_users').document(follower_uid).update({
                'following_count': firestore.Increment(1)
            })
            # Increment follower count for following
            db.collection('collab_users').document(following_uid).update({
                'follower_count': firestore.Increment(1)
            })
        elif action == 'unfollow':
            # Decrement following count for follower
            db.collection('collab_users').document(follower_uid).update({
                'following_count': firestore.Increment(-1)
            })
            # Decrement follower count for following
            db.collection('collab_users').document(following_uid).update({
                'follower_count': firestore.Increment(-1)
            })
    except Exception:
        pass


def get_users_by_school(school: str, limit: int = 20) -> list:
    """Get users by school name"""
    users = []
    school_lower = school.lower()
    
    users_snap = db.collection('collab_users').limit(limit * 2).get()
    
    for user_doc in users_snap:
        user_data = user_doc.to_dict()
        education = user_data.get('education', [])
        
        for edu in education:
            if school_lower in edu.get('institution', '').lower():
                users.append({
                    'uid': user_doc.id,
                    'name': user_data.get('name', ''),
                    'headline': user_data.get('headline', ''),
                    'profile_picture': user_data.get('profile_picture', ''),
                    'education': edu
                })
                break
    
    return users[:limit]


def get_users_by_skills(skills: list, limit: int = 20) -> list:
    """Get users by skill names"""
    users = []
    skills_lower = [s.lower() for s in skills]
    
    # Get all users and filter by skills (with fuzzy matching)
    try:
        all_users = db.collection('collab_users').limit(50).get()
        
        for user_doc in all_users:
            user_data = user_doc.to_dict()
            user_skills = [skill.get('name', '').lower() for skill in user_data.get('skills', [])]
            
            # Check if user has any of the requested skills
            for skill_lower in skills_lower:
                for user_skill in user_skills:
                    if skill_lower in user_skill or user_skill in skill_lower:
                        users.append({
                            'uid': user_doc.id,
                            'name': user_data.get('name', ''),
                            'headline': user_data.get('headline', ''),
                            'profile_picture': user_data.get('profile_picture', ''),
                            'skills': user_data.get('skills', [])
                        })
                        break
                if len(users) >= limit:
                    return users[:limit]
                    
    except Exception as e:
        print(f"Error getting users by skills: {e}")
    
    return users[:limit]


# ============================================================================
# POST & FEED HELPERS
# ============================================================================

def extract_hashtags(text: str) -> list:
    """Extract hashtags from text"""
    import re
    hashtags = re.findall(r'#(\w+)', text)
    return list(set(hashtags))  # Remove duplicates


def sanitize_content(content: str) -> str:
    """Sanitize user content for security"""
    import bleach
    # Allow basic HTML tags for rich text
    allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li', 'code', 'pre']
    allowed_attributes = {'a': ['href'], '*': []}
    return bleach.clean(content, tags=allowed_tags, attributes=allowed_attributes)


def create_post(author_uid: str, content: str, post_type: str = 'post',
                images: list = None, links: list = None, visibility: str = 'public') -> dict:
    """Create a new post.

    Performance: runs analyze_post_content synchronously after writing the
    post and stores the result as _analysis in the same document.  This means
    every subsequent feed load reads cached analysis instead of recomputing it.
    """
    import uuid
    from datetime import datetime

    post_id = str(uuid.uuid4())
    now     = datetime.utcnow().isoformat()

    hashtags       = extract_hashtags(content)
    hashtags_lower = [tag.lower() for tag in hashtags]

    post_data = {
        'author_uid':     author_uid,
        'type':           post_type,
        'content':        sanitize_content(content),
        'images':         images or [],
        'links':          links or [],
        'hashtags':       hashtags,
        'hashtags_lower': hashtags_lower,
        'visibility':     visibility,
        'group_id':       None,
        'reaction_counts': {'insightful': 0, 'motivating': 0, 'support': 0},
        'comment_count':  0,
        'share_count':    0,
        'view_count':     0,
        'created_at':     now,
        'updated_at':     now,
        'deleted':        False,
    }

    try:
        post_ref = db.collection('posts').document(post_id)
        post_ref.set(post_data)

        # ── Pre-compute and store analysis so feed loads never recompute it ──
        try:
            analysis = analyze_post_content(post_data)
            slim_analysis = {k: v for k, v in analysis.items()
                             if k != 'semantic_embedding'}
            post_ref.update({'_analysis': slim_analysis})
            collab_cache.set_post_analysis_cache(post_id, slim_analysis)
        except Exception as ae:
            print(f"Warning: could not pre-compute analysis for post {post_id}: {ae}")

        # Update user's post count
        user_ref = db.collection('collab_users').document(author_uid)
        if user_ref.get().exists:
            user_ref.update({'post_count': firestore.Increment(1)})
        else:
            print(f"User {author_uid} not found, skipping post count update")

        return {'post_id': post_id, **post_data}

    except Exception as e:
        print(f"Error creating post: {e}")
        raise


def get_feed_posts(uid: str, cursor: str = None, limit: int = 20) -> dict:
    """Get feed posts for user with optimized cursor-based pagination"""
    posts = []
    
    try:
        # Get user's connections (accepted) — using participants array field
        connected_users = set()
        follows = set()

        try:
            conn_snap = db.collection('connections')                           .where('participants', 'array_contains', uid)                           .where('status', '==', 'accepted')                           .get()
            for conn in conn_snap:
                for participant in conn.to_dict().get('participants', []):
                    if participant != uid:
                        connected_users.add(participant)
        except Exception as e:
            print(f"Error getting connections for feed: {e}")

        # Get user's follows
        try:
            follow_snap = db.collection('follows')                             .where('follower_uid', '==', uid)                             .get()
            for follow in follow_snap:
                follows.add(follow.to_dict().get('following_uid'))
        except Exception as e:
            print(f"Error getting follows for feed: {e}")
        
        # Build optimized query for posts
        query = db.collection('posts') \
                  .where('deleted', '==', False) \
                  .order_by('created_at', direction=firestore.Query.DESCENDING) \
                  .limit(limit + 1)  # Get one extra for pagination
        
        # Apply cursor if provided
        if cursor:
            try:
                cursor_data = json.loads(base64.b64decode(cursor).decode())
                last_created_at = cursor_data.get('created_at')
                if last_created_at:
                    query = query.start_after({
                        'created_at': last_created_at
                    })
            except Exception as e:
                print(f"Error parsing cursor: {e}")
        
        # Execute query
        posts_snap = query.get()
        
        # Filter and enrich posts in Python
        posts_list = []
        last_doc = None
        
        for i, post_doc in enumerate(posts_snap):
            if i >= limit:  # Only process up to limit
                break
                
            post = post_doc.to_dict()
            post['post_id'] = post_doc.id
            author_uid = post.get('author_uid')
            
            # Enhanced visibility filtering
            visibility = post.get('visibility', 'public')
            include_post = True
            
            if visibility == 'private':
                include_post = author_uid == uid
            elif visibility == 'connections':
                include_post = author_uid in connected_users or author_uid in follows
            # Public posts are always included
            
            if include_post:
                # Batch get author info for better performance
                author_doc = db.collection('collab_users').document(author_uid).get()
                if author_doc.exists:
                    author = author_doc.to_dict()
                    post['author_name'] = author.get('name', 'Unknown')
                    post['author_initials'] = get_initials(author.get('name', 'Unknown'))
                    post['author_headline'] = author.get('headline', '')
                    post['author_picture'] = author.get('profile_picture', '')
                    post['author_verified'] = author.get('verified', False)
                else:
                    post['author_name'] = 'Unknown'
                    post['author_initials'] = '?'
                    post['author_headline'] = ''
                    post['author_picture'] = ''
                    post['author_verified'] = False
                
                # Add engagement metrics
                post['engagement_score'] = (
                    post.get('reaction_counts', {}).get('insightful', 0) * 3 +
                    post.get('reaction_counts', {}).get('motivating', 0) * 2 +
                    post.get('reaction_counts', {}).get('support', 0) * 1 +
                    post.get('comment_count', 0) * 2 +
                    post.get('share_count', 0) * 5
                )
                
                posts_list.append(post)
                last_doc = post_doc
        
        # Sort by engagement score for better feed quality
        posts_list.sort(key=lambda x: (
            x.get('engagement_score', 0) +
            (1 if x.get('author_verified') else 0) * 100
        ), reverse=True)
        
        # Generate next cursor
        next_cursor = None
        has_more = False
        if len(posts_snap) > limit and last_doc:
            cursor_data = {
                'created_at': last_doc.to_dict().get('created_at')
            }
            next_cursor = base64.b64encode(
                json.dumps(cursor_data).encode()
            ).decode()
            has_more = True
        
        return {
            'posts': posts_list,
            'next_cursor': next_cursor,
            'has_more': has_more,
            'total_fetched': len(posts_list)
        }
        
    except Exception as e:
        print(f"Error getting feed posts: {e}")
        return {
            'posts': [],
            'next_cursor': None,
            'has_more': False,
            'total_fetched': 0
        }


def get_post_with_comments(post_id: str, uid: str) -> dict:
    """Get single post with threaded comments - optimized to avoid composite indexes"""
    try:
        # Get post
        post_ref = db.collection('posts').document(post_id).get()
        if not post_ref.exists or post_ref.to_dict().get('deleted'):
            return None
            
        post_data = post_ref.to_dict()
        
        # Get author info
        author_uid = post_data.get('author_uid')
        author_ref = db.collection('collab_users').document(author_uid).get()
        author_data = author_ref.to_dict() if author_ref.exists else {}
        
        # Get user's reaction
        user_reaction = None
        reaction_ref = db.collection('posts').document(post_id).collection('reactions').document(uid).get()
        if reaction_ref.exists:
            user_reaction = reaction_ref.to_dict().get('reaction_type')
        
        # Get comments - optimized to avoid composite index
        comments = []
        
        # Get all comments first, then filter in Python
        comments_snap = db.collection('posts').document(post_id).collection('comments').get()
        
        # Process comments in Python to avoid composite index
        for comment_doc in comments_snap:
            comment_data = comment_doc.to_dict()
            comment_id = comment_doc.id
            
            # Skip deleted comments
            if not comment_data.get('deleted', False):
                # Get comment author
                comment_author_uid = comment_data.get('author_uid')
                comment_author_ref = db.collection('collab_users').document(comment_author_uid).get()
                comment_author_data = comment_author_ref.to_dict() if comment_author_ref.exists else {}
                
                comment_info = {
                    'id': comment_id,
                    'author': {
                        'uid': comment_author_uid,
                        'name': comment_author_data.get('name', ''),
                        'profile_picture': comment_author_data.get('profile_picture', '')
                    },
                    'content': comment_data.get('content', ''),
                    'parent_comment_id': comment_data.get('parent_comment_id'),
                    'reaction_counts': comment_data.get('reaction_counts', {}),
                    'created_at': comment_data.get('created_at')
                }
                
                comments.append(comment_info)
        
        # Sort comments by created_at in Python (more efficient than Firestore sort)
        comments.sort(key=lambda x: x.get('created_at', ''))
        
        return {
            'id': post_id,
            'author': {
                'uid': author_uid,
                'name': author_data.get('name', ''),
                'headline': author_data.get('headline', ''),
                'profile_picture': author_data.get('profile_picture', '')
            },
            'content': post_data.get('content', ''),
            'images': post_data.get('images', []),
            'links': post_data.get('links', []),
            'hashtags': post_data.get('hashtags', []),
            'reaction_counts': post_data.get('reaction_counts', {}),
            'comment_count': len(comments),
            'share_count': post_data.get('share_count', 0),
            'view_count': post_data.get('view_count', 0),
            'user_reaction': user_reaction,
            'comments': comments,
            'created_at': post_data.get('created_at'),
            'updated_at': post_data.get('updated_at')
        }
        
    except Exception as e:
        print(f"Error getting post with comments: {e}")
        return None


def get_hashtag_posts(hashtag: str, cursor: str = None, limit: int = 20) -> dict:
    """Get posts with a specific hashtag using cursor-based pagination"""
    try:
        posts = []
        
        # Convert hashtag to lowercase for case-insensitive search
        hashtag_lower = hashtag.lower()
        
        # Build query for posts with hashtag (case-insensitive)
        # Try hashtags_lower field first, fallback to multiple searches
        try:
            query = db.collection('posts') \
                      .where('deleted', '==', False) \
                      .where('hashtags_lower', 'array_contains', hashtag_lower) \
                      .order_by('created_at', direction=firestore.Query.DESCENDING) \
                      .limit(limit + 1)  # Get one extra to determine if there are more
            
            # Apply cursor if provided
            if cursor:
                try:
                    cursor_data = json.loads(base64.b64decode(cursor).decode())
                    last_created_at = cursor_data.get('created_at')
                    if last_created_at:
                        query = query.start_after({
                            'created_at': last_created_at
                        })
                except Exception as e:
                    print(f"Error parsing cursor: {e}")
            
            # Execute query
            posts_snap = query.get()
            
        except Exception as e:
            print(f"Error using hashtags_lower field: {e}")
            # Fallback: search for multiple case variations
            hashtag_variations = [hashtag, hashtag.lower(), hashtag.upper(), hashtag.capitalize()]
            all_posts = []
            
            for variant in hashtag_variations:
                try:
                    query = db.collection('posts') \
                              .where('deleted', '==', False) \
                              .where('hashtags', 'array_contains', variant) \
                              .order_by('created_at', direction=firestore.Query.DESCENDING) \
                              .limit(limit + 1)  # Get one extra to determine if there are more
                    
                    docs = query.get()
                    for doc in docs:
                        post_data = doc.to_dict()
                        post_data['post_id'] = doc.id
                        if post_data not in all_posts:
                            all_posts.append(post_data)
                except Exception as variant_error:
                    print(f"Error searching for variant '{variant}': {variant_error}")
                    continue
            
            # Sort all posts by created_at
            all_posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            # Apply limit and pagination manually
            posts = all_posts[:limit]
            has_more = len(all_posts) > limit
            
            # Enrich posts with author info
            for post in posts:
                try:
                    author_doc = db.collection('collab_users').document(post['author_uid']).get()
                    if author_doc.exists:
                        author = author_doc.to_dict()
                        post['author_name'] = author.get('name', 'Unknown')
                        post['author_initials'] = get_initials(author.get('name', ''))
                        post['author_headline'] = author.get('headline', '')
                        post['author_picture'] = author.get('profile_picture', '')
                except Exception as author_error:
                    print(f"Error getting author info: {author_error}")
                    post['author_name'] = 'Unknown'
                    post['author_initials'] = 'U'
                    post['author_headline'] = ''
                    post['author_picture'] = ''
            
            return {
                'posts': posts,
                'cursor': '',
                'has_more': has_more,
                'post_count': len(all_posts)
            }
        
        # Convert to list and handle pagination
        posts_list = []
        last_doc = None
        for i, post_doc in enumerate(posts_snap):
            if i < limit:  # Only include up to limit
                post = post_doc.to_dict()
                post['post_id'] = post_doc.id
                
                # Get author info
                author_doc = db.collection('collab_users').document(post['author_uid']).get()
                if author_doc.exists:
                    author = author_doc.to_dict()
                    post['author_name'] = author.get('name', 'Unknown')
                    post['author_initials'] = get_initials(author.get('name', 'Unknown'))
                else:
                    post['author_name'] = 'Unknown'
                    post['author_initials'] = '?'
                
                posts_list.append(post)
                last_doc = post_doc
        
        # Generate next cursor
        next_cursor = None
        has_more = False
        if len(posts_snap) > limit and last_doc:
            cursor_data = {
                'created_at': last_doc.to_dict().get('created_at')
            }
            next_cursor = base64.b64encode(
                json.dumps(cursor_data).encode()
            ).decode()
            has_more = True
        
        return {
            'posts': posts_list,
            'cursor': next_cursor,
            'has_more': has_more,
            'post_count': len(posts_list)
        }
        
    except Exception as e:
        print(f"Error getting hashtag posts: {e}")
        return {
            'posts': [],
            'cursor': None,
            'has_more': False,
            'post_count': 0
        }


def get_trending_hashtags(limit: int = 10) -> list:
    """Get trending hashtags based on recent post activity"""
    try:
        hashtag_counts = {}
        
        # Get recent posts (last 7 days)
        from datetime import datetime, timedelta
        week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        
        recent_posts = db.collection('posts') \
                          .where('deleted', '==', False) \
                          .where('created_at', '>=', week_ago) \
                          .get()
        
        # Count hashtag occurrences
        for post_doc in recent_posts:
            post = post_doc.to_dict()
            hashtags = post.get('hashtags_lower', [])  # Use lowercase field for counting
            for hashtag in hashtags:
                hashtag_counts[hashtag] = hashtag_counts.get(hashtag, 0) + 1
        
        # Sort by count and return top hashtags
        trending = sorted(
            [{'tag': tag, 'count': count} for tag, count in hashtag_counts.items()],
            key=lambda x: x['count'],
            reverse=True
        )[:10]  # Limit to top 10
        
        return trending[:limit]
        
    except Exception as e:
        print(f"Error getting trending hashtags: {e}")
        return []


def search_posts(query: str, filters: dict = {}, limit: int = 20, cursor: str = None) -> dict:
    """Search for posts by content, hashtags, and author - MORE LENIENT VERSION"""
    posts = []
    
    try:
        # If no query, return recent posts
        if not query or not query.strip():
            # Just get recent posts
            query_ref = db.collection('posts') \
                          .where('deleted', '==', False) \
                          .order_by('created_at', direction=firestore.Query.DESCENDING) \
                          .limit(limit)
            
            posts_snap = query_ref.get()
            posts_list = []
            
            for post_doc in posts_snap:
                post = post_doc.to_dict()
                post['post_id'] = post_doc.id
                post['match_score'] = 1  # Default score for recent posts
                
                # Get author info
                author_uid = post.get('author_uid')
                author_doc = db.collection('collab_users').document(author_uid).get()
                if author_doc.exists:
                    author = author_doc.to_dict()
                    post['author_name'] = author.get('name', 'Unknown')
                    post['author_initials'] = get_initials(author.get('name', 'Unknown'))
                    post['author_headline'] = author.get('headline', '')
                    post['author_picture'] = author.get('profile_picture', '')
                    post['author_verified'] = author.get('verified', False)
                else:
                    post['author_name'] = 'Unknown'
                    post['author_initials'] = '?'
                    post['author_headline'] = ''
                    post['author_picture'] = ''
                    post['author_verified'] = False
                
                posts_list.append(post)
            
            return {
                'posts': posts_list,
                'next_cursor': None,
                'has_more': False,
                'total_fetched': len(posts_list)
            }
        
        # For searches, get more posts and filter leniently
        query_ref = db.collection('posts') \
                      .where('deleted', '==', False) \
                      .order_by('created_at', direction=firestore.Query.DESCENDING) \
                      .limit(min(limit * 3, 100))  # Get more posts for better filtering
        
        # Apply cursor if provided
        if cursor:
            try:
                cursor_data = json.loads(base64.b64decode(cursor).decode())
                last_created_at = cursor_data.get('created_at')
                if last_created_at:
                    query_ref = query_ref.start_after({
                        'created_at': last_created_at
                    })
            except Exception as e:
                print(f"Error parsing cursor: {e}")
        
        # Execute query
        posts_snap = query_ref.get()
        
        # Filter and enrich posts in Python with LENIENT matching
        posts_list = []
        last_doc = None
        
        for i, post_doc in enumerate(posts_snap):
            if len(posts_list) >= limit:  # Stop when we have enough results
                break
                
            post = post_doc.to_dict()
            post['post_id'] = post_doc.id
            
            # Apply LENIENT search filters
            match_result = lenient_matches_search_criteria(post, query, filters)
            if not match_result['matches']:
                continue
                
            # Get author info
            author_uid = post.get('author_uid')
            author_doc = db.collection('collab_users').document(author_uid).get()
            if author_doc.exists:
                author = author_doc.to_dict()
                post['author_name'] = author.get('name', 'Unknown')
                post['author_initials'] = get_initials(author.get('name', 'Unknown'))
                post['author_headline'] = author.get('headline', '')
                post['author_picture'] = author.get('profile_picture', '')
                post['author_verified'] = author.get('verified', False)
            else:
                post['author_name'] = 'Unknown'
                post['author_initials'] = '?'
                post['author_headline'] = ''
                post['author_picture'] = ''
                post['author_verified'] = False
            
            # Set match score from lenient matching
            post['match_score'] = match_result['score']
            
            posts_list.append(post)
            last_doc = post_doc
        
        # Sort by match score and created_at
        posts_list.sort(key=lambda x: (x.get('match_score', 0), x.get('created_at', '')), reverse=True)
        
        # Generate next cursor
        next_cursor = None
        has_more = False
        if len(posts_snap) > limit and last_doc:
            cursor_data = {
                'created_at': last_doc.to_dict().get('created_at')
            }
            next_cursor = base64.b64encode(
                json.dumps(cursor_data).encode()
            ).decode()
            has_more = True
        
        return {
            'posts': posts_list,
            'next_cursor': next_cursor,
            'has_more': has_more,
            'total_fetched': len(posts_list)
        }
        
    except Exception as e:
        print(f"Error searching posts: {e}")
        return {
            'posts': [],
            'next_cursor': None,
            'has_more': False,
            'total_fetched': 0
        }


def lenient_matches_search_criteria(post: dict, query: str, filters: dict) -> dict:
    """ENHANCED search criteria matching with AI semantic support"""
    content = post.get('content', '')
    hashtags = post.get('hashtags_lower', [])
    author_uid = post.get('author_uid')
    query_lower = query.lower().strip()
    
    # Start with base score
    score = 0
    matches = False
    
    # LENIENT text search in content
    if query_lower:
        # Exact match - highest score
        if query_lower in content.lower():
            score += 20
            matches = True
        
        # Word boundary matching
        content_words = content.lower().split()
        for word in content_words:
            # Remove punctuation from word for better matching
            clean_word = word.strip('.,!?;:"()[]{}')
            if clean_word and (query_lower in clean_word or clean_word in query_lower):
                score += 15
                matches = True
                break
        
        # Hashtag matching
        for tag in hashtags:
            if query_lower in tag or tag in query_lower:
                score += 10
                matches = True
                break
        
        # AI-powered semantic matching
        try:
            semantic_candidates = [content] + hashtags
            semantic_matches = get_semantic_matches(query_lower, semantic_candidates, threshold=0.3)
            if semantic_matches:
                best_match = semantic_matches[0]
                ai_score = int(best_match['score'] * 100)
                score += ai_score
                matches = True
        except Exception as e:
            print(f"❌ AI semantic matching failed: {e}")
        
        # Fuzzy matching for common variations (fallback)
        fuzzy_matches = get_fuzzy_matches(query_lower)
        for fuzzy_term in fuzzy_matches:
            if fuzzy_term in content:
                score += 5
                matches = True
                break
    
    # Author filter
    if filters.get('author_uid'):
        if author_uid == filters['author_uid']:
            score += 10
        else:
            return {'matches': False, 'score': 0}
    
    # Hashtag filter
    if filters.get('hashtag'):
        hashtag_lower = filters['hashtag'].lower()
        if any(hashtag_lower in tag for tag in hashtags):
            score += 15
            matches = True
        else:
            return {'matches': False, 'score': 0}
    
    # Date range filter
    if filters.get('date_from'):
        try:
            from datetime import datetime
            date_from = datetime.fromisoformat(filters['date_from'])
            post_date = datetime.fromisoformat(post.get('created_at', ''))
            if post_date >= date_from:
                score += 2
            else:
                return {'matches': False, 'score': 0}
        except:
            pass
    
    if filters.get('date_to'):
        try:
            from datetime import datetime
            date_to = datetime.fromisoformat(filters['date_to'])
            post_date = datetime.fromisoformat(post.get('created_at', ''))
            if post_date <= date_to:
                score += 2
            else:
                return {'matches': False, 'score': 0}
        except:
            pass
    
    # If no query but we have other filters, consider it a match
    if not query_lower and (filters.get('author_uid') or filters.get('hashtag')):
        matches = True
        score = max(score, 5)
    
    return {'matches': matches, 'score': score}


def get_fuzzy_matches(query: str) -> list:
    """Get semantic matching variations using AI instead of hardcoded mapping"""
    if not AI_AVAILABLE or not query:
        return [query]  # Return original query if AI not available
    
    # Common semantic variations for popular tech terms
    semantic_variations = {
        'python': ['py', 'python3', 'python programming', 'python dev'],
        'javascript': ['js', 'javascript', 'nodejs', 'node.js', 'ecmascript'],
        'react': ['reactjs', 'react.js', 'react native', 'react hooks'],
        'java': ['java programming', 'jvm', 'java development'],
        'web': ['website', 'web development', 'web dev', 'frontend', 'backend', 'full stack'],
        'design': ['designer', 'ui', 'ux', 'designing', 'graphic design'],
        'data': ['data science', 'database', 'data analysis', 'analytics', 'big data'],
        'machine': ['machine learning', 'ml', 'ai', 'artificial intelligence', 'deep learning'],
        'dev': ['developer', 'development', 'devops', 'programming', 'coding'],
        'app': ['application', 'mobile', 'android', 'ios', 'software'],
        'code': ['coding', 'programming', 'software', 'source code'],
        'tech': ['technology', 'technical', 'engineering', 'it'],
        'student': ['study', 'education', 'learning', 'academic', 'university'],
        'project': ['projects', 'portfolio', 'work', 'assignment'],
    }
    
    variations = [query]
    query_lower = query.lower()
    
    # Add semantic variations from AI-powered mapping
    for key, values in semantic_variations.items():
        if query_lower in key or key in query_lower:
            variations.extend(values)
    
    # Use AI semantic matching for additional variations
    try:
        common_terms = ['programming', 'development', 'engineering', 'software', 'technology', 'data', 'web', 'mobile', 'app', 'design', 'ai', 'ml']
        ai_candidates = []
        
        for term in common_terms:
            if term not in query_lower and len(term) >= 3:
                ai_candidates.append(f"{query} {term}")
        
        if ai_candidates:
            semantic_matches = get_semantic_matches(query, ai_candidates, threshold=0.4)
            for match in semantic_matches[:3]:  # Top 3 matches
                variations.append(match['text'])
    except Exception as e:
        print(f"❌ AI semantic variations failed: {e}")
    
    return list(set(variations))  # Remove duplicates


def matches_search_criteria(post: dict, query: str, filters: dict) -> bool:
    """Check if a post matches search criteria"""
    content = post.get('content', '').lower()
    hashtags = post.get('hashtags_lower', [])
    author_uid = post.get('author_uid')
    
    # Text search in content
    if query and query.lower():
        query_lower = query.lower()
        if query_lower not in content:
            # Check if query matches any hashtag
            if not any(query_lower in tag for tag in hashtags):
                return False
    
    # Author filter
    if filters.get('author_uid'):
        if author_uid != filters['author_uid']:
            return False
    
    # Hashtag filter
    if filters.get('hashtag'):
        hashtag_lower = filters['hashtag'].lower()
        if hashtag_lower not in hashtags:
            return False
    
    # Date range filter
    if filters.get('date_from'):
        try:
            from datetime import datetime
            date_from = datetime.fromisoformat(filters['date_from'])
            post_date = datetime.fromisoformat(post.get('created_at', ''))
            if post_date < date_from:
                return False
        except:
            pass
    
    if filters.get('date_to'):
        try:
            from datetime import datetime
            date_to = datetime.fromisoformat(filters['date_to'])
            post_date = datetime.fromisoformat(post.get('created_at', ''))
            if post_date > date_to:
                return False
        except:
            pass
    
    return True


def calculate_post_match_score(post: dict, query: str, filters: dict) -> int:
    """Calculate match score for a post"""
    score = 0
    content = post.get('content', '').lower()
    hashtags = post.get('hashtags_lower', [])
    
    # Exact query match in content
    if query and query.lower():
        query_lower = query.lower()
        if query_lower in content:
            score += 10
            # Bonus for exact word match
            words = content.split()
            if query_lower in words:
                score += 5
    
    # Hashtag matches
    if query and query.lower():
        query_lower = query.lower()
        for tag in hashtags:
            if query_lower in tag:
                score += 5
    
    # Engagement bonus
    reaction_counts = post.get('reaction_counts', {})
    engagement = (reaction_counts.get('insightful', 0) * 3 +
                  reaction_counts.get('motivating', 0) * 2 +
                  reaction_counts.get('support', 0) * 1 +
                  post.get('comment_count', 0) * 2)
    score += min(engagement // 10, 5)  # Cap engagement bonus at 5
    
    # Recency bonus (posts from last 3 days)
    try:
        from datetime import datetime, timedelta
        three_days_ago = datetime.utcnow() - timedelta(days=3)
        post_date = datetime.fromisoformat(post.get('created_at', ''))
        if post_date > three_days_ago:
            score += 2
    except:
        pass
    
    return score


def get_all_users(limit: int = 50) -> list:
    """Get all users for user directory"""
    users = []
    
    try:
        users_snap = db.collection('collab_users').limit(limit).get()
        users = []
        
        for user_doc in users_snap:
            user_data = user_doc.to_dict()
            users.append({
                'uid': user_doc.id,
                'name': user_data.get('name', ''),
                'headline': user_data.get('headline', ''),
                'profile_picture': user_data.get('profile_picture', ''),
                'skills': user_data.get('skills', [])[:5],  # Top 5 skills
                'education': user_data.get('education', [])[:2],  # Top 2 education entries
                'connection_count': user_data.get('connection_count', 0),
                'follower_count': user_data.get('follower_count', 0),
                'post_count': user_data.get('post_count', 0)
            })
        
        return users
    except Exception as e:
        print(f"Error getting all users: {e}")
        return []
# ============================================================================
# MENTORSHIP HELPERS
# ============================================================================

def get_mentor_suggestions(uid: str, limit: int = 10) -> list:
    """Get mentor suggestions for a user based on their profile"""
    try:
        # Get user profile for context
        user_doc = db.collection('collab_users').document(uid).get()
        if not user_doc.exists:
            return []
        
        user_data = user_doc.to_dict()
        user_skills = [skill.get('name', '').lower() for skill in user_data.get('skills', [])]
        user_schools = []
        
        # Extract schools from education
        for edu in user_data.get('education', []):
            if isinstance(edu, dict):
                school = edu.get('institution', '')
                if school:
                    user_schools.append(school.lower())
        
        # Get all available mentors
        mentors_query = db.collection('collab_users') \
                         .where('mentorship_available', '==', True) \
                         .limit(limit * 3) \
                         .get()
        
        suggestions = []
        
        for mentor_doc in mentors_query:
            if mentor_doc.id == uid:  # Skip self
                continue
                
            mentor_data = mentor_doc.to_dict()
            score = 0
            reasons = []
            
            # Check for mutual connections
            mutual_count = get_mutual_connections(uid, mentor_doc.id)
            if mutual_count > 0:
                score += mutual_count * 3
                reasons.append(f"{mutual_count} mutual connection{'s' if mutual_count > 1 else ''}")
            
            # Check for shared school
            mentor_schools = []
            for edu in mentor_data.get('education', []):
                if isinstance(edu, dict):
                    school = edu.get('institution', '')
                    if school:
                        mentor_schools.append(school.lower())
            
            for user_school in user_schools:
                for mentor_school in mentor_schools:
                    if is_similar_school(user_school, mentor_school):
                        score += 5
                        reasons.append("Same school")
                        break
                if score > 0:
                    break
            
            # Check for shared skills
            mentor_skills = [skill.get('name', '').lower() for skill in mentor_data.get('skills', [])]
            shared_skills = set(user_skills) & set(mentor_skills)
            if shared_skills:
                score += len(shared_skills) * 2
                reasons.append(f"{len(shared_skills)} shared skill{'s' if len(shared_skills) > 1 else ''}")
            
            # Check focus areas alignment
            focus_areas = [area.lower() for area in mentor_data.get('mentorship_focus_areas', [])]
            if focus_areas:
                score += 2  # Bonus for having focus areas
                reasons.append("Experienced mentor")
            
            if score > 0:
                suggestions.append({
                    'uid': mentor_doc.id,
                    'name': mentor_data.get('name', ''),
                    'headline': mentor_data.get('headline', ''),
                    'profile_picture': mentor_data.get('profile_picture', ''),
                    'mentorship_focus_areas': mentor_data.get('mentorship_focus_areas', []),
                    'mentorship_stats': mentor_data.get('mentorship_stats', {}),
                    'skills': mentor_data.get('skills', [])[:3],
                    'education': mentor_data.get('education', [])[:1],
                    'score': score,
                    'reasons': reasons[:2],  # Top 2 reasons
                    'mutual_connections': mutual_count
                })
        
        # Sort by score and return top suggestions
        suggestions.sort(key=lambda x: x['score'], reverse=True)
        return suggestions[:limit]
        
    except Exception as e:
        print(f"Error getting mentor suggestions: {e}")
        return []


def update_mentorship_stats(mentor_uid: str, action: str):
    """Update mentorship statistics for a mentor"""
    try:
        mentor_doc = db.collection('collab_users').document(mentor_uid).get()
        if not mentor_doc.exists:
            return False
        
        mentor_data = mentor_doc.to_dict()
        stats = mentor_data.get('mentorship_stats', {
            'total_mentees': 0,
            'active_mentees': 0,
            'completed_mentorships': 0,
            'average_rating': 0
        })
        
        if action == 'mentee_added':
            stats['total_mentees'] += 1
            stats['active_mentees'] += 1
        elif action == 'mentee_completed':
            stats['active_mentees'] = max(0, stats['active_mentees'] - 1)
            stats['completed_mentorships'] += 1
        elif action == 'rating_updated':
            # This would be called with a rating value
            pass
        
        db.collection('collab_users').document(mentor_uid).update({
            'mentorship_stats': stats,
            'updated_at': datetime.utcnow().isoformat()
        })
        return True
        
    except Exception as e:
        print(f"Error updating mentorship stats: {e}")
        return False


# ============================================================================
# ADVANCED FEED ALGORITHM
# ============================================================================

def build_user_interest_profile(uid: str) -> dict:
    """Generate comprehensive user interest profile for feed personalization.

    Caching: Redis with 1hr TTL.
    NOTE: embeddings are NOT stored in Redis (too large); they are recomputed
    in-memory each time if AI is available.  The lightweight category items
    (skills, education, etc.) are cached so Firestore is not hit every request.
    """
    # ── Redis cache check (lightweight fields only) ───────────────────────
    cached = collab_cache.get_user_profile_cache(uid)
    if cached:
        # Re-attach in-memory embedding if AI is available — this is fast
        # because get_cached_embedding uses a local in-process dict cache
        if AI_AVAILABLE and not cached.get('embedding'):
            all_items = []
            for cat_data in cached.values():
                if isinstance(cat_data, dict):
                    all_items.extend(cat_data.get('items', []))
            if all_items:
                combined = ' '.join(list(set(all_items)))[:1000]
                emb = get_cached_embedding(combined)
                if emb is not None:
                    cached['embedding'] = emb.tolist()
        return cached

    try:
        user_doc = db.collection('collab_users').document(uid).get()
        if not user_doc.exists:
            return {}

        user_data = user_doc.to_dict()

        # Extract explicit interests
        skills = [skill.get('name', '').lower() for skill in user_data.get('skills', [])]

        # Extract education interests
        education_interests, schools = [], []
        for edu in user_data.get('education', []):
            if isinstance(edu, dict):
                if edu.get('institution'):
                    schools.append(edu['institution'].lower())
                if edu.get('field'):
                    education_interests.append(edu['field'].lower())
                if edu.get('degree'):
                    education_interests.append(edu['degree'].lower())

        # Extract experience interests
        experience_interests = []
        for exp in user_data.get('experience', []):
            if isinstance(exp, dict):
                if exp.get('title'):
                    experience_interests.append(exp['title'].lower())
                if exp.get('company'):
                    experience_interests.append(exp['company'].lower())

        # Extract project interests (tech stack focus)
        project_interests = []
        for proj in user_data.get('projects', []):
            if isinstance(proj, dict):
                if proj.get('title'):
                    project_interests.append(proj['title'].lower())
                project_interests.extend(
                    tech.lower() for tech in proj.get('tech_stack', [])
                )
                # Top 10 meaningful words from description
                desc_words = [
                    w.lower() for w in proj.get('description', '').split()
                    if len(w) > 4
                ]
                project_interests.extend(desc_words[:10])

        mentorship_areas = [a.lower() for a in user_data.get('mentorship_focus_areas', [])]

        interest_profile = {
            'skills':     {'items': skills,               'weight': 0.30},
            'education':  {'items': education_interests,  'weight': 0.20},
            'experience': {'items': experience_interests, 'weight': 0.20},
            'projects':   {'items': project_interests,    'weight': 0.15},
            'schools':    {'items': schools,              'weight': 0.10},
            'mentorship': {'items': mentorship_areas,     'weight': 0.05},
        }

        # Compute embedding (in-process cache only — not stored in Redis)
        all_interests = []
        for cat_data in interest_profile.values():
            all_interests.extend(cat_data['items'])

        if AI_AVAILABLE and all_interests:
            combined = ' '.join(list(set(all_interests)))[:1000]
            emb = get_cached_embedding(combined)
            if emb is not None:
                interest_profile['embedding'] = emb.tolist()

        # Cache lightweight version (no embedding) in Redis
        collab_cache.set_user_profile_cache(uid, interest_profile)

        return interest_profile

    except Exception as e:
        print(f"Error building user interest profile: {e}")
        return {}


# Expose cache invalidation so collab.py can call it on profile edits
def invalidate_interest_profile_cache(uid: str):
    """Call whenever a user updates their skills / education / experience."""
    collab_cache.invalidate_user_profile_cache(uid)


def _tfidf_keywords(text: str, top_n: int = 15) -> list:
    """
    Lightweight TF-IDF-style keyword extraction with no external dependencies.

    Filters stop-words, short tokens, and punctuation; returns the top_n
    most distinctive words ranked by term frequency × inverse document
    frequency approximation (rare words in this text score higher).
    """
    STOP = {
        'the','and','for','are','was','were','has','have','had','that','this',
        'with','from','they','their','been','will','would','could','should',
        'what','when','where','which','who','how','why','all','but','not',
        'can','just','also','more','some','than','then','its','our','your',
        'you','about','into','over','after','before','very','even','each',
        'such','here','there','these','those','being','doing','going',
    }
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.]{2,}", text.lower())
    freq: dict = {}
    for t in tokens:
        if t not in STOP:
            freq[t] = freq.get(t, 0) + 1
    if not freq:
        return []
    # Simple IDF proxy: penalise very common words by dividing by sqrt(count)
    import math
    scored = sorted(freq.items(), key=lambda x: x[1] / math.sqrt(x[1]), reverse=True)
    return [w for w, _ in scored[:top_n]]


def analyze_post_content(post_data: dict) -> dict:
    """Analyse post content and return a lightweight analysis dict.

    Topic classification — what changed:
    ─────────────────────────────────────
    OLD: hardcoded 10-bucket keyword dict.  A post about "neurotech" or
         "UPSC prep" scored 0 topics because none of its words appeared in
         the keyword lists.

    NEW: semantic zero-shot classification via sentence-transformers.
         The model compares the post against STUDENT_TOPIC_LABELS using
         cosine similarity.  "neurotech" → "biology, medicine, and health".
         "UPSC" → "academic studies and exam preparation".  No hardcoding.

    Hashtags are always included as explicit topic signals — they are
    author-declared and override any classifier output.

    Skill extraction:
    Removed from here — skills are matched at scoring time in
    calculate_relevance_score by comparing user profile skills against
    post keywords + hashtags.  This is more accurate and works without AI.

    This function runs exactly once per post (on creation), never on feed
    loads.  Result is stored in Firestore _analysis field.
    """
    try:
        content  = post_data.get('content', '')
        hashtags = [tag.lstrip('#').lower() for tag in post_data.get('hashtags', [])]

        # ── Semantic topic classification ─────────────────────────────────
        semantic_topics = classify_topics_semantic(content, top_k=3, threshold=0.22)

        # Hashtags = author-declared topics, always reliable
        hashtag_topics = list(dict.fromkeys(hashtags))

        # Merge semantic + hashtag topics
        topics = list(dict.fromkeys(semantic_topics + hashtag_topics))

        # Fallback when AI is unavailable
        if not semantic_topics:
            topics = list(dict.fromkeys(classify_topics_keyword(content) + hashtag_topics))

        # ── Keywords via TF-IDF approximation ────────────────────────────
        combined_text = f"{content} {' '.join(hashtags)}"
        keywords = _tfidf_keywords(combined_text, top_n=15)

        # ── Education level — from content signals ────────────────────────
        text_lower = combined_text.lower()
        advanced_signals = {'phd','research','thesis','algorithm','optimization',
                             'architecture','dissertation','publication','arxiv'}
        beginner_signals = {'beginner','basic','intro','tutorial','getting started',
                             'first time','newbie','noob','learning'}
        if any(s in text_lower for s in advanced_signals):
            edu_level = 'advanced'
        elif any(s in text_lower for s in beginner_signals):
            edu_level = 'beginner'
        else:
            edu_level = 'intermediate'

        # ── Semantic embedding (AI path) ──────────────────────────────────
        embedding = None
        if AI_AVAILABLE and content:
            emb = get_cached_embedding(content[:1000])
            embedding = emb.tolist() if emb is not None else None

        return {
            'topics':             topics,
            'keywords':           keywords,
            'education_level':    edu_level,
            'semantic_embedding': embedding,
        }

    except Exception as e:
        print(f"Error analyzing post content: {e}")
        return {
            'topics': [], 'keywords': [], 'education_level': 'intermediate',
            'semantic_embedding': None,
        }



def get_cached_post_analysis(post_id: str, post_data: dict) -> dict:
    """
    Return analysis for a post, with a two-level cache:
      1. Redis  (fast, ephemeral)          — key: post_analysis:{post_id}
      2. Firestore _analysis field         — persistent across restarts
      3. Compute fresh and back-fill both  — only on true cache miss

    Embeddings are always recomputed in-memory (not persisted anywhere) to
    keep storage costs low and avoid serialising large float arrays.
    """
    # 1. Redis
    cached = collab_cache.get_post_analysis_cache(post_id)
    if cached:
        # Reattach embedding in-memory if AI is available
        if AI_AVAILABLE and not cached.get('semantic_embedding'):
            content = post_data.get('content', '')
            if content:
                emb = get_cached_embedding(content[:1000])
                if emb is not None:
                    cached['semantic_embedding'] = emb.tolist()
        return cached

    # 2. Firestore _analysis field
    try:
        doc = db.collection('posts').document(post_id).get()
        if doc.exists:
            stored = doc.to_dict().get('_analysis')
            if stored:
                # Warm Redis from Firestore
                collab_cache.set_post_analysis_cache(post_id, stored)
                # Reattach embedding
                if AI_AVAILABLE and not stored.get('semantic_embedding'):
                    content = post_data.get('content', '')
                    if content:
                        emb = get_cached_embedding(content[:1000])
                        if emb is not None:
                            stored['semantic_embedding'] = emb.tolist()
                return stored
    except Exception as e:
        print(f"get_cached_post_analysis Firestore read error: {e}")

    # 3. Compute fresh
    analysis = analyze_post_content(post_data)

    # Back-fill both caches (strip embedding for storage)
    slim = {k: v for k, v in analysis.items() if k != 'semantic_embedding'}
    collab_cache.set_post_analysis_cache(post_id, slim)
    try:
        db.collection('posts').document(post_id).update({'_analysis': slim})
    except Exception as e:
        print(f"get_cached_post_analysis Firestore write error: {e}")

    return analysis


def calculate_relevance_score(user_profile: dict, post_analysis: dict, user_data: dict) -> float:
    """
    Calculate relevance score between a user's interest profile and a post.

    Scoring breakdown (max 100):
      ── AI path (sentence-transformers available) ──────────────────────
      • Cosine similarity between user-profile embedding and post embedding  → up to 40 pts
      ── Always-on (pure Python) ────────────────────────────────────────
      • User skills ∩ post hashtags/keywords  (weight 0.30)               → up to 30 pts
      • User education/experience ∩ post topics/keywords  (weight 0.20)   → up to 20 pts
      • User project keywords ∩ post keywords  (weight 0.15)              → up to 15 pts
      • Education level alignment                                           → up to 10 pts

    Changes vs original:
    - Removed post_analysis['skills'] dependency (was always [] without AI).
      Now matches user skills directly against post hashtags + keywords.
      This works correctly regardless of AI availability.
    - user_education_level is inferred from actual degree data (not hardcoded).
    """
    try:
        if not user_profile or not post_analysis:
            return 0.0

        score = 0.0

        post_topics   = set(post_analysis.get('topics', []))
        post_keywords = set(post_analysis.get('keywords', []))
        # Hashtags are stored in 'topics' (they ARE the topics now)
        post_signals  = post_topics | post_keywords

        # ── Semantic similarity (AI path) ─────────────────────────────────
        if (AI_AVAILABLE
                and user_profile.get('embedding')
                and post_analysis.get('semantic_embedding')):
            try:
                import numpy as np
                from sklearn.metrics.pairwise import cosine_similarity as cos_sim
                u_emb = np.array(user_profile['embedding']).reshape(1, -1)
                p_emb = np.array(post_analysis['semantic_embedding']).reshape(1, -1)
                sim   = float(cos_sim(u_emb, p_emb)[0][0])
                score += sim * 40
            except Exception as e:
                print(f"Semantic similarity error: {e}")

        # ── Category-based matching (always runs) ─────────────────────────
        for category, cat_data in user_profile.items():
            if category == 'embedding':
                continue
            if not isinstance(cat_data, dict):
                continue

            items  = set(cat_data.get('items', []))
            weight = cat_data.get('weight', 0.1)
            if not items:
                continue

            if category == 'skills':
                # Match user skills directly against hashtags + keywords
                matches = items & post_signals
                score  += len(matches) * weight * 20

            elif category in ('education', 'experience'):
                matches = items & (post_topics | post_keywords)
                score  += len(matches) * weight * 15

            else:   # projects, schools, mentorship
                matches = items & post_keywords
                score  += len(matches) * weight * 10

        # ── Education level alignment ─────────────────────────────────────
        edu_text = ' '.join(
            f"{e.get('degree','')} {e.get('field','')}"
            for e in user_data.get('education', [])
            if isinstance(e, dict)
        ).lower()

        if any(k in edu_text for k in ('phd', 'doctor', 'research', 'master')):
            user_lvl = 'advanced'
        elif any(k in edu_text for k in ('bachelor', 'undergrad', 'college')):
            user_lvl = 'intermediate'
        else:
            user_lvl = 'beginner'

        post_lvl = post_analysis.get('education_level', 'intermediate')
        alignment = {
            'beginner':     {'beginner': 10, 'intermediate': 5, 'advanced': 2},
            'intermediate': {'beginner': 5,  'intermediate': 10, 'advanced': 5},
            'advanced':     {'beginner': 2,  'intermediate': 5,  'advanced': 10},
        }
        score += alignment.get(user_lvl, {}).get(post_lvl, 0)

        return min(score, 100.0)

    except Exception as e:
        print(f"Error calculating relevance score: {e}")
        return 0.0


def calculate_social_proof_score(
    post_author_uid: str,
    viewer_uid: str,
    post_data: dict,
    # Pre-loaded sets passed in from get_personalized_feed — avoids N Firestore reads
    connected_users: set = None,
    follows: set = None,
    author_data: dict = None,
) -> float:
    """Calculate social proof score based on network relationships.

    Bugs fixed:
    - Previously called get_mutual_connections (4 queries) + follows query
      + author doc fetch for EVERY post in the scoring loop — up to 600+
      extra reads per feed load.
    - Now accepts pre-loaded sets so the function is pure Python arithmetic.
    - Falls back to individual queries only when called standalone.
    """
    try:
        score = 0.0

        # Use pre-loaded sets when available, otherwise fall back to DB queries
        _connected = connected_users if connected_users is not None else set()
        _follows   = follows if follows is not None else set()

        # Direct connection boost
        if post_author_uid in _connected:
            score += 30

        # Follow boost
        if post_author_uid in _follows:
            score += 15

        # Mutual connections — only compute if connected_users is available
        # (avoids 4 extra queries per post when called from the feed loop)
        if connected_users is not None:
            # Cheap approximation: if author is followed by any of our connections
            # we can't know this without more queries, so skip and rely on
            # the connection/follow boosts above.
            pass
        else:
            # Standalone fallback: do the full DB query
            mutual_count = get_mutual_connections(viewer_uid, post_author_uid)
            if mutual_count > 0:
                score += min(mutual_count * 5, 20)

        # Author credibility — use pre-loaded author_data when available
        _author = author_data if author_data is not None else {}
        if not _author and author_data is None:
            # Only fetch from DB if truly not provided
            try:
                a_doc = db.collection('collab_users').document(post_author_uid).get()
                _author = a_doc.to_dict() if a_doc.exists else {}
            except Exception:
                _author = {}

        if _author.get('verified', False):
            score += 10

        conn_count = _author.get('connection_count', 0)
        if conn_count > 50:   score += 5
        elif conn_count > 20: score += 3

        follower_count = _author.get('follower_count', 0)
        if follower_count > 100: score += 5
        elif follower_count > 50: score += 3

        return min(score, 50)

    except Exception as e:
        print(f"Error calculating social proof score: {e}")
        return 0.0


def is_connected(uid_a: str, uid_b: str) -> bool:
    """Check if two users are connected"""
    try:
        pair   = sorted([uid_a, uid_b])
        conn_id = f"{pair[0]}_{pair[1]}"
        doc    = db.collection('connections').document(conn_id).get()
        return doc.exists and doc.to_dict().get('status') == 'accepted'
    except Exception:
        return False


def calculate_freshness_score(created_at: str, current_time: datetime = None) -> float:
    """Calculate freshness score with time decay.

    Bug fixed: datetime.utcnow() returns a naive datetime while
    fromisoformat('...+00:00') returns timezone-aware — subtracting them
    raises TypeError.  We now normalise both sides to UTC-aware.
    """
    try:
        from datetime import timezone
        now_utc = datetime.now(timezone.utc)

        # Parse stored timestamp — handles both 'Z' and '+00:00' suffixes
        ts = created_at.strip()
        if ts.endswith('Z'):
            ts = ts[:-1] + '+00:00'
        post_time = datetime.fromisoformat(ts)
        # If stored without tzinfo (legacy), assume UTC
        if post_time.tzinfo is None:
            post_time = post_time.replace(tzinfo=timezone.utc)

        hours_old = (now_utc - post_time).total_seconds() / 3600

        if hours_old < 1:    return 10.0
        elif hours_old < 6:  return 8.0
        elif hours_old < 24: return 6.0
        elif hours_old < 72: return 4.0
        elif hours_old < 168: return 2.0
        else:                return 1.0

    except Exception as e:
        print(f"Error calculating freshness score: {e}")
        return 1.0


def get_personalized_feed(uid: str, limit: int = 20, cursor: str = None) -> dict:
    """Advanced personalized feed algorithm.

    Performance additions vs previous version:
    ─ Redis feed cache (5 min TTL per uid+cursor).  Cache is invalidated on
      post create / react / comment via invalidate_user_feed_cache(uid).
    ─ Post analysis is read from cache (Redis → Firestore _analysis) instead
      of being recomputed on every feed load.  For a 60-candidate page this
      eliminates up to 60 NLP calls per request.

    Bug fixes (carried over from previous session):
    1. start_after(DocumentSnapshot) — correct Firestore pagination.
    2. Cursor tracks raw Firestore order (pre-rerank), not re-ranked position.
    3. Batch author fetch via db.get_all().
    4. calculate_social_proof_score receives pre-loaded sets (zero hot-loop reads).
    5. Own posts included with relevance boost.
    6. Per-author diversity cap (MAX_POSTS_PER_AUTHOR), not backwards 3-author block.
    7. freshness_score: timezone-aware datetime subtraction.
    8. Education level inferred from actual degree data.
    """
    MAX_POSTS_PER_AUTHOR = 2
    CANDIDATE_MULTIPLIER = 5

    # ── Redis cache check ─────────────────────────────────────────────────
    cached_feed = collab_cache.get_feed_cache(uid, cursor or '')
    if cached_feed:
        print(f"✅ Feed served from Redis cache for {uid}")
        return cached_feed

    try:
        user_doc = db.collection('collab_users').document(uid).get()
        if not user_doc.exists:
            return {'posts': [], 'next_cursor': None, 'has_more': False}

        user_data            = user_doc.to_dict()
        user_interest_profile = build_user_interest_profile(uid)

        # ── Pre-load connection + follow sets (2 queries) ─────────────────
        connected_users: set = set()
        follows: set         = set()

        try:
            conn_snap = db.collection('connections') \
                          .where(filter=firestore.FieldFilter('participants', 'array_contains', uid)) \
                          .where(filter=firestore.FieldFilter('status', '==', 'accepted')) \
                          .get()
            for conn in conn_snap:
                for p in conn.to_dict().get('participants', []):
                    if p != uid:
                        connected_users.add(p)
        except Exception as e:
            print(f"Error getting connections for feed: {e}")

        try:
            follow_snap = db.collection('follows') \
                            .where(filter=firestore.FieldFilter('follower_uid', '==', uid)) \
                            .get()
            for f in follow_snap:
                follows.add(f.to_dict().get('following_uid'))
        except Exception as e:
            print(f"Error getting follows for feed: {e}")

        # ── Fetch candidate posts (1 query) ───────────────────────────────
        candidate_limit = max(60, limit * CANDIDATE_MULTIPLIER)
        query = db.collection('posts') \
                  .where(filter=firestore.FieldFilter('deleted', '==', False)) \
                  .order_by('created_at', direction=firestore.Query.DESCENDING) \
                  .limit(candidate_limit)

        if cursor:
            try:
                cursor_data = json.loads(base64.b64decode(cursor).decode())
                last_doc_id = cursor_data.get('last_doc_id')
                if last_doc_id:
                    last_snap = db.collection('posts').document(last_doc_id).get()
                    if last_snap.exists:
                        query = query.start_after(last_snap)
            except Exception as e:
                print(f"Error applying cursor: {e}")

        posts_snap = list(query.get())
        print(f"🔍 Raw query returned {len(posts_snap)} posts")

        # ── Batch-fetch all author profiles (1 call for N authors) ────────
        author_uids = list({
            doc.to_dict().get('author_uid')
            for doc in posts_snap
            if doc.to_dict().get('author_uid')
        })
        author_cache: dict = {}
        if author_uids:
            try:
                refs      = [db.collection('collab_users').document(a) for a in author_uids]
                a_docs    = db.get_all(refs)
                for a_doc in a_docs:
                    if a_doc.exists:
                        author_cache[a_doc.id] = a_doc.to_dict()
            except Exception as e:
                print(f"Error batch-fetching authors: {e}")
                for auid in author_uids:
                    try:
                        a = db.collection('collab_users').document(auid).get()
                        if a.exists:
                            author_cache[auid] = a.to_dict()
                    except Exception:
                        pass

        # ── Score every candidate ─────────────────────────────────────────
        from datetime import timezone as _tz
        current_time_utc = datetime.now(_tz.utc)

        scored_posts                          = []
        last_raw_doc                          = None
        visibility_filtered = missing_author  = 0
        own_posts_count                       = 0

        for post_doc in posts_snap:
            post      = post_doc.to_dict()
            post_id   = post_doc.id
            post['post_id']  = post_id
            author_uid = post.get('author_uid')

            # Visibility
            visibility = post.get('visibility', 'public')
            if visibility == 'private' and author_uid != uid:
                visibility_filtered += 1; continue
            if visibility == 'connections' and author_uid != uid:
                if author_uid not in connected_users and author_uid not in follows:
                    visibility_filtered += 1; continue

            author_data = author_cache.get(author_uid)
            if not author_data:
                missing_author += 1; continue

            is_own = (author_uid == uid)
            if is_own:
                own_posts_count += 1

            # ── Post analysis: cache → compute ────────────────────────────
            post_analysis = get_cached_post_analysis(post_id, post)

            # ── Scoring (all pure Python, zero DB reads) ──────────────────
            try:
                relevance_score = calculate_relevance_score(
                    user_interest_profile, post_analysis, user_data)
            except Exception:
                relevance_score = 0.0

            engagement_score = min(
                post.get('reaction_counts', {}).get('insightful', 0) * 3 +
                post.get('reaction_counts', {}).get('motivating', 0) * 2 +
                post.get('reaction_counts', {}).get('support', 0)    * 1 +
                post.get('comment_count', 0) * 2 +
                post.get('share_count', 0)   * 5,
                100,
            )

            try:
                social_proof_score = calculate_social_proof_score(
                    post_author_uid=author_uid, viewer_uid=uid,
                    post_data=post,
                    connected_users=connected_users, follows=follows,
                    author_data=author_data,
                )
            except Exception:
                social_proof_score = 0.0

            try:
                freshness_score = calculate_freshness_score(post.get('created_at', ''))
            except Exception:
                freshness_score = 1.0

            own_boost  = 10 if is_own else 0
            final_score = (
                relevance_score    * 0.40 +
                engagement_score   * 0.30 +
                social_proof_score * 0.20 +
                freshness_score    * 0.10 +
                own_boost
            )

            post.update({
                'author_name':       author_data.get('name', 'Unknown'),
                'author_initials':   get_initials(author_data.get('name', 'Unknown')),
                'author_headline':   author_data.get('headline', ''),
                'author_picture':    author_data.get('profile_picture', ''),
                'author_verified':   author_data.get('verified', False),
                'relevance_score':   relevance_score,
                'engagement_score':  engagement_score,
                'social_proof_score': social_proof_score,
                'freshness_score':   freshness_score,
                'final_score':       final_score,
                'post_analysis':     post_analysis,
            })

            scored_posts.append(post)
            last_raw_doc = post_doc

        # ── Sort and diversify ────────────────────────────────────────────
        scored_posts.sort(key=lambda x: x['final_score'], reverse=True)

        author_post_count: dict = {}
        used_topics: set        = set()
        diversified_posts       = []

        for post in scored_posts:
            author = post.get('author_uid')
            topics = set(post.get('post_analysis', {}).get('topics', []))

            if author_post_count.get(author, 0) >= MAX_POSTS_PER_AUTHOR:
                continue
            if len(topics) > 0 and len(topics & used_topics) > 2:
                continue

            diversified_posts.append(post)
            author_post_count[author] = author_post_count.get(author, 0) + 1
            used_topics.update(topics)

            if len(diversified_posts) >= limit:
                break

        # Back-fill if diversity constraints left us short
        if len(diversified_posts) < limit:
            seen = {p['post_id'] for p in diversified_posts}
            for post in scored_posts:
                if post['post_id'] not in seen:
                    diversified_posts.append(post)
                    seen.add(post['post_id'])
                if len(diversified_posts) >= limit:
                    break

        # ── Cursor (tracks raw Firestore order, pre-rerank) ───────────────
        next_cursor = None
        has_more    = len(posts_snap) >= candidate_limit
        if last_raw_doc and has_more:
            next_cursor = base64.b64encode(
                json.dumps({'last_doc_id': last_raw_doc.id}).encode()
            ).decode()

        print(f"🔍 Feed debug: raw={len(posts_snap)} vis_filtered={visibility_filtered} "
              f"own={own_posts_count} no_author={missing_author} "
              f"scored={len(scored_posts)} returned={len(diversified_posts[:limit])}")

        result = {
            'posts':         diversified_posts[:limit],
            'next_cursor':   next_cursor,
            'has_more':      has_more,
            'total_fetched': len(diversified_posts),
            'algorithm_info': {
                'candidate_limit':     candidate_limit,
                'total_candidates':    len(scored_posts),
                'avg_relevance_score': (
                    sum(p['relevance_score'] for p in diversified_posts[:limit]) /
                    len(diversified_posts[:limit])
                ) if diversified_posts else 0,
                'diversified':    True,
                'posts_returned': len(diversified_posts[:limit]),
                'cache_hit':      False,
                'debug_info': {
                    'raw_query_posts':     len(posts_snap),
                    'visibility_filtered': visibility_filtered,
                    'own_posts_included':  own_posts_count,
                    'missing_author':      missing_author,
                },
            },
        }

        # ── Write result to Redis (5 min TTL) ─────────────────────────────
        # Strip embeddings before storing — large float arrays bloat Redis
        cache_result = {
            **result,
            'posts': [
                {k: v for k, v in p.items() if k != 'semantic_embedding'}
                for p in result['posts']
            ]
        }
        cache_result['algorithm_info']['cache_hit'] = False
        collab_cache.set_feed_cache(uid, cursor or '', cache_result)

        return result

    except Exception as e:
        print(f"Error getting personalized feed: {e}")
        return get_feed_posts(uid, cursor, limit)

def track_user_interaction(uid: str, post_id: str, interaction_type: str, metadata: dict = None):
    """Track user interactions with posts for algorithm improvement"""
    try:
        interaction_data = {
            'user_uid': uid,
            'post_id': post_id,
            'interaction_type': interaction_type,  # 'view', 'like', 'comment', 'share', 'save'
            'created_at': datetime.utcnow().isoformat(),
            'metadata': metadata or {}
        }
        
        # Store interaction in Firestore
        db.collection('user_interactions').add(interaction_data)
        
        # Update post engagement counters
        post_ref = db.collection('posts').document(post_id)
        
        if interaction_type == 'like':
            # This would be called when a user reacts to a post
            pass  # Reaction handling is already implemented elsewhere
        elif interaction_type == 'comment':
            post_ref.update({'comment_count': firestore.Increment(1)})
        elif interaction_type == 'share':
            post_ref.update({'share_count': firestore.Increment(1)})
        elif interaction_type == 'view':
            post_ref.update({'view_count': firestore.Increment(1)})
        
        return True
        
    except Exception as e:
        print(f"Error tracking user interaction: {e}")
        return False


def get_user_interest_insights(uid: str) -> dict:
    """Get insights about user's content interests based on interactions"""
    try:
        # Get user's recent interactions
        interactions_snap = db.collection('user_interactions') \
                               .where(filter=firestore.FieldFilter('user_uid', '==', uid)) \
                               .order_by('created_at', direction=firestore.Query.DESCENDING) \
                               .limit(100) \
                               .get()
        
        # Analyze interaction patterns
        interaction_topics = {}
        interaction_skills = {}
        interaction_authors = {}
        
        for interaction_doc in interactions_snap:
            interaction = interaction_doc.to_dict()
            post_id = interaction.get('post_id')
            
            # Get post details
            post_doc = db.collection('posts').document(post_id).get()
            if post_doc.exists:
                post_data = post_doc.to_dict()
                post_analysis = analyze_post_content(post_data)
                
                # Track topics
                for topic in post_analysis.get('topics', []):
                    interaction_topics[topic] = interaction_topics.get(topic, 0) + 1
                
                # Track skills
                for skill in post_analysis.get('skills', []):
                    interaction_skills[skill] = interaction_skills.get(skill, 0) + 1
                
                # Track authors
                author_uid = post_data.get('author_uid')
                if author_uid:
                    interaction_authors[author_uid] = interaction_authors.get(author_uid, 0) + 1
        
        # Sort by frequency
        top_topics = sorted(interaction_topics.items(), key=lambda x: x[1], reverse=True)[:10]
        top_skills = sorted(interaction_skills.items(), key=lambda x: x[1], reverse=True)[:10]
        top_authors = sorted(interaction_authors.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'top_topics': [{'topic': topic, 'count': count} for topic, count in top_topics],
            'top_skills': [{'skill': skill, 'count': count} for skill, count in top_skills],
            'top_authors': [{'author_uid': uid, 'count': count} for uid, count in top_authors],
            'total_interactions': len(interactions_snap)
        }
        
    except Exception as e:
        print(f"Error getting user interest insights: {e}")
        return {
            'top_topics': [],
            'top_skills': [],
            'top_authors': [],
            'total_interactions': 0
        }