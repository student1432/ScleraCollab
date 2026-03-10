# ScleraCollab – Master Plan
## "LinkedIn for Students" — Product Requirements, Architecture & Phased Implementation

---

# PART 1 — PRODUCT REQUIREMENTS DOCUMENT (PRD)

## 1.1 Vision & Problem Statement

**Vision:** ScleraCollab is the professional-academic social layer of the Sclera ecosystem — a platform where students discover peers, build verified academic identities, share knowledge, and access opportunities. Think LinkedIn × GitHub × Notion, purpose-built for students aged 13–25.

**Problem:** Students using Sclera (the academic slice) have no professional identity online that is:
- Tied to verifiable academic progress
- Safe, age-appropriate, and school-aware
- Integrated with their career interests (ScleraCareer)
- A place for real collaboration (not just consumption)

**Solution:** ScleraCollab gives every student a living professional portfolio that evolves with their academic journey, a trusted network of peers and mentors, and a content ecosystem where student knowledge compounds.

---

## 1.2 Target Users

| Persona | Description | Primary Need |
|---------|-------------|--------------|
| **Studious Student** | 14–18, school-going | Build profile, connect with classmates, share notes |
| **Aspiring Professional** | 17–22, college/JEE/NEET | Showcase projects, find mentors, internship signals |
| **Mentor/Senior Student** | 20–25, experienced | Give back, build reputation, find mentees |
| **Teacher (observer)** | Institution teachers | View student professional growth (read-only) |

---

## 1.3 Core Feature Modules

### MODULE A — Professional Profile
- **A1** Extended profile fields: work experience, volunteer work, projects, publications, patents, awards, languages, education
- **A2** Skills with endorsements (count + endorser avatars)
- **A3** Written recommendations (request → approve → display flow)
- **A4** Portfolio section: project cards with description, live link, GitHub, media upload
- **A5** Profile completion meter (0–100%, milestone-based)
- **A6** Privacy controls: per-section visibility (Public / Connections / Only Me)
- **A7** Academic data bridge: auto-import board/grade/school from Sclera academic slice

### MODULE B — Networking & Connections
- **B1** Follow system (asymmetric) + Connection system (symmetric) — both supported
- **B2** Mentorship connections: separate "Mentor" connection type with request/accept flow
- **B3** Smart suggestions: mutual connections, same school, shared career goals
- **B4** Alumni network: auto-surface students from same institution
- **B5** Follow institutions/companies: curated pages with updates

### MODULE C — Feed & Content
- **C1** Posts: short-form (280+ chars, images, links)
- **C2** Articles: long-form rich-text editor (reuse Docs editor style)
- **C3** Engagement: reactions (👍 Insightful / 🔥 Motivating / ❤️ Support), comments, shares
- **C4** Feed: hybrid algorithmic + chronological toggle
- **C5** Hashtags: #AI #Internship #NEET etc. for discovery
- **C6** Resource sharing: notes/files shared publicly or to connections
- **C7** Saved posts: bookmark any post/article

### MODULE D — Groups (Evolved Bubbles)
- **D1** Rename Bubbles → Groups throughout
- **D2** Public groups (topic-based, open join) + Private groups (invite only)
- **D3** Group features: pinned posts, rules, moderators, member roles (Admin/Mod/Member)
- **D4** Group events: create, RSVP, reminders
- **D5** Group feed separate from main feed
- **D6** Migrate existing bubbles data seamlessly

### MODULE E — Messaging
- **E1** Direct Messages (1:1): real-time via SocketIO
- **E2** Group chats: ad-hoc chat groups (separate from Groups/Bubbles)
- **E3** File sharing in DMs
- **E4** Message reactions, read receipts
- **E5** Message requests (from non-connections)

### MODULE F — Notifications & Activity
- **F1** Notification center: connection requests, endorsements, post reactions, mentions, comments
- **F2** Activity log: "X endorsed your Python skill", "Y commented on your post"
- **F3** Weekly digest (optional email)
- **F4** Real-time notification badge via SocketIO

---

## 1.4 Non-Goals (Explicitly Out of Scope)
- Video/voice calls (WebRTC) — future phase
- Job board / internship applications — lives in ScleraCareer slice
- Academic progress tracking — lives in Sclera academic slice
- Payment / premium features — future

---

## 1.5 Success Metrics

| Metric | Target (3 months post-launch) |
|--------|-------------------------------|
| Profile completion rate | >60% reach "Complete" status |
| DAU/MAU ratio | >30% |
| Avg. connections per user | >10 |
| Posts per active user/week | >2 |
| DM sessions per week | >5 per active user |

---

# PART 2 — USER FLOW

## 2.1 Onboarding Flow
```
New User (from Sclera signup)
  │
  ├─ Auto-import: name, email, school/board/grade from Sclera users collection
  │
  ├─ ScleraCollab Profile Setup Wizard (5 steps)
  │   ├─ Step 1: Profile photo + headline + bio (250 chars)
  │   ├─ Step 2: Education (auto-filled from Sclera, allow manual additions)
  │   ├─ Step 3: Skills (type to add, suggest from career interests)
  │   ├─ Step 4: Projects (optional, can skip)
  │   └─ Step 5: Privacy preferences
  │
  ├─ Profile completion meter shows % → nudge to reach 60%
  │
  └─ Redirect to Feed with smart suggestions sidebar
```

## 2.2 Profile Flow
```
Profile Page (own / others)
  │
  ├─ Own Profile
  │   ├─ Edit any section inline or via edit modal
  │   ├─ Request recommendation from a connection
  │   ├─ View who endorsed skills
  │   └─ Profile completion meter with suggested next actions
  │
  └─ Other's Profile
      ├─ Connect / Follow / Message / Endorse Skill / Request Mentorship
      ├─ View public sections (based on their privacy settings)
      └─ Report profile
```

## 2.3 Feed Flow
```
Feed
  │
  ├─ Post Creation
  │   ├─ Short post (text + image/link + hashtags)
  │   └─ Long article (rich text editor → publish)
  │
  ├─ Feed Items
  │   ├─ Posts from connections + followed entities
  │   ├─ Suggested posts (based on hashtags/interests)
  │   └─ "Trending in your network" section
  │
  └─ Engagement
      ├─ React → counter updates via SocketIO
      ├─ Comment → threaded, can reply to replies (2 levels)
      └─ Share → repost with optional quote
```

## 2.4 Messaging Flow
```
Messages
  │
  ├─ DM List (sorted by last active)
  │   ├─ Existing connections → direct message
  │   └─ Non-connections → message request (must be accepted)
  │
  ├─ Chat Window
  │   ├─ Real-time via SocketIO room: dm_{sorted_uid_pair}
  │   ├─ Send text, files, reactions
  │   └─ Read receipts (double tick)
  │
  └─ Group Chat (ad-hoc)
      ├─ Create group → name → add members
      └─ Same real-time features as DM
```

## 2.5 Groups Flow
```
Groups
  │
  ├─ Discover: browse public groups by topic/hashtag
  ├─ My Groups: groups I'm in
  │
  ├─ Group Detail
  │   ├─ Group Feed (posts visible to members / public)
  │   ├─ Members list (with roles)
  │   ├─ Files tab (shared resources)
  │   ├─ Events tab
  │   └─ About (rules, description, created by)
  │
  ├─ Create Group: name, type (public/private), topic tags, rules
  └─ Admin Panel: manage members, remove, promote, pin posts
```

---

# PART 3 — LOGIC FLOW & DATA ARCHITECTURE

## 3.1 Firestore Collections

```
/collab_users/{uid}                        ← Extended profile (overlay on Sclera users)
    name, headline, bio, profile_picture
    education: [{school, degree, grade, gpa, from, to, current}]
    experience: [{title, company, type, from, to, description}]
    volunteer: [{org, role, cause, from, to}]
    projects: [{id, title, description, link, github, media[]}]
    publications: [{title, journal, link, date}]
    awards: [{title, issuer, date}]
    languages: [{language, proficiency}]
    skills: [{name, endorsement_count}]
    profile_completion: 0-100
    privacy: {per_section_visibility}
    follower_count, following_count, connection_count
    created_at, updated_at

/collab_users/{uid}/recommendations/{rec_id}
    from_uid, from_name, relationship, text, status (pending/approved/rejected)
    created_at, approved_at

/collab_users/{uid}/endorsements/{skill_name}
    endorsers: [uid...]
    count: int

/connections/{conn_id}                     ← Symmetric connections (migrated from Sclera)
    user_a, user_b, status, type (peer/mentor/mentee), created_at

/follows/{follow_id}                       ← Asymmetric follows
    follower_uid, following_uid (or entity_id), entity_type (user/institution/company)
    created_at

/posts/{post_id}
    author_uid, type (post/article), content, images[], links[]
    hashtags[], visibility (public/connections/group)
    group_id (null if feed post)
    reaction_counts: {insightful: 0, motivating: 0, support: 0}
    comment_count, share_count, view_count
    created_at, updated_at, deleted

/posts/{post_id}/comments/{comment_id}
    author_uid, content, parent_comment_id (for threading)
    reaction_counts, created_at, deleted

/posts/{post_id}/reactions/{uid}
    reaction_type, created_at

/groups/{group_id}                         ← Evolved from bubbles
    name, description, type (public/private)
    topic_tags[], rules[], banner_image
    creator_uid, moderator_uids[], member_count
    created_at, updated_at

/groups/{group_id}/members/{uid}
    role (admin/moderator/member), joined_at, status

/groups/{group_id}/events/{event_id}
    title, description, date, location (virtual/physical)
    rsvp_count, created_by

/direct_messages/{dm_id}                   ← dm_id = sorted(uid1, uid2).join('_')
    participants: [uid1, uid2]
    last_message, last_message_at
    message_request: bool (if not connections)

/direct_messages/{dm_id}/messages/{msg_id}
    sender_uid, content, type (text/file)
    read_by: [uid...], reactions: {uid: emoji}
    created_at, deleted

/group_chats/{chat_id}
    name, creator_uid, member_uids[]
    last_message, last_message_at

/group_chats/{chat_id}/messages/{msg_id}   ← Same structure as DM messages

/notifications/{notif_id}
    recipient_uid, type, actor_uid, entity_id, entity_type
    message, read, created_at
```

## 3.2 Key Logic Flows

### Profile Completion Scoring
```python
COMPLETION_WEIGHTS = {
    'photo': 10,
    'headline': 10,
    'bio': 10,
    'education': 15,
    'skills_min_3': 10,
    'experience_or_projects': 15,
    'connections_min_5': 10,
    'first_post': 10,
    'recommendation': 10,
}
# Sum matching weights → score / 100
```

### Feed Algorithm
```
Feed score = (
    recency_weight * time_decay +
    connection_weight * (is_connection ? 1 : 0.3) +
    engagement_weight * (reactions + comments * 2) / hours_old +
    interest_weight * hashtag_overlap_score
)
```

### SocketIO Rooms
```
- User personal room: user_{uid}              ← notifications, DM alerts
- DM room: dm_{sorted_pair}                   ← real-time DM messages
- Group chat room: grpchat_{chat_id}          ← group chat messages
- Group room: group_{group_id}                ← group activity (posts, events)
```

---

# PART 4 — TECH STACK

| Layer | Technology | Reason |
|-------|-----------|--------|
| **Backend** | Flask (Python) | Same as Sclera — shared codebase patterns |
| **Real-time** | Flask-SocketIO + threading | Already used in app.py for bubbles |
| **Database** | Firebase Firestore | Same as Sclera — no migration needed |
| **Auth** | Firebase Admin Auth | Shared auth — single login for all slices |
| **Storage** | Local filesystem (Phase 1) → Firebase Storage (Phase 2) | Same pattern as app.py uploads |
| **Frontend** | Jinja2 + Tailwind CSS + Vanilla JS | Same as Sclera — consistent design system |
| **UI Pattern** | Glassmorphism islands, dark/light mode toggle | Same as screenshot |
| **Security** | Flask-Talisman (CSP), Flask-Limiter, input sanitization | Same as app.py |
| **Email** | Flask-Mail | Same as app.py |
| **File** | separate `collab.py` (mirrors app.py structure) | Clean separation, shared firebase_config |
| **Environment** | `.env` + `python-dotenv` | Same as app.py |

### New dependencies (beyond app.py)
```
bleach           # HTML sanitization for articles/rich text
Pillow           # Already likely used — image processing
markdown         # Render article markdown to HTML
```

---

# PART 5 — IMPLEMENTATION PLAN (PHASED)

## Overview

The project is split into **6 phases**, each deliverable as a standalone prompt session. Each phase builds on the previous and produces working, runnable code.

```
Phase 1 → Foundation + Profile System
Phase 2 → Connections, Follows & Suggestions
Phase 3 → Feed, Posts & Articles
Phase 4 → Groups (Evolved Bubbles) + Events
Phase 5 → Messaging (DM + Group Chat)
Phase 6 → Notifications, Polish & Integration
```

---

## PHASE 1 — Foundation + Extended Profile System
**Estimated prompts:** 2–3
**Deliverables:**
- `collab.py` — main Flask app file (mirrors app.py structure)
- `firebase_config.py` — shared (already exists)
- `collab_utils.py` — profile completion scorer, privacy helpers
- Templates:
  - `collab_base.html` — base layout with glassmorphism design system, dark/light toggle, island grid
  - `collab_dashboard.html` — landing page post-login (feed placeholder + profile summary island)
  - `collab_profile.html` — full profile page (all sections)
  - `collab_profile_edit.html` — edit profile (each section inline)
  - `collab_setup_wizard.html` — 5-step onboarding wizard

**Routes to implement:**
```python
GET  /collab                          → collab_dashboard (redirect if not logged in)
GET  /collab/profile/<uid>            → view any profile
GET  /collab/profile/edit             → edit own profile
POST /collab/profile/edit             → save profile section
POST /collab/profile/photo            → upload profile photo
POST /api/collab/profile/section      → AJAX save individual section
GET  /api/collab/profile/completion   → get completion score + suggestions
POST /api/collab/recommendations/request  → request recommendation
POST /api/collab/recommendations/<id>/respond → approve/reject rec
POST /api/collab/skills/<skill>/endorse → endorse a skill
DELETE /api/collab/skills/<skill>/endorse → remove endorsement
```

**Data:**
- Create `collab_users` collection with full schema on first Collab login
- Bridge function: auto-import from `users/{uid}` (name, school, grade, board)

**UI Details (from screenshot):**
- Same top nav pattern: pill-shaped active state, icon + label
- Islands: rounded-2xl, bg-[#1a1a1a] dark / bg-white/80 light, subtle border
- Profile: banner image (1200×300), avatar overlaid bottom-left, headline below
- Completion meter: circular progress ring (like Academic Progress island)
- Skills: tag chips with endorsement count badge
- Section cards: each section is its own island (Education, Experience, Projects…)

---

## PHASE 2 — Connections, Follows & Smart Suggestions
**Estimated prompts:** 2
**Deliverables:**
- Extend `collab.py` with connection/follow routes
- `collab_network.html` — My Network page (connections, pending, suggestions)
- `collab_suggestions.html` — People you may know
- `collab_search.html` — search people by name/school/skill/hashtag
- `collab_mentorship.html` — mentorship request flow

**Routes:**
```python
GET  /collab/network                       → network overview
GET  /collab/network/suggestions           → suggestions page
POST /api/collab/connections/send          → send connection request
POST /api/collab/connections/<id>/accept   → accept
POST /api/collab/connections/<id>/decline  → decline
POST /api/collab/connections/<id>/withdraw → withdraw sent request
DELETE /api/collab/connections/<uid>       → remove connection
POST /api/collab/follow/<uid>              → follow user/entity
DELETE /api/collab/follow/<uid>            → unfollow
GET  /api/collab/suggestions               → get smart suggestions
POST /api/collab/mentorship/request        → send mentorship request
POST /api/collab/mentorship/<id>/accept    → accept mentorship
GET  /collab/search                        → people/group/post search
```

**Suggestion Algorithm:**
```python
def get_suggestions(uid):
    scores = {}
    # mutual connections: +3 per mutual
    # same school: +5
    # same career goal: +4
    # same skills: +2 per skill
    # same grade: +1
    return sorted(scores, reverse=True)[:20]
```

**Migration:** Import existing `connections` from app.py Firestore, map to new schema.

---

## PHASE 3 — Feed, Posts, Articles & Engagement
**Estimated prompts:** 3
**Deliverables:**
- Extend `collab.py` with post/feed routes
- `collab_feed.html` — main feed page with create post widget + feed list
- `collab_post.html` — single post detail page with comment threading
- `collab_article_editor.html` — rich text article editor (reuse Docs editor style)
- `collab_article.html` — article reader view
- `collab_hashtag.html` — hashtag discovery page

**Routes:**
```python
GET  /collab/feed                          → main feed
POST /api/collab/posts                     → create post
PUT  /api/collab/posts/<id>                → edit post
DELETE /api/collab/posts/<id>              → delete post
GET  /api/collab/posts/<id>                → get single post
POST /api/collab/posts/<id>/react          → add/change reaction
DELETE /api/collab/posts/<id>/react        → remove reaction
POST /api/collab/posts/<id>/comments       → add comment
DELETE /api/collab/posts/<id>/comments/<c> → delete comment
POST /api/collab/posts/<id>/share          → share/repost
POST /api/collab/posts/<id>/save           → bookmark post
GET  /collab/hashtag/<tag>                 → hashtag feed
GET  /api/collab/feed                      → paginated feed (AJAX, cursor-based)
POST /api/collab/articles                  → create/update article (draft)
POST /api/collab/articles/<id>/publish     → publish article
```

**Feed Pagination:** cursor-based (last_doc_id param) for infinite scroll.

**SocketIO:** When a reaction/comment is added, broadcast to `post_{post_id}` room so all viewers see live updates.

---

## PHASE 4 — Groups (Evolved Bubbles) + Events
**Estimated prompts:** 2
**Deliverables:**
- Extend `collab.py` with groups routes
- `collab_groups.html` — groups discovery + my groups
- `collab_group_detail.html` — group page (feed, members, files, events, about)
- `collab_group_admin.html` — admin panel
- `collab_event_detail.html` — single event page with RSVP
- Migration script: move existing `bubbles` → `groups` with backwards compat

**Routes:**
```python
GET  /collab/groups                        → groups discovery
POST /api/collab/groups                    → create group
GET  /collab/groups/<id>                   → group detail
PUT  /api/collab/groups/<id>               → update group
DELETE /api/collab/groups/<id>             → delete group
POST /api/collab/groups/<id>/join          → join public group
POST /api/collab/groups/<id>/leave         → leave group
POST /api/collab/groups/<id>/invite        → invite member
GET  /api/collab/groups/<id>/members       → list members
POST /api/collab/groups/<id>/members/<uid>/role → change role
DELETE /api/collab/groups/<id>/members/<uid>    → remove member
POST /api/collab/groups/<id>/posts         → post to group
POST /api/collab/groups/<id>/posts/<p>/pin → pin post
POST /api/collab/groups/<id>/events        → create event
POST /api/collab/groups/<id>/events/<e>/rsvp → RSVP
```

**Migration bridge:**
```python
def migrate_bubble_to_group(bubble_id):
    # Read from bubbles/{bubble_id}
    # Write to groups/{bubble_id} (keep same ID for URL continuity)
    # Migrate member_uids → members subcollection with role='member'
    # Keep backwards-compat: /bubble/<id> redirects to /collab/groups/<id>
```

---

## PHASE 5 — Direct Messaging & Group Chats
**Estimated prompts:** 2–3
**Deliverables:**
- Extend `collab.py` with DM/chat routes + SocketIO handlers
- `collab_messages.html` — messaging hub (DM list + group chats sidebar)
- `collab_dm.html` — individual DM conversation view
- `collab_group_chat.html` — group chat view
- `collab_message_request.html` — message requests inbox

**Routes:**
```python
GET  /collab/messages                      → messages hub
GET  /collab/messages/dm/<uid>             → DM with specific user
GET  /api/collab/dms                       → list all DM threads
GET  /api/collab/dms/<dm_id>/messages      → get messages (paginated)
POST /api/collab/dms/<uid>/send            → send DM
DELETE /api/collab/dms/<dm_id>/messages/<id> → delete message
POST /api/collab/dms/<dm_id>/messages/<id>/react → react to message
GET  /api/collab/message-requests          → list message requests
POST /api/collab/message-requests/<id>/accept  → accept request
POST /api/collab/group-chats               → create group chat
GET  /api/collab/group-chats               → list user's group chats
POST /api/collab/group-chats/<id>/send     → send to group chat
```

**SocketIO handlers:**
```python
@socketio.on('collab_dm_send')     → persist + emit to dm_{pair} room
@socketio.on('collab_dm_read')     → update read_by + emit receipt
@socketio.on('collab_dm_react')    → update reaction + emit
@socketio.on('collab_typing')      → emit typing indicator (ephemeral)
```

**DM room naming:** `dm_{min_uid}_{max_uid}` (sorted lexicographically — same pair always same room)

---

## PHASE 6 — Notifications, Polish & Integration
**Estimated prompts:** 2
**Deliverables:**
- Extend `collab.py` with notification routes
- `collab_notifications.html` — full notification center
- Notification badge widget (inline SocketIO-driven)
- `collab_activity.html` — my activity log
- Integration hooks: ScleraCareer bridge (import career goals for suggestions), Sclera academic bridge (auto-import education section updates)
- Final polish: mobile responsiveness audit, Lighthouse pass, loading skeletons

**Routes:**
```python
GET  /api/collab/notifications             → paginated notifications
POST /api/collab/notifications/<id>/read   → mark read
POST /api/collab/notifications/read-all    → mark all read
GET  /collab/activity                      → my activity log
GET  /api/collab/activity                  → activity feed (AJAX)
```

**Notification triggers (called from within other route handlers):**
```python
def create_notification(recipient_uid, type, actor_uid, entity_id, message):
    # Write to /notifications/{auto_id}
    # Emit via SocketIO to user_{recipient_uid} room
    # Increment unread badge count
```

**Notification types:**
```
connection_request, connection_accepted,
endorsement, recommendation_request, recommendation_received,
post_reaction, post_comment, post_mention, post_share,
group_invite, group_post, group_event,
dm_request, dm_message,
mentorship_request, mentorship_accepted
```

---

# PART 6 — UI/UX DESIGN SYSTEM

## 6.1 Design Tokens (from screenshot analysis)

```css
/* Dark Mode (default) */
--bg-primary: #0d0d0d;
--bg-island: #1a1a1a;
--bg-island-hover: #222222;
--border: rgba(255,255,255,0.08);
--text-primary: #ffffff;
--text-secondary: #9ca3af;
--accent: #22c55e;           /* Green accent (from streak/completed indicators) */
--accent-blue: #3b82f6;
--accent-red: #ef4444;

/* Light Mode */
--bg-primary: #f5f5f5;
--bg-island: rgba(255,255,255,0.85);
--border: rgba(0,0,0,0.06);
--text-primary: #111827;
--text-secondary: #6b7280;
```

## 6.2 Island Component Pattern

Every UI section is an "island" — a self-contained card:
```html
<div class="island">           <!-- rounded-2xl, bg-island, border, p-6 -->
  <div class="island-header">  <!-- label in small caps, muted, tracking-widest -->
    SECTION TITLE
  </div>
  <div class="island-body">    <!-- content -->
  </div>
</div>
```

## 6.3 Navigation
Top nav: same pill-style as screenshot. For Collab:
`Feed | Network | Groups | Messages | Notifications[badge] | Profile`

## 6.4 Mobile
- Islands stack to single column on <768px
- Bottom nav bar on mobile (replaces top nav)
- Touch-friendly tap targets (min 44px)
- Swipe-to-go-back on message views

---

# PART 7 — FILE STRUCTURE

```
sclera_collab/
├── collab.py                  ← Main Flask app (mirrors app.py)
├── collab_utils.py            ← Profile completion, privacy, suggestion algo
├── firebase_config.py         ← Shared (symlink or import from parent)
├── collab_socket.py           ← SocketIO event handlers (separated for clarity)
├── static/
│   ├── collab.css             ← Design tokens + island components
│   ├── collab_feed.js         ← Feed infinite scroll, reactions
│   ├── collab_profile.js      ← Inline editing, completion meter
│   ├── collab_chat.js         ← DM + group chat real-time
│   └── collab_notifications.js← Notification badge + center
└── templates/
    ├── collab_base.html
    ├── collab_dashboard.html
    ├── collab_profile.html
    ├── collab_profile_edit.html
    ├── collab_setup_wizard.html
    ├── collab_feed.html
    ├── collab_network.html
    ├── collab_search.html
    ├── collab_groups.html
    ├── collab_group_detail.html
    ├── collab_messages.html
    ├── collab_dm.html
    ├── collab_notifications.html
    └── collab_activity.html
```

---

# PART 8 — PROMPT-BY-PROMPT EXECUTION GUIDE

When you are ready to implement, use these prompts in order:

### Prompt 1 (Phase 1A — Foundation)
> "Implement Phase 1A of ScleraCollab: create `collab.py` (Flask app skeleton with auth guard, Firestore connection, profile data model, `collab_base.html` with glassmorphism design system matching the dark/light island UI, and `collab_dashboard.html` as the landing page. Use the design system from the screenshot — dark bg #0d0d0d, islands at #1a1a1a, green accent #22c55e, pill nav."

### Prompt 2 (Phase 1B — Full Profile)
> "Implement Phase 1B of ScleraCollab: full profile page (`collab_profile.html`), profile edit (`collab_profile_edit.html`), profile completion scorer in `collab_utils.py`, skills + endorsements UI, recommendations request/display, portfolio project cards. AJAX inline section saving."

### Prompt 3 (Phase 2 — Connections & Network)
> "Implement Phase 2 of ScleraCollab: connections API, follow system, smart suggestion algorithm, `collab_network.html`, `collab_search.html`, mentorship request flow. Migrate existing Firestore connections from Sclera."

### Prompt 4 (Phase 3A — Feed & Posts)
> "Implement Phase 3A of ScleraCollab: post creation (text + image + hashtags), feed rendering with cursor-based pagination, reaction system (3 types), share/bookmark. `collab_feed.html` and `collab_post.html`."

### Prompt 5 (Phase 3B — Articles & Hashtags)
> "Implement Phase 3B of ScleraCollab: rich-text article editor (`collab_article_editor.html`), article reader view, hashtag feed page, comment threading (2 levels). SocketIO live reactions."

### Prompt 6 (Phase 4 — Groups & Events)
> "Implement Phase 4 of ScleraCollab: Groups system (evolved from Bubbles), group discovery + creation, group detail page with feed/members/files/events tabs, event creation + RSVP, group admin panel, bubble migration script."

### Prompt 7 (Phase 5A — DM)
> "Implement Phase 5A of ScleraCollab: Direct Messaging — DM list, DM conversation view, SocketIO real-time send/receive/read receipts, file sharing in DMs, message reactions, message requests flow."

### Prompt 8 (Phase 5B — Group Chats)
> "Implement Phase 5B of ScleraCollab: ad-hoc group chats (separate from Groups), group chat creation, group chat view, SocketIO handlers."

### Prompt 9 (Phase 6 — Notifications & Polish)
> "Implement Phase 6 of ScleraCollab: notification system (Firestore + SocketIO badge), notification center page, activity log, final mobile responsiveness pass, loading skeletons, integrate career goal data bridge from ScleraCareer for profile suggestions."

---

*Document version 1.0 — ScleraCollab Master Plan*
*Generated for Divik — Sclera Student Platform*
