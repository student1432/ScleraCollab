ScleraCollab – Master Plan (Updated for Standalone Implementation)
"LinkedIn for Students" — Product Requirements, Architecture & Phased Implementation
This document has been updated to reflect the current standalone implementation of ScleraCollab, as shown in sclera_collab.py. All references to dependencies on the main Sclera academic slice have been removed. The platform now operates as an independent application with its own Firebase Auth, Firestore collections, and user base. Future integrations with other slices are optional and can be added via APIs if desired.

PART 1 — PRODUCT REQUIREMENTS DOCUMENT (PRD)
1.1 Vision & Problem Statement
Vision: ScleraCollab is the professional-academic social layer of the Sclera ecosystem — a platform where students discover peers, build verified academic identities, share knowledge, and access opportunities. Think LinkedIn × GitHub × Notion, purpose-built for students aged 13–25.

Problem: Students have no dedicated professional identity online that is:

Tied to verifiable academic progress (optional integration)

Safe, age-appropriate, and school-aware

Integrated with career interests (future optional integration with ScleraCareer)

A place for real collaboration (not just consumption)

Solution: ScleraCollab gives every student a living professional portfolio that evolves with their journey, a trusted network of peers and mentors, and a content ecosystem where student knowledge compounds. It is built as a standalone application, independent of other slices, ensuring modularity and easy deployment.

1.2 Target Users
Persona	Description	Primary Need
Studious Student	14–18, school-going	Build profile, connect with classmates, share notes
Aspiring Professional	17–22, college/JEE/NEET	Showcase projects, find mentors, internship signals
Mentor/Senior Student	20–25, experienced	Give back, build reputation, find mentees
Teacher (observer)	Institution teachers	View student professional growth (read-only)
1.3 Core Feature Modules
MODULE A — Professional Profile
A1 Extended profile fields: work experience, volunteer work, projects, publications, patents, awards, languages, education

A2 Skills with endorsements (count + endorser avatars)

A3 Written recommendations (request → approve → display flow)

A4 Portfolio section: project cards with description, live link, GitHub, media upload

A5 Profile completion meter (0–100%, milestone-based)

A6 Privacy controls: per-section visibility (Public / Connections / Only Me)

A7 (Optional future integration) Academic data bridge to import board/grade/school from Sclera academic slice via API.

MODULE B — Networking & Connections
B1 Follow system (asymmetric) + Connection system (symmetric) — both supported

B2 Mentorship connections: separate "Mentor" connection type with request/accept flow

B3 Smart suggestions: mutual connections, same school, shared career goals

B4 Alumni network: auto-surface students from same institution

B5 Follow institutions/companies: curated pages with updates

MODULE C — Feed & Content
C1 Posts: short-form (280+ chars, images, links)

C2 Articles: long-form rich-text editor (reuse Docs editor style)

C3 Engagement: reactions (👍 Insightful / 🔥 Motivating / ❤️ Support), comments, shares

C4 Feed: hybrid algorithmic + chronological toggle

C5 Hashtags: #AI #Internship #NEET etc. for discovery

C6 Resource sharing: notes/files shared publicly or to connections

C7 Saved posts: bookmark any post/article

MODULE D — Groups (Evolved Bubbles)
D1 Rename Bubbles → Groups throughout

D2 Public groups (topic-based, open join) + Private groups (invite only)

D3 Group features: pinned posts, rules, moderators, member roles (Admin/Mod/Member)

D4 Group events: create, RSVP, reminders

D5 Group feed separate from main feed

D6 Migrate existing bubbles data seamlessly (if migrating from original app)

MODULE E — Messaging
E1 Direct Messages (1:1): real-time via SocketIO

E2 Group chats: ad-hoc chat groups (separate from Groups)

E3 File sharing in DMs

E4 Message reactions, read receipts

E5 Message requests (from non-connections)

MODULE F — Notifications & Activity
F1 Notification center: connection requests, endorsements, post reactions, mentions, comments

F2 Activity log: "X endorsed your Python skill", "Y commented on your post"

F3 Weekly digest (optional email)

F4 Real-time notification badge via SocketIO

1.4 Non-Goals (Explicitly Out of Scope)
Video/voice calls (WebRTC) — future phase

Job board / internship applications — lives in ScleraCareer slice (future integration)

Academic progress tracking — lives in Sclera academic slice (future integration)

Payment / premium features — future

1.5 Success Metrics
Metric	Target (3 months post-launch)
Profile completion rate	>60% reach "Complete" status
DAU/MAU ratio	>30%
Avg. connections per user	>10
Posts per active user/week	>2
DM sessions per week	>5 per active user
PART 2 — USER FLOW
2.1 Onboarding Flow
text
New User (signs up via ScleraCollab standalone)
  │
  ├─ Create account with email/password (Firebase Auth)
  │
  ├─ ScleraCollab Profile Setup Wizard (5 steps)
  │   ├─ Step 1: Profile photo + headline + bio (250 chars)
  │   ├─ Step 2: Education (add manually, no auto-import)
  │   ├─ Step 3: Skills (type to add, suggest from career interests)
  │   ├─ Step 4: Projects (optional, can skip)
  │   └─ Step 5: Privacy preferences
  │
  ├─ Profile completion meter shows % → nudge to reach 60%
  │
  └─ Redirect to Feed with smart suggestions sidebar
2.2 Profile Flow
text
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
2.3 Feed Flow
text
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
2.4 Messaging Flow
text
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
2.5 Groups Flow
text
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
PART 3 — LOGIC FLOW & DATA ARCHITECTURE
3.1 Firestore Collections
text
/collab_users/{uid}                        ← Extended profile (standalone collection)
    name, headline, bio, profile_picture, profile_banner
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
    created_at, updated_at, setup_complete

/collab_users/{uid}/recommendations/{rec_id}
    from_uid, from_name, relationship, text, status (pending/approved/rejected)
    created_at, approved_at

/collab_users/{uid}/endorsements/{skill_name}
    endorsers: [uid...]
    count: int

/collab_users/{uid}/rec_inbox/{req_id}     ← Recommendation requests received
    requesting_uid, message, status, read

/connections/{conn_id}                     ← Symmetric connections
    user_a, user_b, status, type (peer/mentor/mentee), created_at

/follows/{follow_id}                       ← Asymmetric follows
    follower_uid, following_uid, entity_type (user), created_at

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
3.2 Key Logic Flows
Profile Completion Scoring
python
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
Feed Algorithm
text
Feed score = (
    recency_weight * time_decay +
    connection_weight * (is_connection ? 1 : 0.3) +
    engagement_weight * (reactions + comments * 2) / hours_old +
    interest_weight * hashtag_overlap_score
)
SocketIO Rooms
text
- User personal room: user_{uid}              ← notifications, DM alerts
- DM room: dm_{sorted_pair}                   ← real-time DM messages
- Group chat room: grpchat_{chat_id}          ← group chat messages
- Group room: group_{group_id}                ← group activity (posts, events)
- Post room: post_{post_id}                   ← live updates on a post (reactions/comments)
PART 4 — TECH STACK
Layer	Technology	Reason
Backend	Flask (Python)	Same pattern as original app, familiar, extensible
Real-time	Flask-SocketIO + threading	For live messaging, notifications, feed updates
Database	Firebase Firestore	Scalable, real-time capable, same as other slices (but separate collections)
Authentication	Firebase Auth (REST API + Admin SDK)	Standalone user management; users are separate from other slices
Storage	Local filesystem (Phase 1) → Firebase Storage (Phase 2)	Profile pictures, banners, post images
Frontend	Jinja2 + Tailwind CSS + Vanilla JS	Consistent with design system; reuse existing patterns
UI Pattern	Glassmorphism islands, dark/light mode toggle	Matches Sclera aesthetic
Security	Flask-Talisman (CSP), Flask-Limiter, input sanitization	Same as original app
Email	Flask-Mail	For notifications (weekly digest, etc.)
Configuration	.env + python-dotenv	Environment variables for API keys, secrets
Dependencies
text
Flask
firebase-admin
flask-socketio
flask-limiter
flask-talisman
flask-mail
python-dotenv
requests           # for Firebase REST API calls
Pillow             # image processing
bleach             # HTML sanitization for articles/rich text
markdown           # render article markdown to HTML
PART 5 — IMPLEMENTATION PLAN (PHASED)
Overview
The project is split into 6 phases, each deliverable as a standalone prompt session. Phase 1 has already been implemented (see current sclera_collab.py). The remaining phases build upon it.

text
Phase 1 → Foundation + Extended Profile System  [COMPLETED]
Phase 2 → Connections, Follows & Suggestions
Phase 3 → Feed, Posts & Articles
Phase 4 → Groups (Evolved Bubbles) + Events
Phase 5 → Messaging (DM + Group Chat)
Phase 6 → Notifications, Polish & Integration
PHASE 1 — Foundation + Extended Profile System ✅
Deliverables already present in sclera_collab.py:

Standalone Flask app with its own Firebase Auth (REST + Admin)

Firestore collection collab_users with full profile schema

Profile view/edit, photo upload, setup wizard

Skills with endorsements (API endpoints)

Recommendations request/respond (basic)

Profile completion scorer (helper functions)

Templates created:

collab_base.html, collab_dashboard.html, collab_profile.html, collab_profile_edit.html, collab_setup_wizard.html

Routes implemented:

text
GET  /                         → redirect to dashboard or login
GET  /login, /register, /logout
GET  /dashboard
GET  /profile/<uid>
GET  /profile/edit
POST /profile/edit
POST /profile/photo
POST /api/collab/profile/section
GET  /api/collab/profile/completion
POST /api/collab/recommendations/request
POST /api/collab/recommendations/<id>/respond
POST /api/collab/skills/<skill>/endorse
DELETE /api/collab/skills/<skill>/endorse
PHASE 2 — Connections, Follows & Smart Suggestions
Estimated prompts: 2
Deliverables:

Extend collab.py with connection/follow routes

collab_network.html — My Network page (connections, pending, suggestions)

collab_suggestions.html — People you may know

collab_search.html — search people by name/school/skill/hashtag

collab_mentorship.html — mentorship request flow

Routes to implement:

python
GET  /collab/network                       → network overview
GET  /collab/network/suggestions           → suggestions page
POST /api/collab/connections/send          → send connection request
POST /api/collab/connections/<id>/accept   → accept
POST /api/collab/connections/<id>/decline  → decline
POST /api/collab/connections/<id>/withdraw → withdraw sent request
DELETE /api/collab/connections/<uid>       → remove connection
POST /api/collab/follow/<uid>              → follow user
DELETE /api/collab/follow/<uid>            → unfollow
GET  /api/collab/suggestions               → get smart suggestions
POST /api/collab/mentorship/request        → send mentorship request
POST /api/collab/mentorship/<id>/accept    → accept mentorship
GET  /collab/search                         → people search
Suggestion Algorithm:

python
def get_suggestions(uid):
    scores = {}
    # mutual connections: +3 per mutual
    # same school (from education): +5
    # same career goal (optional from future integration): +4
    # same skills: +2 per skill
    # same grade (from education): +1
    return sorted(scores, reverse=True)[:20]
PHASE 3 — Feed, Posts, Articles & Engagement
Estimated prompts: 3
Deliverables:

Extend collab.py with post/feed routes

collab_post.html — single post detail page with comment threading

collab_article_editor.html — rich text article editor (reuse Docs editor style)

collab_article.html — article reader view

collab_hashtag.html — hashtag discovery page

Routes:

python
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
Feed Pagination: cursor-based (last_doc_id param) for infinite scroll.

SocketIO: When a reaction/comment is added, broadcast to post_{post_id} room so all viewers see live updates.

PHASE 4 — Groups (Evolved Bubbles) + Events
Estimated prompts: 2
Deliverables:

Extend collab.py with groups routes

collab_groups.html — groups discovery + my groups

collab_group_detail.html — group page (feed, members, files, events, about)

collab_group_admin.html — admin panel

collab_event_detail.html — single event page with RSVP

(Optional) Migration script for existing bubbles if importing from original app

Routes:

python
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
PHASE 5 — Direct Messaging & Group Chats
Estimated prompts: 2–3
Deliverables:

Extend collab.py with DM/chat routes + SocketIO handlers

collab_messages.html — messaging hub (DM list + group chats sidebar)

collab_dm.html — individual DM conversation view

collab_group_chat.html — group chat view

collab_message_request.html — message requests inbox

Routes:

python
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
SocketIO handlers:

python
@socketio.on('collab_dm_send')     → persist + emit to dm_{pair} room
@socketio.on('collab_dm_read')     → update read_by + emit receipt
@socketio.on('collab_dm_react')    → update reaction + emit
@socketio.on('collab_typing')      → emit typing indicator (ephemeral)
DM room naming: dm_{min_uid}_{max_uid} (sorted lexicographically)

PHASE 6 — Notifications, Polish & Integration
Estimated prompts: 2
Deliverables:

Extend collab.py with notification routes

collab_notifications.html — full notification center

Notification badge widget (inline SocketIO-driven)

collab_activity.html — my activity log

Optional integration hooks: ScleraCareer API (import career goals), Sclera academic API (import education) – if desired, can be added as optional features

Final polish: mobile responsiveness audit, Lighthouse pass, loading skeletons

Routes:

python
GET  /api/collab/notifications             → paginated notifications
POST /api/collab/notifications/<id>/read   → mark read
POST /api/collab/notifications/read-all    → mark all read
GET  /collab/activity                      → my activity log
GET  /api/collab/activity                  → activity feed (AJAX)
Notification triggers (called from within other route handlers):

python
def create_notification(recipient_uid, type, actor_uid, entity_id, message):
    # Write to /notifications/{auto_id}
    # Emit via SocketIO to user_{recipient_uid} room
    # Increment unread badge count
Notification types:

text
connection_request, connection_accepted,
endorsement, recommendation_request, recommendation_received,
post_reaction, post_comment, post_mention, post_share,
group_invite, group_post, group_event,
dm_request, dm_message,
mentorship_request, mentorship_accepted
PART 6 — UI/UX DESIGN SYSTEM
6.1 Design Tokens (from screenshot analysis)
css
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
6.2 Island Component Pattern
Every UI section is an "island" — a self-contained card:

html
<div class="island">           <!-- rounded-2xl, bg-island, border, p-6 -->
  <div class="island-header">  <!-- label in small caps, muted, tracking-widest -->
    SECTION TITLE
  </div>
  <div class="island-body">    <!-- content -->
  </div>
</div>
6.3 Navigation
Top nav: same pill-style as screenshot. For Collab:
Feed | Network | Groups | Messages | Notifications[badge] | Profile

6.4 Mobile
Islands stack to single column on <768px

Bottom nav bar on mobile (replaces top nav)

Touch-friendly tap targets (min 44px)

Swipe-to-go-back on message views

PART 7 — FILE STRUCTURE
text
sclera_collab/
├── collab.py                  ← Main Flask app (already contains Phase 1)
├── collab_utils.py            ← Profile completion, privacy, suggestion algo (partial)
├── firebase_config.py         ← Firebase Admin SDK init (shared)
├── collab_socket.py           ← (to be created) SocketIO event handlers
├── static/
│   ├── collab.css             ← Design tokens + island components
│   ├── collab_feed.js         ← (future) Feed infinite scroll, reactions
│   ├── collab_profile.js      ← Inline editing, completion meter
│   ├── collab_chat.js         ← (future) DM + group chat real-time
│   └── collab_notifications.js← (future) Notification badge + center
└── templates/
    ├── collab_base.html       ← Already exists
    ├── collab_dashboard.html  ← Already exists
    ├── collab_profile.html    ← Already exists
    ├── collab_profile_edit.html ← Already exists
    ├── collab_setup_wizard.html ← Already exists
    ├── collab_feed.html       ← To be created
    ├── collab_network.html    ← To be created
    ├── collab_search.html     ← To be created
    ├── collab_groups.html     ← To be created
    ├── collab_group_detail.html ← To be created
    ├── collab_messages.html   ← To be created
    ├── collab_dm.html         ← To be created
    ├── collab_notifications.html ← To be created
    └── collab_activity.html   ← To be created
PART 8 — PROMPT-BY-PROMPT EXECUTION GUIDE
Use these prompts to continue building after Phase 1:

Prompt 2 (Phase 2 — Connections & Network)
"Extend ScleraCollab (based on existing collab.py) to add connections, follows, and smart suggestions. Create collab_network.html, collab_suggestions.html, collab_search.html, and collab_mentorship.html. Implement API endpoints for sending/accepting/declining connection requests, following/unfollowing users, and generating smart suggestions (mutual connections, same school, same skills). Also add search functionality for people by name, school, skill, or hashtag."

Prompt 3 (Phase 3A — Feed & Posts)
"Implement the feed and post system for ScleraCollab. Create posting functionality with modal in main dashboard, collab_post.html (single post view), and the necessary API routes: create post, edit/delete post, react (insightful/motivating/support), comment (threaded), share, bookmark. Use cursor-based pagination for the feed. Add SocketIO to broadcast reactions/comments in real-time to the post room."

Prompt 4 (Phase 3B — Articles & Hashtags)
"Add long-form articles to ScleraCollab. Create collab_article_editor.html (rich text editor with markdown support), collab_article.html (article reader), and collab_hashtag.html (hashtag discovery). Implement API endpoints for article drafts, publishing, and hashtag feeds. Ensure proper HTML sanitization using bleach."

Prompt 5 (Phase 4 — Groups & Events)
"Evolve the existing Bubbles concept into Groups. Create collab_groups.html, collab_group_detail.html (with tabs for feed, members, files, events, about), collab_group_admin.html, and collab_event_detail.html. Implement API endpoints for group creation, joining/leaving, inviting, role management, posting to group, pinning posts, and creating/RSVPing to events."

Prompt 6 (Phase 5A — Direct Messaging)
"Implement direct messaging for ScleraCollab. Create collab_messages.html (DM list) and collab_dm.html (conversation view). Add SocketIO handlers for sending/receiving messages, read receipts, message reactions, and typing indicators. Include message requests for non-connections. Store messages in Firestore subcollections."

Prompt 7 (Phase 5B — Group Chats)
"Add ad-hoc group chats (separate from Groups) to ScleraCollab. Extend collab_messages.html to include group chats sidebar, and create collab_group_chat.html. Implement SocketIO rooms for group chats, and API endpoints for creating group chats, adding members, and sending messages."

Prompt 8 (Phase 6 — Notifications & Polish)
"Complete ScleraCollab with a full notification system. Create collab_notifications.html and collab_activity.html. Implement create_notification helper and trigger it from all relevant actions (connections, endorsements, posts, comments, groups, messages). Add a real-time notification badge via SocketIO. Perform a mobile responsiveness audit, add loading skeletons, and ensure Lighthouse scores are high."

Document version 2.0 — ScleraCollab Master Plan (Standalone)
Updated for current implementation — ready for Phases 2–6