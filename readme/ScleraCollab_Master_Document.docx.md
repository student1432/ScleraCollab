**ScleraCollab**

*The Student Professional Network*

**MASTER TECHNICAL DOCUMENT**

Complete Architecture · All Features · Implementation Roadmap · Phase Prompts

| Document Version | 3.0 |
| :---- | :---- |
| **Status** | Living Document |
| **Platform** | Standalone Flask \+ Firebase |
| **Target Users** | Students aged 13–25 |
| **Phase Reached** | Phase 3A (Feed \+ Posts) |
| **Phases Remaining** | 3B, 4, 5, 6 |

# **PART 1 — PLATFORM OVERVIEW & VISION**

## **1.1  Vision Statement**

ScleraCollab is a purpose-built professional-academic social network for students aged 13–25. It combines the professional networking of LinkedIn, the portfolio showcasing of GitHub, and the knowledge-sharing of Notion into a single platform designed for student life cycles — from high school to early career. The platform operates as a standalone application completely independent of any other Sclera slice, with its own Firebase Auth, Firestore collections, and user base.

## **1.2  Problem Statement**

Students have no dedicated professional identity platform that is simultaneously:

* Safe, age-appropriate, and school-aware

* Tied to verifiable academic progress and peer endorsement

* A place for real collaboration — not just content consumption

* Integrated with career interests, internship discovery, and mentorship

* Accessible without requiring professional experience

## **1.3  Target User Personas**

| Persona | Primary Need |
| :---- | :---- |
| Studious Student (14–18) | Build profile, connect with classmates, share notes |
| Aspiring Professional (17–22) | Showcase projects, find mentors, get internship signals |
| Mentor/Senior Student (20–25) | Give back, build reputation, find mentees |
| Teacher/Observer | View student professional growth (read-only) |

## **1.4  Success Metrics (3 months post-launch)**

| Metric | Target |
| :---- | :---- |
| Profile completion rate | \>60% reach "Complete" status |
| DAU/MAU ratio | \>30% |
| Avg. connections per user | \>10 |
| Posts per active user/week | \>2 |
| DM sessions per week | \>5 per active user |

# **PART 2 — TECHNOLOGY STACK**

## **2.1  Core Stack**

| Layer | Technology | Purpose / Notes |
| :---- | :---- | :---- |
| **Backend** | Flask (Python) | Application server, routing, session management, API layer |
| **Real-time** | Flask-SocketIO (threading mode) | Live feed updates, reactions, comments, DMs, notifications |
| **Database** | Firebase Firestore | NoSQL document store — separate collab\_ collections from main Sclera |
| **Authentication** | Firebase Auth (REST \+ Admin SDK) | Email/password; REST API for sign-in/register, Admin SDK for token validation |
| **File Storage** | Local filesystem → Firebase Storage | Phase 1: /static/media/ local; Phase 2: Firebase Storage bucket |
| **Caching** | Redis (collab\_cache.py) | Feed cache (5min TTL), interest profiles (1hr TTL), post analysis (24hr TTL), trending (10min TTL); graceful no-op if unavailable |
| **AI / NLP** | sentence-transformers (all-MiniLM-L6-v2) | Post topic classification (20 student labels), semantic feed ranking, cosine similarity scoring; optional — falls back to keyword matching if not installed |
| **ML / Numeric** | NumPy \+ scikit-learn | Cosine similarity, embedding arithmetic |
| **HTML Sanitization** | bleach | Post/article content — allowlist tags: p, br, strong, em, u, a, ul, ol, li, code, pre |
| **Frontend** | Jinja2 \+ Tailwind CSS \+ Vanilla JS | Server-rendered templates with progressive JS enhancements |
| **Environment** | python-dotenv \+ .env | All secrets and configuration via environment variables |
| **Image Processing** | Pillow (planned) | Profile photo / banner resizing and compression |
| **Email** | Flask-Mail (planned) | Weekly digest, notification emails |
| **Security (planned)** | Flask-Limiter \+ Flask-Talisman | Rate limiting on write endpoints, CSP headers |

## **2.2  Python Dependencies (requirements.txt)**

flask

firebase-admin

flask-socketio

python-dotenv

requests              \# Firebase REST API calls

bleach                \# HTML sanitization

Pillow                \# Image processing

sentence-transformers \# AI feed ranking (optional)

scikit-learn          \# Cosine similarity

numpy                 \# Embedding arithmetic

redis                 \# Redis caching layer

flask-limiter         \# Rate limiting (to be added)

flask-talisman        \# CSP headers (to be added)

flask-mail            \# Email notifications (to be added)

## **2.3  Firebase Collections Architecture**

All ScleraCollab collections are prefixed with collab\_ or are standalone (posts, connections, follows) to remain separate from the parent Sclera academic namespace.

### **Current Active Collections**

* collab\_users/{uid} — Extended user profiles with all professional fields

* collab\_users/{uid}/recommendations/{rec\_id} — Written recommendations

* collab\_users/{uid}/endorsements/{skill\_name} — Skill endorser lists

* collab\_users/{uid}/rec\_inbox/{req\_id} — Recommendation requests received

* connections/{conn\_id} — Symmetric peer/mentor connections (conn\_id \= sorted(uid\_a,uid\_b).join("\_"))

* follows/{follow\_id} — Asymmetric follow relationships

* posts/{post\_id} — Feed posts with NLP analysis cached in \_analysis field

* posts/{post\_id}/reactions/{uid} — Per-user reactions

* posts/{post\_id}/comments/{comment\_id} — Comments (flat, parent\_comment\_id for threading planned)

* hashtags/{tag} — Hashtag metadata and post counts

### **Planned Collections (Phases 4–6)**

* groups/{group\_id} — Group metadata (type: private | public)

* groups/{group\_id}/members/{uid} — Member roles and join status

* groups/{group\_id}/posts/{post\_id} — Group-scoped posts (forum)

* groups/{group\_id}/files/{file\_id} — Shared files (private groups)

* groups/{group\_id}/folders/{folder\_id} — Folder structure (public groups)

* groups/{group\_id}/chatrooms/{room\_id} — Named chatrooms (public groups)

* groups/{group\_id}/events/{event\_id} — Group events with calendar data (public groups)

* direct\_messages/{dm\_id}/messages/{msg\_id} — DM messages (dm\_id \= min\_uid \+ "\_" \+ max\_uid)

* message\_requests/{req\_id} — Pending DM requests from non-connections

* group\_chats/{chat\_id}/messages/{msg\_id} — Group chat messages

* notifications/{notif\_id} — All notification types

* articles/{article\_id} — Long-form articles (separate from posts)

## **2.4  SocketIO Room Architecture**

| Room Name | Purpose |
| :---- | :---- |
| post\_{post\_id} | Live reactions \+ comments on a specific post |
| user\_{uid} | Personal notifications, DM alerts, badge updates |
| dm\_{min\_uid}\_{max\_uid} | Real-time direct messages between two users |
| grpchat\_{chat\_id} | Group chat real-time messages |
| group\_{group\_id} | Group activity (posts, events, member changes) |
| chatroom\_{room\_id} | Named chatroom within a public group |

## **2.5  Caching Architecture**

collab\_cache.py implements a Redis caching layer with graceful degradation — if Redis is unavailable, all cache calls silently no-op and the app continues functioning.

| Cache Key Pattern | TTL / Purpose |
| :---- | :---- |
| feed:{uid}:{cursor} | 5 min — Ranked feed per user per page |
| user\_profile:{uid} | 1 hr — Interest profile for feed ranking (no embeddings stored) |
| post\_analysis:{post\_id} | 24 hrs — NLP analysis: topics, keywords, education level |
| trending:hashtags | 10 min — Top 10 trending hashtags |

Invalidation triggers: feed cache invalidated on post create/react/comment (all connected users' caches). Interest profile invalidated on profile edit. Post analysis invalidated never (24hr TTL is sufficient).

# **PART 3 — CURRENT IMPLEMENTED FEATURES**

## **3.1  Authentication System**

ScleraCollab uses Firebase Authentication via REST API for email/password flows, and Firebase Admin SDK for server-side token validation. Sessions are Flask server-side sessions stored in a signed cookie (7-day lifetime).

### **Sign-In Flow**

* POST to Firebase REST identitytoolkit signInWithPassword endpoint

* On success: extract localId (uid), look up collab\_users/{uid} profile

* If profile not found: auto-create via initialize\_collab\_profile() and redirect to /setup wizard

* If profile found but setup\_complete=False: redirect to /setup

* Store uid, email, name in Flask session

* Cross-Sclera login: if user logs in from main Sclera app (from\_sclera=True), auto-initialise collab profile from academic data

### **Registration Flow**

* POST to Firebase REST signUp endpoint

* Create collab\_users document via initialize\_collab\_profile()

* Password strength indicator (client-side: 5-level scoring based on length, uppercase, numbers, symbols)

* Password match validation before submit

* Auto-login after successful registration

### **Security: login\_required Decorator**

All protected routes use @login\_required. The decorator checks session\["uid"\]. If missing: JSON requests get 401, HTML requests redirect to /login?next={path}.

## **3.2  Profile System**

Profiles are stored in collab\_users/{uid} with a rich schema covering all professional dimensions.

### **Profile Schema Fields**

* Basic: name, email, headline, bio (250 char), location, website, github, linkedin

* Media: profile\_picture (filename), profile\_banner (filename)

* Education: array of {institution, degree, field, grade, gpa, from\_date, to\_date, current}

* Experience: array of {title, company, type, from\_date, to\_date, description, current}

* Volunteer: array of {organization, role, cause, from\_date, to\_date}

* Projects: array of {id, title, description, link, github, tech\_stack\[\], media\[\]}

* Publications: array of {title, journal, link, date}

* Patents: array of {title, number, date}

* Awards: array of {title, issuer, date}

* Languages: array of {language, proficiency}

* Certifications: array of {name, issuer, date, link}

* Skills: array of {name, endorsement\_count}

* Mentorship: mentorship\_available, mentorship\_focus\_areas\[\], mentorship\_preferences{time\_commitment, communication\_style, max\_mentees}, mentorship\_stats{total\_mentees, active\_mentees, completed\_mentorships, average\_rating}

* Counts: follower\_count, following\_count, connection\_count, post\_count

* Privacy: per-section visibility (public / connections / only\_me)

* Meta: profile\_completion (0–100), setup\_complete, created\_at, updated\_at

### **Profile Completion Scoring**

calculate\_profile\_completion() checks 11 criteria with weighted points:

| Criterion | Points |
| :---- | :---- |
| Profile photo uploaded | 10 |
| Headline filled in | 10 |
| Bio written (any text) | 10 |
| Education entry added | 15 |
| 3+ skills added | 10 |
| Experience OR project added | 15 |
| 5+ connections made | 10 |
| First post published | 10 |
| Recommendation received | 10 |
| Languages listed | 5 |
| Volunteer OR award added | 5 |

Returns: score (0–100), milestone label/color, list of completed criteria, list of missing criteria with suggested next action.

### **Privacy System**

DEFAULT\_PRIVACY defines section-level defaults. filter\_profile\_for\_viewer() respects these when returning profile data:

* Public sections: visible to all authenticated users

* Connections only: visible only to accepted connections

* Only Me: visible only to profile owner

### **Profile Photo Upload**

POST /profile/photo accepts multipart form upload. Validates: extension (png/jpg/jpeg/webp/gif), size (\<5MB). Saves to /static/media/ with UUID filename.

## **3.3  Setup Wizard**

/setup route renders a 5-step onboarding flow for new users. Steps: (1) Photo \+ headline \+ bio, (2) Education, (3) Skills, (4) Projects, (5) Privacy preferences. Completion sets setup\_complete=True on the profile document.

## **3.4  Connection System**

Symmetric connections stored in /connections/{conn\_id} where conn\_id \= sorted(\[uid\_a, uid\_b\]).join("\_"). This ensures uniqueness regardless of who sent the request.

### **Connection States**

* pending — request sent, awaiting recipient acceptance

* accepted — both users are connected

* declined — recipient declined (document kept for audit)

* withdrawn — sender withdrew before acceptance (document deleted)

### **Connection Types**

* peer — standard mutual connection

* mentor — requesting user asks to be mentored

* mentee — requesting user offers to mentor

### **Implemented Routes**

* POST /api/collab/connections/send — validates no existing connection, creates pending document

* POST /api/collab/connections/{id}/accept — validates recipient uid, sets status=accepted, increments both users' connection\_count

* POST /api/collab/connections/{id}/decline — sets status=declined

* POST /api/collab/connections/{id}/withdraw — deletes document if sender and still pending

* DELETE /api/collab/connections/{uid} — removes accepted connection, decrements counts

* GET /api/collab/connections — lists user's connections, pending sent, pending received

## **3.5  Follow System**

Asymmetric follow relationships stored in /follows/{follow\_id}. A user can follow anyone without mutual consent, like Twitter/Instagram follows. Separate from connections.

* POST /api/collab/follow/{uid} — creates follow document, increments follower/following counts

* DELETE /api/collab/follow/{uid} — removes follow document, decrements counts

update\_follow\_counts() uses Firestore increments to atomically update follower\_count and following\_count on both user documents.

## **3.6  Smart Suggestions Engine**

get\_smart\_suggestions(uid) scores all users against the requesting user using a multi-factor algorithm:

| Factor | Score Weight |
| :---- | :---- |
| Mutual connections | \+3 per mutual connection |
| Same school (AI fuzzy match) | \+5 if school name matches semantically |
| Shared skills (AI fuzzy match) | \+2 per shared skill |
| Same grade/year | \+1 |

AI matching uses sentence-transformers cosine similarity for school names (threshold 0.8) and skill names (threshold 0.7). Falls back to string similarity (Levenshtein-like) if AI unavailable. Results sorted by score descending, top 20 returned.

## **3.7  Mentorship System**

Mentorship is a specialised connection type with its own profile section and matching algorithm.

* GET /api/collab/mentorship/suggestions — runs get\_mentor\_suggestions() scoring based on field overlap, skill gaps, experience level, mentorship\_available flag

* PUT /api/collab/mentorship/profile — updates mentorship preferences (time commitment, communication style, max mentees, focus areas)

* POST /api/collab/mentorship/respond — accept/decline mentorship request

* GET /api/collab/mentorship/relationships — list active mentorships

* update\_mentorship\_stats() — called on accept/complete to update mentorship\_stats on mentor profile

## **3.8  Post System**

Posts are stored in /posts/{post\_id} with NLP analysis cached in the \_analysis field.

### **Post Creation**

POST /api/collab/posts validates content, calls create\_post() which:

* Sanitizes content via sanitize\_content() (bleach allowlist)

* Extracts hashtags via extract\_hashtags() (regex \#word pattern)

* Runs analyze\_post\_content() — semantic topic classification (20 student topics), TF-IDF keyword extraction, education level detection, semantic embedding (if AI available)

* Writes post document with \_analysis field

* Increments hashtag counts in /hashtags/{tag}

* Invalidates feed cache for author and all connections via invalidate\_feed\_for\_connections()

### **Post Reactions**

Three reaction types: insightful (💡), motivating (🔥), support (🙌). Each user can have one active reaction per post. POST /api/collab/posts/{id}/react updates reaction\_counts map on post document and emits post\_reaction SocketIO event to post\_{post\_id} room. DELETE removes reaction and emits post\_reaction\_removed.

### **Post Comments**

POST /api/collab/posts/{id}/comments stores comment in subcollection, increments post comment\_count, emits new\_comment SocketIO event. DELETE /api/collab/posts/{id}/comments/{comment\_id} validates author ownership, soft-deletes, emits comment\_deleted.

### **Post Deletion**

DELETE /api/collab/posts/{id} validates author, sets deleted=True (soft delete), invalidates feed caches.

## **3.9  Personalized Feed Algorithm**

get\_personalized\_feed() is the most sophisticated component of the current implementation. It runs a multi-signal scoring pipeline to rank posts for each user.

### **Algorithm Steps**

* 1\. Redis cache check — if feed cached for uid+cursor, return immediately

* 2\. Build user interest profile — from skills, education, experience, projects (cached 1hr)

* 3\. Pre-load connection set and follow set — 2 Firestore queries

* 4\. Fetch candidate posts — single query, max(60, limit×5) candidates, ordered by created\_at DESC, cursor-based pagination

* 5\. Batch-fetch author profiles — db.get\_all() for all unique author UIDs in one call

* 6\. Score each candidate — relevance \+ social proof \+ freshness \+ own post boost

* 7\. Diversity cap — max 2 posts per author per page

* 8\. Sort by score DESC, take top N

* 9\. Cache result in Redis (5min TTL)

### **Scoring Breakdown**

| Signal | Max Points |
| :---- | :---- |
| Cosine similarity: user embedding vs post embedding (AI) | 40 pts |
| User skills ∩ post hashtags/keywords (always-on) | 30 pts |
| User education/experience ∩ post topics/keywords | 20 pts |
| User project keywords ∩ post keywords | 15 pts |
| Education level alignment (beginner/intermediate/advanced) | 10 pts |
| Social proof: direct connection author | 30 pts |
| Social proof: followed author | 15 pts |
| Social proof: author credibility (verified, connections, followers) | 20 pts |
| Freshness: \<1hr=10, \<6hr=8, \<24hr=6, \<72hr=4, \<168hr=2, else=1 | 10 pts |
| Own post boost | \+15 pts |

## **3.10  Hashtag System**

Hashtags are extracted from posts automatically. Each post can have multiple hashtags stored as an array. Hashtag pages (/collab/hashtag/{tag}) show all posts tagged with that hashtag and trending sidebar. get\_trending\_hashtags() returns top 10 hashtags by post count (cached 10min).

## **3.11  Search System**

People search (/collab/search) and post search (/api/collab/search/posts) with multi-criteria filtering.

* People: name, school, skill, headline full-text — fuzzy matching with lenient fallback

* Posts: query text, date range, hashtag filter

* get\_fuzzy\_matches() — Levenshtein distance for typo tolerance

* lenient\_matches\_search\_criteria() — relaxed scoring when strict match returns 0 results

## **3.12  User Interest Tracking**

build\_user\_interest\_profile(uid) aggregates interests from the user's profile data with per-category weights:

| Category | Weight in Interest Profile |
| :---- | :---- |
| Skills | 0.30 (highest — explicit declaration) |
| Education (field \+ degree) | 0.20 |
| Experience (title \+ company) | 0.20 |
| Projects (title \+ tech stack \+ desc keywords) | 0.15 |
| Schools attended | 0.10 |
| Mentorship focus areas | 0.05 |

Interaction tracking (POST /api/collab/interactions/track) records post views, reactions, comments, shares to build implicit interest signals. Interest insights are accessible at GET /api/collab/insights/interests.

## **3.13  Current Templates**

| Template | Status / Purpose |
| :---- | :---- |
| collab\_base.html | ✅ Base layout — nav, dark/light mode, SocketIO |
| collab\_login.html | ✅ Standalone login with theme toggle, password toggle |
| collab\_register.html | ✅ Registration with password strength meter |
| collab\_dashboard.html | ✅ Feed with post creation, personalized posts, sidebar |
| collab\_profile.html | ✅ Full profile view with all sections |
| collab\_profile\_edit.html | ✅ Edit all profile sections |
| collab\_setup\_wizard.html | ✅ 5-step onboarding wizard |
| collab\_network.html | ✅ Connections list, pending requests, suggestions preview |
| collab\_suggestions.html | ✅ Full suggestions page with sort/filter |
| collab\_search.html | ✅ People \+ post search |
| collab\_users.html | ✅ Browsable user directory |
| collab\_mentorship.html | ✅ Mentorship requests and active relationships |
| collab\_post.html | ✅ Single post view with comments and reactions |
| collab\_hashtag.html | ✅ Hashtag feed with trending sidebar |
| collab\_messages.html | ⚠️ STUB — "Coming Soon" placeholder only |
| collab\_error.html | ✅ Error page (403/404/500) |

# **PART 4 — CURRENT USER FLOWS**

## **4.1  New User Onboarding**

* User visits / → redirected to /login (if no session)

* /login: submits email+password → Firebase REST signInWithPassword

* No account? → /register → creates Firebase Auth user \+ collab\_users doc → auto-login

* First login: setup\_complete=False → redirect to /setup wizard

* /setup Step 1: Upload photo, enter headline and bio

* /setup Step 2: Add education entries

* /setup Step 3: Add skills (minimum 3 recommended)

* /setup Step 4: Add projects (optional)

* /setup Step 5: Set privacy preferences

* Wizard completion: sets setup\_complete=True → redirect to /dashboard

## **4.2  Feed and Post Flow**

* User lands on /dashboard → get\_personalized\_feed() runs → ranked posts displayed

* Post creation: click "Share something..." → modal opens with content area, image upload, hashtag support

* Submit post: sanitized, hashtags extracted, NLP analysis run, feed caches invalidated

* Post in feed: click reaction button → AJAX POST to /api/collab/posts/{id}/react → count updates via SocketIO

* Click "Comments" → navigate to /collab/post/{id} or inline expand

* Add comment → AJAX POST, SocketIO broadcasts new\_comment to all viewers of that post

* Click hashtag → /collab/hashtag/{tag} → shows all posts with that tag

* Infinite scroll: AJAX GET /api/collab/feed?cursor={cursor} → appends new posts

## **4.3  Profile Flow**

* Visit own profile /profile/{uid} → full view with edit buttons

* Edit profile: click section edit → inline modal or /profile/edit → save → back

* Visit others profile: connection status shown → Connect / Follow / Message / Endorse buttons

* Endorse a skill: POST /api/skills/{skill}/endorse → adds uid to endorsers, increments count

* Request recommendation: POST /api/recommendations/request → creates rec\_inbox item for target user

* Profile completion meter visible on own profile and dashboard sidebar

## **4.4  Network Flow**

* Visit /collab/network → see connections (by user\_a and user\_b queries), pending sent, pending received

* Accept request: POST /api/collab/connections/{id}/accept → updates status, updates counts

* Decline: POST /api/collab/connections/{id}/decline

* Withdraw sent request: POST /api/collab/connections/{id}/withdraw

* Remove connection: DELETE /api/collab/connections/{uid}

* Visit /collab/network/suggestions → smart suggestions with score-based ranking

* Visit /collab/users → browsable directory with client-side search

## **4.5  Search Flow**

* Navigate to /collab/search → search field with filters (school, skill, date)

* Submit: GET /api/collab/search?q={query}\&school={s}\&skill={s}

* Results: scored by exact \+ fuzzy name match, skill match, school match

* Post search: GET /api/collab/search/posts?q={query} → scored by keyword overlap, hashtag match

## **4.6  Mentorship Flow**

* Visit /collab/mentorship → shows mentor suggestions, active mentorships, received requests

* Set mentorship availability: PUT /api/collab/mentorship/profile

* Request mentorship: POST /api/collab/mentorship/request → creates connection with type=mentor

* Accept/decline: POST /api/collab/mentorship/respond → updates connection status, updates stats

# **PART 5 — PLANNED FEATURES**

## **5.1  Feature Status Overview**

| Feature / Module | Status | Notes |
| :---- | :---: | :---- |
| **Auth \+ Registration** | **✅ DONE** |  |
| **Extended Profile System** | **✅ DONE** |  |
| **Connections \+ Follows** | **✅ DONE** |  |
| **Smart Suggestions** | **✅ DONE** |  |
| **Mentorship System** | **✅ DONE** |  |
| **Feed \+ Posts \+ Reactions** | **✅ DONE** |  |
| **Hashtag Pages** | **✅ DONE** |  |
| **Personalized Feed (AI)** | **✅ DONE** |  |
| **Redis Caching Layer** | **✅ DONE** |  |
| **Security Hardening** | **🔴 NEEDED** |  |
| **Long-form Articles** | **🟡 PLANNED** |  |
| **Post Save \+ Bookmark** | **🟡 PLANNED** |  |
| **Post Share/Repost** | **🟡 PLANNED** |  |
| **Comment Threading (2-level)** | **🟡 PLANNED** |  |
| **Notification System** | **🟡 PLANNED** |  |
| **Private Groups (Study)** | **🟡 PLANNED** |  |
| **Public Groups (Community)** | **🟡 PLANNED** |  |
| **Direct Messaging (3 types)** | **🟡 PLANNED** |  |
| **Activity Log** | **🟡 PLANNED** |  |
| **Mobile Bottom Nav** | **🟡 PLANNED** |  |
| **Rate Limiting** | **🔴 NEEDED** |  |
| **CSRF Protection** | **🔴 NEEDED** |  |

## **5.2  Groups System (Detailed Spec)**

Groups come in two fundamentally different types with different feature sets, access models, and Firestore schemas.

### **Type A — Private Groups (Study Groups)**

Private groups are intimate, invitation-only spaces for students to collaborate with their existing connections. Designed for study partners, project teams, and friend groups.

* Access: invitation-only from connections; no public discovery

* Size: small (2–50 members recommended)

* Member roles: Admin (creator auto-assigned), Member

* Admin capabilities: rename group, delete group, invite members from connections, remove members, promote/demote members

* Features:

  * Group Chat — real-time chat room (single room per group, SocketIO room: grpchat\_{group\_id})

  * Group Forum — post/comment discussion board visible only to members

  * Group Goals — shared goal tracking with progress, due dates, assignments

  * Group Files — file sharing (upload/download), stored under groups/{group\_id}/files/

  * Invite system — admin selects from connections list → sends group\_invite notification

### **Type B — Public Groups (Community Groups)**

Public groups are open communities for topics, interests, and institutions. Designed for large-scale collaboration, subject communities, and institutional groups.

* Access: publicly listed and joinable; searchable by topic tags

* Size: unlimited (designed for hundreds to thousands of members)

* Member roles: Admin, Moderator, Member

* Admin capabilities: rename group, delete group, invite people, remove members, promote to Moderator, create folders, create chatrooms, create events, pin posts

* Moderator capabilities: pin posts, remove posts, remove members, create events

* Features:

  * Group Forum — threaded discussion board, public posts visible to all members, pinnable posts

  * Group Folders — admin-created folder structure for organized file sharing

  * Group Files — files uploaded into folders, downloadable by all members

  * Group Chatrooms — multiple named chatrooms per group (e.g., \#general, \#resources, \#off-topic)

  * Group Events — event creation with title, description, date/time, location (physical or virtual URL)

  * Calendar Integration — each event generates a calendar link (Google Calendar, iCal .ics download)

  * Events Calendar View — monthly/weekly calendar view of group events

  * RSVP System — Going / Maybe / Not Going per event, attendee count

### **Shared Group Fields (Firestore: /groups/{group\_id})**

group\_id: string (auto)

name: string

description: string

type: "private" | "public"

topic\_tags: string\[\]           \# public groups only

banner\_image: string | null

creator\_uid: string

admin\_uids: string\[\]

moderator\_uids: string\[\]       \# public groups only

member\_count: int

created\_at: ISO timestamp

updated\_at: ISO timestamp

deleted: bool

### **Group Member Document (groups/{group\_id}/members/{uid})**

uid: string

role: "admin" | "moderator" | "member"

joined\_at: ISO timestamp

invited\_by: string | null

status: "active" | "removed"

### **Group Event Document (groups/{group\_id}/events/{event\_id})**

title: string

description: string

start\_datetime: ISO timestamp

end\_datetime: ISO timestamp | null

location\_type: "physical" | "virtual"

location\_address: string | null       \# physical

virtual\_url: string | null            \# virtual

rsvp\_going: string\[\]                  \# UIDs

rsvp\_maybe: string\[\]

rsvp\_not\_going: string\[\]

calendar\_link\_google: string          \# generated URL

ical\_data: string                     \# iCal format string

created\_by: string

created\_at: ISO timestamp

## **5.3  Messaging System (Detailed Spec)**

Direct messaging operates in three distinct modes, each with different UX patterns and Firestore paths.

### **Mode 1 — Connection Direct Message**

Standard real-time chat between two accepted connections.

* Accessible: from connection's profile, from network page, from messages hub

* DM room ID: dm\_{min(uid\_a,uid\_b)}\_{max(uid\_a,uid\_b)}

* Features: text messages, emoji reactions to messages, file sharing (images, PDFs, any file type), read receipts (double tick), typing indicator (ephemeral — not stored), message delete (own messages only)

* SocketIO events: collab\_dm\_send, collab\_dm\_read, collab\_dm\_react, collab\_typing

* No request required — both parties are connections

### **Mode 2 — Non-Connection Message Request**

A controlled-access messaging flow for non-connections. Prevents spam while enabling discovery.

* Sender side:

  * Sends a message request (not visible to recipient until they check requests)

  * Pre-formatted message templates available: Recommendation Request, Help/Advice Request, Collaboration Invite, Project Inquiry, Job/Opportunity Reference

  * Can write custom message alongside or instead of template

  * Message marked "pending" — sender sees "Request Sent" status

* Recipient side (shown in Networks → Message Requests tab):

  * See sender profile card, profile picture, headline, mutual connections

  * See the message preview (first 200 chars)

  * Pre-formatted response templates: Accept with welcome message, Decline politely, Accept with note, Decline with reason

  * On accept: DM thread created, both users can now chat; sender gets notification

  * On decline: request deleted, sender gets "request not accepted" notification

* Stored in: /message\_requests/{req\_id}

### **Mode 3 — Mentor/Mentee Direct Message**

Enhanced chat between established mentor-mentee connection pairs. Adds scheduling tools on top of standard chat.

* Accessible only when a mentor/mentee connection exists (type \= "mentor" or "mentee")

* All standard connection DM features included

* Additional features:

  * Session Scheduler — calendar widget to propose a meeting time

  * Google Calendar Link Generator — creates shareable calendar event link

  * iCal download for the proposed session

  * Scheduled sessions list visible in chat sidebar

  * Session notes — lightweight rich text note attached to each scheduled session

* UI distinguishes this chat type with mentor badge on header

### **DM Firestore Schema**

/direct\_messages/{dm\_id}

  participants: \[uid\_a, uid\_b\]

  last\_message: string

  last\_message\_at: ISO timestamp

  last\_sender\_uid: string

  unread\_count\_a: int

  unread\_count\_b: int

  connection\_type: "connection" | "request" | "mentor"

  is\_mentor\_chat: bool

/direct\_messages/{dm\_id}/messages/{msg\_id}

  sender\_uid: string

  content: string

  type: "text" | "file" | "image" | "system"

  file\_url: string | null

  file\_name: string | null

  read\_by: string\[\]        \# UIDs who have read this

  reactions: {uid: emoji}

  created\_at: ISO timestamp

  deleted: bool

/message\_requests/{req\_id}

  from\_uid: string

  to\_uid: string

  template\_type: string | null

  message: string

  status: "pending" | "accepted" | "declined"

  created\_at: ISO timestamp

## **5.4  Notification System (Detailed Spec)**

A centralised notification system that receives triggers from all existing and planned systems.

### **Notification Types and Triggers**

| Type | Trigger | Recipient |
| :---- | :---- | :---- |
| connection\_request | User A sends connection request to User B | User B |
| connection\_accepted | User B accepts User A's request | User A |
| connection\_declined | User B declines User A's request | User A |
| endorsement | User A endorses User B's skill | User B |
| rec\_request | User A requests recommendation from B | User B |
| rec\_received | User B writes and sends recommendation to A | User A |
| post\_reaction | User A reacts to User B's post | User B (post author) |
| post\_comment | User A comments on User B's post | User B (post author) |
| post\_mention | User A mentions @User B in post/comment | User B |
| post\_share | User A shares User B's post | User B |
| mentorship\_request | User A requests mentorship from User B | User B |
| mentorship\_accepted | User B accepts mentorship from User A | User A |
| group\_invite | Admin invites User to a group | User |
| group\_post | New post in a group User is in | All group members |
| group\_event | New event in a group User is in | All group members |
| dm\_message | New DM received | Recipient |
| message\_request | Non-connection sends message request | Recipient |
| message\_request\_accepted | Recipient accepts message request | Sender |
| follow | User A follows User B | User B |

### **Notification Document Schema (/notifications/{notif\_id})**

recipient\_uid: string

type: string              \# from types above

actor\_uid: string         \# who triggered it

actor\_name: string        \# cached for display

actor\_picture: string | null

entity\_id: string         \# post\_id, conn\_id, group\_id etc.

entity\_type: string       \# "post" | "connection" | "group" | "dm"

message: string           \# human-readable e.g. "Alex endorsed your Python skill"

read: bool                \# false initially

created\_at: ISO timestamp

### **Delivery Mechanism**

* On notification creation: write to Firestore, then emit SocketIO event to user\_{recipient\_uid} room

* SocketIO event name: new\_notification — payload includes type, message, entity\_id, actor\_picture

* Client-side handler: increment badge counter in nav, show toast

* Badge: red dot / count on Messages icon and bell icon in nav

* GET /api/collab/notifications?limit=20\&cursor={} — paginated list

* POST /api/collab/notifications/{id}/read — mark single as read

* POST /api/collab/notifications/read-all — mark all as read

# **PART 6 — PLANNED USER FLOWS**

## **6.1  Notification Flow**

* Any triggering action (reaction, connection, comment, etc.) calls create\_notification()

* Firestore write to /notifications/{notif\_id}

* SocketIO emit to user\_{recipient\_uid} room → client increments badge

* User clicks bell icon → /collab/notifications → list of unread (highlighted) \+ read

* Click notification → navigate to entity (post, profile, group, DM thread)

* Mark all read → badge clears

## **6.2  Private Group (Study Group) Flow**

* User clicks "Create Group" → selects type "Private Study Group"

* Enters name, description → group created with creator as Admin

* Admin sees group page: Chat tab, Forum tab, Goals tab, Files tab

* Invite: Admin clicks "Invite" → selects from connections list → invitee gets notification

* Invitee: receives group\_invite notification → visits group page → "Accept" or "Decline" invite

* Group Chat: real-time messages, file attachments, SocketIO room grpchat\_{group\_id}

* Group Goals: Admin/any member creates goal with title, description, due date, assigned members; members mark progress; completion tracked as %

* Group Files: any member uploads file → appears in shared files list; any member can download

* Group Forum: any member posts → shows in forum feed; reactions, comments supported

* Admin moderation: remove member (with confirmation), rename group, delete group

## **6.3  Public Group Flow**

* User browses /collab/groups → discovery grid filtered by topic tags

* Click group → group landing page (forum visible to all) with "Join" button

* Join: becomes Member, gains access to all tabs

* Forum tab: threaded posts, emoji reactions, pinned posts shown at top

* Folders tab: Admin-created folder hierarchy; members upload files into folders

* Chatrooms tab: list of named chatrooms → click to enter → real-time SocketIO chat

* Events tab: calendar view \+ list view; upcoming events with RSVP

* Event detail: title, description, date/time, location; RSVP buttons; Google Calendar link; iCal download

* Admin panel: accessible to admin\_uids only → manage members/roles, create folders/chatrooms, pin posts, create events

## **6.4  Direct Message — Connection**

* User visits connection's profile → click "Message" button

* Or: visit /collab/messages → DM list → click existing thread or "New Message"

* Chat window opens: message history loaded, SocketIO room joined (dm\_{pair})

* Type message → send → persisted to Firestore, emitted via SocketIO to both participants

* Recipient sees new message in real-time, unread count increments

* File attachment: click paperclip → file picker → upload → file message type stored

* React to message: hover/long-press → emoji picker → reaction stored and emitted

* Typing indicator: emit collab\_typing (ephemeral, not stored) → recipient sees "... is typing"

## **6.5  Direct Message — Non-Connection Request**

* User A views User B's profile (not connected) → "Message" button shows "Send Request"

* Click → modal opens with: template picker (Recommendation / Help / Collaboration / Inquiry) \+ custom message field

* Submit → /message\_requests/{req\_id} created, User B gets message\_request notification

* User B: visits /collab/network → "Message Requests" tab → sees User A's card \+ message preview

* User B: selects pre-formatted response (Accept with welcome / Decline politely / custom) → submits

* On accept: DM thread created, User A gets message\_request\_accepted notification, both can now chat

* On decline: User A gets notification, request document deleted

## **6.6  Direct Message — Mentor/Mentee**

* User A and User B have an accepted mentor/mentee connection

* Either user visits messages hub → sees mentor chat (labelled with mentor badge)

* Chat opens: all standard DM features active

* Schedule meeting: click calendar icon → mini calendar picker → select date/time → add title

* Submit: generates Google Calendar link and .ics data, stores as scheduled\_sessions entry in DM doc

* Both users see scheduled session in chat sidebar with Google Calendar and iCal buttons

* Session notes: click session → notes editor opens → rich text notes saved to session

## **6.7  Articles Flow (Planned Phase 3B)**

* User clicks "Write Article" on dashboard or profile

* Rich text editor loads (/collab/articles/new) — Quill.js editor with formatting toolbar

* Auto-save as draft every 30 seconds (PUT /api/collab/articles/{id})

* Hashtags, title, cover image added

* Publish: POST /api/collab/articles/{id}/publish → NLP analysis run → appears in feed as article card

* Article card in feed shows: title, author, first 200 chars of content, read time estimate, cover image

* Full article reader: /collab/article/{id} → full content, reactions, comments, author card

# **PART 7 — IMPLEMENTATION PHASES**

The following phases build on the current state of the codebase. Each phase includes a PRD, data architecture, logic flow, and complete implementation prompt.

**PHASE 0  SECURITY HARDENING  \[IMMEDIATE — DO FIRST\]**

Critical security fixes that must be applied before any new feature work. These address active risks in the current production codebase.

## **Phase 0 — PRD**

* Gate all /debug/\* routes behind FLASK\_ENV \== development check — they mutate production data

* Add Flask-Limiter: rate-limit POST /api/collab/posts (10/min), connections/send (20/hr), login (5/min), reactions (30/min)

* Raise RuntimeError if SECRET\_KEY env var is missing in non-development environments

* Change SocketIO cors\_allowed\_origins from "\*" to configured domain list

* Remove duplicate /api/collab/feed route (line 1043 in collab.py — dead code)

* Replace {{ post.content|safe }} in dashboard and post templates with a safe nl2br filter that does not bypass Jinja2 escaping

* Add CSRF token for non-JSON POST routes (Flask-WTF or custom header check)

***📋 Windsurf / Claude Prompt — Phase 0 — Security Hardening***

You are working on ScleraCollab (collab.py, collab\_utils.py). Apply the following security fixes:1. Gate all /debug/\* routes: add \`if os.environ.get("FLASK\_ENV") \!= "development": abort(404)\` as the first line of each debug route handler.2. Install and configure Flask-Limiter. Apply limits: login (5/min), register (10/hour), api\_create\_post (10/min per user), api\_send\_connection\_request (20/hour per user), api\_add\_reaction (30/min per user).3. At app startup (after load\_dotenv()), add: \`if not app.debug and not app.testing and app.secret\_key \== "collab-standalone-dev-secret": raise RuntimeError("SECRET\_KEY env var not set for production")\`4. Change SocketIO init to: \`socketio \= SocketIO(app, cors\_allowed\_origins=os.environ.get("ALLOWED\_ORIGINS", "").split(",") or "\*", async\_mode="threading")\`5. Delete the FIRST /api/collab/feed route (the one at line \~1043 that calls get\_feed\_posts). Keep only the second one (line \~2622) which calls get\_personalized\_feed.6. Create a new Jinja2 filter \`safe\_nl2br\` that escapes HTML first, then replaces \\n with \<br\>. Replace all {{ x|safe }} with {{ x|safe\_nl2br }}.Do not change any other functionality.

**PHASE 3B  ARTICLES \+ COMMENT THREADING \+ SAVE/SHARE  \[NEXT UP\]**

Completes the content system with long-form articles, saves, share/repost, and 2-level comment threading.

## **Phase 3B — PRD**

* Long-form article creation via Quill.js rich text editor

* Article draft auto-save (30s interval)

* Article publishing with NLP analysis (same pipeline as posts)

* Article rendering in feed as card (title \+ excerpt \+ read time)

* Full article reader page

* Post bookmark/save: toggle save on any post, view saved posts in profile

* Post share/repost: create new post with optional quote, embed original post card

* 2-level comment threading: reply to a comment (parent\_comment\_id field)

## **Phase 3B — Data**

/articles/{article\_id}

  author\_uid, title, content (HTML), cover\_image

  hashtags\[\], status: "draft"|"published"

  read\_time\_minutes: int

  reaction\_counts, comment\_count, view\_count

  \_analysis: {topics, keywords, education\_level}

  created\_at, published\_at, updated\_at, deleted

/collab\_users/{uid}/saved\_posts/{post\_id}

  saved\_at: ISO timestamp

  post\_type: "post" | "article"

posts/{post\_id} — new fields:

  share\_count: int

  original\_post\_id: string | null   \# if this is a repost

  quote\_content: string | null       \# quote added on repost

posts/{post\_id}/comments/{comment\_id} — new field:

  parent\_comment\_id: string | null   \# for threading

  depth: 0 | 1                       \# max 2 levels

## **Phase 3B — Logic Flow**

* Article: POST /api/collab/articles (create draft) → returns article\_id

* PUT /api/collab/articles/{id} (auto-save) → overwrites content, does not re-run NLP

* POST /api/collab/articles/{id}/publish → run analyze\_post\_content(), set status=published, add to feed

* Save post: POST /api/collab/posts/{id}/save → write to saved\_posts subcollection → update save\_count on post

* Share: POST /api/collab/posts/{id}/share → create new post with original\_post\_id and optional quote\_content → increment share\_count on original → invalidate feed caches

* Comment reply: POST /api/collab/posts/{id}/comments with parent\_comment\_id → if depth=0 allowed, if depth=1 rejected (max 2 levels)

* Feed renders: check original\_post\_id → if present, fetch original post and embed as card within share post

***📋 Windsurf / Claude Prompt — Phase 3B — Articles, Save, Share, Threading***

Extend ScleraCollab (collab.py, collab\_utils.py). Implement the following:1. ARTICLES:   \- New Firestore collection /articles/{article\_id} (schema as documented).   \- Routes: POST /api/collab/articles (create draft), PUT /api/collab/articles/{id} (auto-save), POST /api/collab/articles/{id}/publish (run NLP, set published), GET /collab/article/{id} (reader), GET /collab/articles/new (editor).   \- Create collab\_article\_editor.html: Quill.js CDN editor, title input, cover image upload, hashtag input, save draft button, publish button, auto-save every 30s.   \- Create collab\_article.html: full content render, author card, reactions, comments, related articles sidebar.   \- In feed, render article type posts as cards: title prominent, first 200 chars excerpt, estimated read time, cover image thumbnail.2. SAVE/BOOKMARK:   \- POST /api/collab/posts/{id}/save and DELETE /api/collab/posts/{id}/save → toggle save in collab\_users/{uid}/saved\_posts/{post\_id}.   \- GET /api/collab/posts/saved → list user's saved posts.   \- Add bookmark icon to every post card in dashboard and post templates. Show filled state if saved.3. SHARE/REPOST:   \- POST /api/collab/posts/{id}/share with optional {quote\_content}.   \- Creates new post with original\_post\_id \+ quote\_content, increments share\_count on original.   \- In feed templates, detect original\_post\_id and render embedded original post card.4. COMMENT THREADING:   \- Update POST /api/collab/posts/{id}/comments to accept optional parent\_comment\_id.   \- Validate depth: if parent comment has depth=1, reject (max 2 levels).   \- Update collab\_post.html to render nested replies under each top-level comment with indent and "Reply" button.   \- SocketIO emit new\_comment includes parent\_comment\_id so client renders in correct position.5. Wire create\_notification() (stub it if Phase 5 not done yet) for: post\_share triggers notification to original author.

**PHASE 4A  NOTIFICATION SYSTEM  \[BUILD BEFORE GROUPS/DMS\]**

Cross-cutting notification infrastructure that all subsequent phases depend on.

## **Phase 4A — PRD**

* create\_notification() helper function in collab\_utils.py

* GET /api/collab/notifications — paginated, most recent first

* POST /api/collab/notifications/{id}/read — mark single read

* POST /api/collab/notifications/read-all — mark all read

* GET /collab/notifications — notification center page

* Real-time badge in collab\_base.html nav via SocketIO

* Toast notification UI on new notification

* Wire existing systems: connection accept, endorsement, recommendation, post reaction, post comment

## **Phase 4A — Data**

/notifications/{notif\_id}

  recipient\_uid: string

  type: string             \# see type list in Part 5.4

  actor\_uid: string

  actor\_name: string       \# cached at creation time

  actor\_picture: string | null

  entity\_id: string

  entity\_type: string

  message: string          \# e.g. "Priya reacted 💡 to your post"

  read: bool

  created\_at: ISO timestamp

## **Phase 4A — Logic Flow**

* create\_notification(recipient\_uid, type, actor\_uid, actor\_name, actor\_picture, entity\_id, entity\_type, message) → writes to /notifications → emits new\_notification to user\_{recipient\_uid} SocketIO room

* Client: listen on new\_notification → increment badge count in localStorage → show toast (fade out after 4s)

* Notification center page: GET /api/collab/notifications → paginated list, unread highlighted in accent color

* Click notification: mark read, navigate to entity

***📋 Windsurf / Claude Prompt — Phase 4A — Notification System***

Implement the notification system for ScleraCollab.1. In collab\_utils.py, add create\_notification(recipient\_uid, type, actor\_uid, actor\_name, actor\_picture, entity\_id, entity\_type, message) function. It should:   \- Write to /notifications/{auto\_id} with all fields \+ read=False \+ created\_at   \- Import socketio from collab.py (or pass it as parameter) and emit "new\_notification" to user\_{recipient\_uid} room with {type, message, entity\_id, actor\_picture, count: unread\_count}   \- Return the notification ID2. In collab.py, add:   \- GET /api/collab/notifications?cursor=\&limit=20 — query /notifications where recipient\_uid==uid, order by created\_at DESC, cursor-based pagination   \- POST /api/collab/notifications/{id}/read — update read=True   \- POST /api/collab/notifications/read-all — batch update all unread for uid   \- GET /collab/notifications — render collab\_notifications.html3. Create collab\_notifications.html extending collab\_base.html:   \- Grouped by date (Today, Yesterday, Earlier)   \- Each notification: actor avatar, message text, timestamp, unread dot (green)   \- "Mark all read" button at top   \- Click navigates to entity and marks read   \- Empty state: friendly illustration4. In collab\_base.html nav, add a bell icon with a badge \<span id="notif-badge"\> that:   \- Loads unread count on page load via GET /api/collab/notifications?unread\_only=true\&limit=1   \- Listens on SocketIO "new\_notification" event → increment badge, show toast   \- Hides badge when count is 05\. Wire create\_notification() into these existing routes:   \- api\_accept\_connection → notify sender: connection\_accepted   \- api\_add\_reaction → notify post author: post\_reaction (skip if author \== reactor)   \- api\_add\_comment → notify post author: post\_comment (skip if author \== commenter)   \- api skills endorse → notify endorsed user: endorsement   \- api\_send\_connection\_request → notify recipient: connection\_request

**PHASE 4B  PRIVATE GROUPS (STUDY GROUPS)  \[PHASE 4B\]**

Invitation-only study groups with chat, forum, goals, and file sharing.

## **Phase 4B — PRD**

* Create private group: name, description, type=private

* Creator becomes Admin automatically

* Group features: Forum, Chat, Goals, Files tabs

* Invite from connections only (Admin action)

* Admin controls: rename, delete, remove members, invite

* Group chat: single real-time chatroom per private group

* Group goals: create/track/complete shared goals

* Group files: upload/download shared files

* Group forum: posts visible only to members

## **Phase 4B — Data**

/groups/{group\_id} — type="private"

/groups/{group\_id}/members/{uid}

/groups/{group\_id}/posts/{post\_id}    \# forum posts

/groups/{group\_id}/files/{file\_id}

  file\_id, name, url, size, uploaded\_by, uploaded\_at

/groups/{group\_id}/goals/{goal\_id}

  title, description, due\_date

  assigned\_uids: string\[\]

  progress: int (0-100)

  status: "active"|"completed"

  created\_by, created\_at

***📋 Windsurf / Claude Prompt — Phase 4B — Private Groups (Study Groups)***

Implement private study groups for ScleraCollab.FIRESTORE COLLECTIONS:- /groups/{group\_id}: id, name, description, type="private", creator\_uid, admin\_uids\[\], member\_count, created\_at, deleted- /groups/{group\_id}/members/{uid}: uid, role ("admin"|"member"), joined\_at, invited\_by- /groups/{group\_id}/posts/{post\_id}: standard post schema, visible to members only- /groups/{group\_id}/files/{file\_id}: name, url, size, uploaded\_by, uploaded\_at- /groups/{group\_id}/goals/{goal\_id}: title, description, due\_date, assigned\_uids\[\], progress (0-100), status, created\_by, created\_atROUTES (add to collab.py):- POST /api/collab/groups — create group, auto-add creator as admin member- GET /collab/groups — groups discovery \+ My Groups (private section)- GET /collab/groups/{id} — group detail page- POST /api/collab/groups/{id}/invite — admin only, from connections, sends group\_invite notification via create\_notification()- POST /api/collab/groups/{id}/invite/respond — accept/decline invite- POST /api/collab/groups/{id}/leave — remove self from group- DELETE /api/collab/groups/{id}/members/{uid} — admin only, remove member- PUT /api/collab/groups/{id} — admin only, rename- DELETE /api/collab/groups/{id} — admin only, soft delete- POST /api/collab/groups/{id}/posts — create forum post (member only)- POST /api/collab/groups/{id}/files — upload file (member only)- GET /api/collab/groups/{id}/files — list files- POST /api/collab/groups/{id}/goals — create goal (member only)- PUT /api/collab/groups/{id}/goals/{goal\_id} — update progress/statusTEMPLATES:- collab\_groups.html: "My Private Groups" section \+ "Create Group" modal- collab\_group\_detail.html (private): 4 tabs — Forum | Chat | Goals | Files  \- Forum: post list with member-only posts, create post button  \- Chat: embedded single chat room, SocketIO room grpchat\_{group\_id}  \- Goals: goal cards with progress bars, create goal button (admin)  \- Files: file list with upload/download buttons  \- Admin panel (admin only): invite from connections modal, member list with remove buttons, rename group, danger zone (delete)SOCKETIO:- @socketio.on("join\_group\_chat") → join\_room(f"grpchat\_{group\_id}") after verifying membership- @socketio.on("group\_chat\_message") → persist to /groups/{id}/messages/{auto\_id}, emit to grpchat\_{group\_id}NOTIFICATIONS: on invite → create\_notification(invitee\_uid, "group\_invite", admin\_uid, ...)

**PHASE 4C  PUBLIC GROUPS (COMMUNITY GROUPS)  \[PHASE 4C\]**

Open communities with folders, multiple chatrooms, events calendar, and admin/moderator roles.

## **Phase 4C — PRD**

* Publicly discoverable groups, open join (no invite needed)

* Three roles: Admin, Moderator, Member

* Forum: threaded posts, pinnable, moderation tools

* Folder system: Admin-created folders → file upload into folders

* Multiple named chatrooms per group (Admin creates them)

* Events: create event with title, date/time, location, virtual URL

* Calendar integration: Google Calendar link \+ iCal download per event

* RSVP: Going / Maybe / Not Going with counts

* Events calendar view (monthly grid)

* Group discovery page with topic tag filtering

## **Phase 4C — Data**

/groups/{group\_id} — type="public"

  topic\_tags: string\[\]

  moderator\_uids: string\[\]

/groups/{group\_id}/folders/{folder\_id}

  name, parent\_folder\_id (null for root), created\_by, created\_at

/groups/{group\_id}/folders/{folder\_id}/files/{file\_id}

  name, url, size, uploaded\_by, uploaded\_at

/groups/{group\_id}/chatrooms/{room\_id}

  name, created\_by, created\_at, message\_count

/groups/{group\_id}/chatrooms/{room\_id}/messages/{msg\_id}

  sender\_uid, content, created\_at, deleted

/groups/{group\_id}/events/{event\_id}

  (full schema in Part 5.2)

***📋 Windsurf / Claude Prompt — Phase 4C — Public Groups***

Implement public community groups for ScleraCollab, extending the groups system from Phase 4B.PUBLIC GROUP ADDITIONS:- Group creation: add type="public" option, topic\_tags\[\] field, moderator\_uids\[\] field- Group discovery: GET /collab/groups shows public groups grid, filterable by topic\_tags- Open join: POST /api/collab/groups/{id}/join — no invite needed, adds as memberADDITIONAL COLLECTIONS:- /groups/{group\_id}/folders/{folder\_id}: name, parent\_folder\_id, created\_by- /groups/{group\_id}/folders/{folder\_id}/files/{file\_id}: name, url, size, uploaded\_by- /groups/{group\_id}/chatrooms/{room\_id}: name, created\_by (admin only to create)- /groups/{group\_id}/chatrooms/{room\_id}/messages/{msg\_id}: sender\_uid, content, created\_at- /groups/{group\_id}/events/{event\_id}: full event schema from Part 5.2ROUTES:- POST /api/collab/groups/{id}/join and /leave- POST /api/collab/groups/{id}/folders — admin only, create folder- POST /api/collab/groups/{id}/folders/{fid}/files — upload file into folder- GET /api/collab/groups/{id}/folders — tree structure- POST /api/collab/groups/{id}/chatrooms — admin only, create named chatroom- GET /api/collab/groups/{id}/chatrooms — list chatrooms- POST /api/collab/groups/{id}/events — admin/mod only, create event- POST /api/collab/groups/{id}/events/{eid}/rsvp — member RSVP- GET /collab/groups/{id}/events — events pageCALENDAR INTEGRATION:For each event, generate:- Google Calendar URL: https://calendar.google.com/calendar/render?action=TEMPLATE\&text={title}\&dates={start}/{end}\&details={desc}\&location={loc}- iCal string: RFC 5545 format, downloadable as event.icsTEMPLATES:- collab\_group\_detail.html (public variant): 5 tabs — Forum | Files | Chatrooms | Events | Members- Files tab: folder tree on left, file list on right, breadcrumb navigation- Chatrooms tab: list of rooms on left, active chat on right (SocketIO room chatroom\_{room\_id})- Events tab: toggle between Calendar view (monthly grid) and List view; each event has RSVP buttons, Google Calendar link, iCal download- collab\_group\_admin.html: member management table (role column with dropdowns), chatroom management, folder managementMODERATION:- Admin can promote member to Moderator: PUT /api/collab/groups/{id}/members/{uid}/role- Admin/Mod can remove members, pin forum posts- POST /api/collab/groups/{id}/posts/{pid}/pin — toggle pin statusNOTIFICATIONS: group\_post (new post in group) and group\_event (new event) → send to all active group members via create\_notification()

**PHASE 5A  DIRECT MESSAGING (3 TYPES)  \[PHASE 5A\]**

Full messaging system: connection DMs, non-connection requests with templates, and mentor/mentee scheduling chat.

## **Phase 5A — PRD**

* Replace collab\_messages.html stub with real messaging hub

* Mode 1: Connection DM — text, files, reactions, read receipts, typing indicator

* Mode 2: Non-connection request — template messages, request inbox, pre-formatted responses

* Mode 3: Mentor/mentee DM — all Mode 1 features \+ session scheduling \+ calendar links

* DM list sorted by last\_message\_at DESC

* Unread count badges on each thread and on nav icon

* SocketIO for all real-time features

## **Phase 5A — Data**

See detailed schemas in Part 5.3. Key Firestore paths:

* /direct\_messages/{dm\_id} — thread metadata

* /direct\_messages/{dm\_id}/messages/{msg\_id} — individual messages

* /message\_requests/{req\_id} — pending non-connection requests

## **Phase 5A — Logic Flow**

* collab\_messages.html: left sidebar \= DM list (connections) \+ message requests badge \+ mentor chats section

* Clicking a thread: GET /api/collab/dms/{dm\_id}/messages?limit=50 → render, join SocketIO room, mark read

* Sending: emit collab\_dm\_send with {dm\_id, content, type} → server persists, emits to dm\_{pair}, updates last\_message

* Read receipt: emit collab\_dm\_read when thread opened → server updates read\_by, decrements unread count, emits collab\_dm\_receipt back

* Typing: emit collab\_typing (no DB write) → received by partner only

* File: POST /api/collab/dms/{dm\_id}/files → upload → returns url → send as type="file" message

***📋 Windsurf / Claude Prompt — Phase 5A — Direct Messaging (3 types)***

Implement the full 3-mode DM system for ScleraCollab. Replace the stub collab\_messages.html.FIRESTORE SCHEMA:- /direct\_messages/{dm\_id}: participants\[\], last\_message, last\_message\_at, last\_sender\_uid, unread\_count\_a, unread\_count\_b, connection\_type ("connection"|"request"|"mentor"), is\_mentor\_chat- /direct\_messages/{dm\_id}/messages/{msg\_id}: sender\_uid, content, type("text"|"file"|"image"), file\_url, file\_name, read\_by\[\], reactions{uid:emoji}, created\_at, deleted- /message\_requests/{req\_id}: from\_uid, to\_uid, template\_type, message, status("pending"|"accepted"|"declined"), created\_atROUTES:- GET /collab/messages — messaging hub- GET /collab/messages/dm/{uid} — open/create DM with specific user- GET /api/collab/dms — list all DM threads sorted by last\_message\_at DESC- GET /api/collab/dms/{dm\_id}/messages?cursor=\&limit=50 — paginated messages- POST /api/collab/dms/{uid}/send — send message to connection- DELETE /api/collab/dms/{dm\_id}/messages/{msg\_id} — delete own message- POST /api/collab/dms/{dm\_id}/messages/{msg\_id}/react — add emoji reaction- GET /api/collab/message-requests — list pending requests- POST /api/collab/message-requests/send — send request to non-connection- POST /api/collab/message-requests/{id}/respond — accept or declineSOCKETIO HANDLERS:- @socketio.on("join\_dm") → join\_room(f"dm\_{dm\_id}"), verify participant- @socketio.on("collab\_dm\_send") → persist message, emit to dm\_{dm\_id} room, update thread last\_message, increment unread count- @socketio.on("collab\_dm\_read") → update read\_by array, set unread\_count to 0 for reader, emit "collab\_dm\_receipt"- @socketio.on("collab\_dm\_react") → update reactions map, emit reaction update to dm\_{dm\_id}- @socketio.on("collab\_typing") → emit "collab\_typing\_indicator" to OTHER participants only (no DB write)TEMPLATES:- collab\_messages.html: split pane layout  LEFT: search threads, DM list (avatar, name, last message preview, timestamp, unread badge), "Message Requests" tab with badge count, "Mentor Chats" section  RIGHT: active chat or empty state  Chat header: avatar, name, headline, online dot (future), video/call (future placeholder icons)  Chat area: message bubbles (own \= right/accent, other \= left/gray), read ticks, emoji reactions on hover  Input area: text field, emoji picker, file attach, send button, typing indicatorMODE 2 — MESSAGE REQUESTS:  \- From non-connection profile → "Message" button → opens request modal  \- Modal: template selector (5 templates), custom message textarea, "Send Request" button  \- Templates: "Requesting a recommendation for \[role\]", "Asking for advice about \[topic\]", "Proposing collaboration on \[project\]", "Job inquiry about \[company\]", "Custom"  \- Request inbox (Network page, Message Requests tab): sender card, message preview (200 chars), Accept/Decline buttons with pre-formatted response templates  \- Accept: creates DM thread, sends notification to senderMODE 3 — MENTOR CHAT:  \- Detected when connection type is "mentor" or "mentee"  \- Chat header shows "Mentor Chat" badge  \- Extra button in input area: calendar icon → "Schedule Session" modal  \- Modal: date picker, time picker, duration selector, session title  \- On submit: store session in DM doc sessions\[\] array, generate Google Calendar URL and iCal, send as "system" message type in chat showing session details with calendar buttons  \- Sessions panel: collapsible panel in chat showing upcoming scheduled sessionsNOTIFICATIONS: wire create\_notification() for dm\_message (new DM), message\_request (new request), message\_request\_accepted

**PHASE 6  POLISH, ACTIVITY LOG & MOBILE  \[FINAL PHASE\]**

Activity log, mobile responsiveness, loading skeletons, and final production polish.

## **Phase 6 — PRD**

* GET /collab/activity — personal activity log (own posts, reactions given, connections made)

* Mobile bottom navigation bar replacing top nav on \<768px screens

* Loading skeleton components for feed, profile sections, DM list

* Lazy-loading for images (loading="lazy" attribute \+ CSS shimmer)

* Lighthouse performance pass: defer non-critical JS, compress images on upload (Pillow)

* Push notifications infrastructure (service worker, web push — optional stretch goal)

* Weekly email digest (Flask-Mail, summarise new connections, trending posts, missed reactions)

***📋 Windsurf / Claude Prompt — Phase 6 — Polish, Activity Log, Mobile***

Final polish phase for ScleraCollab.1. ACTIVITY LOG:   \- GET /collab/activity renders collab\_activity.html   \- GET /api/collab/activity?cursor=\&limit=20 — query /notifications where actor\_uid==uid (things you did), ordered by created\_at DESC   \- Display: "You reacted 💡 to Alex's post", "You connected with Priya", "You posted '...'" — with timestamps and entity links2. MOBILE BOTTOM NAV:   \- In collab\_base.html, add a \<nav class="mobile-bottom-nav"\> containing: Feed, Network, Groups, Messages (with badge), Profile icons   \- Show only on \<768px via CSS media query   \- Hide top nav items on mobile (keep logo and notification bell)   \- Tap targets minimum 48px height3. LOADING SKELETONS:   \- Create CSS skeleton animation (shimmer effect: gradient sweep)   \- Add skeleton versions of: post card, profile card, DM thread row, notification row   \- Show skeletons on initial page load, replace with real content on data arrival4. IMAGE OPTIMIZATION:   \- In /profile/photo route, add Pillow resizing: max 400×400px, JPEG quality 85, save as .jpg   \- Add loading="lazy" to all \<img\> tags in feed templates5. PERFORMANCE:   \- Add defer attribute to non-critical \<script\> tags in collab\_base.html   \- Add \<link rel="preconnect"\> for Google Fonts in base template6. WEEKLY EMAIL DIGEST (Flask-Mail):   \- Background task (APScheduler or cron) that runs Monday 9am   \- For each user with notifications in past 7 days: compile digest (new connections, post reactions received, trending hashtags)   \- Send HTML email via Flask-Mail   \- GET /api/collab/digest/unsubscribe?token={} — unsubscribe link in email

# **PART 8 — COMPLETE DATA ARCHITECTURE REFERENCE**

## **8.1  collab\_users/{uid} — Full Schema**

uid: string

name: string

email: string

headline: string                    \# 250 char max

bio: string

profile\_picture: string | null      \# filename in /static/media/

profile\_banner: string | null

location: string

website: string

github: string

linkedin: string

education: \[{institution, degree, field, grade, gpa, from\_date, to\_date, current}\]

experience: \[{title, company, type, from\_date, to\_date, description, current}\]

volunteer: \[{organization, role, cause, from\_date, to\_date}\]

projects: \[{id, title, description, link, github, tech\_stack\[\], media\[\]}\]

publications: \[{title, journal, link, date}\]

patents: \[{title, number, date}\]

awards: \[{title, issuer, date}\]

languages: \[{language, proficiency}\]

certifications: \[{name, issuer, date, link}\]

skills: \[{name, endorsement\_count}\]

follower\_count: int

following\_count: int

connection\_count: int

post\_count: int

recommendations\_received: \[\]

profile\_completion: int (0-100)

setup\_complete: bool

privacy: {section: "public"|"connections"|"only\_me"}

mentorship\_available: bool

mentorship\_focus\_areas: string\[\]

mentorship\_preferences: {time\_commitment, communication\_style, max\_mentees}

mentorship\_stats: {total\_mentees, active\_mentees, completed, avg\_rating}

created\_at: ISO timestamp

updated\_at: ISO timestamp

## **8.2  posts/{post\_id} — Full Schema**

post\_id: string (auto)

author\_uid: string

type: "post" | "article" | "share"

content: string (sanitized HTML)

images: string\[\]

links: string\[\]

hashtags: string\[\]

visibility: "public" | "connections" | "group"

group\_id: string | null

original\_post\_id: string | null     \# if share type

quote\_content: string | null

reaction\_counts: {insightful:0, motivating:0, support:0}

comment\_count: int

share\_count: int

view\_count: int

save\_count: int

\_analysis: {topics, keywords, education\_level}  \# NLP cache

created\_at: ISO timestamp

updated\_at: ISO timestamp

deleted: bool

## **8.3  connections/{conn\_id} — Schema**

conn\_id: "{min\_uid}\_{max\_uid}"

user\_a: string               \# sender

user\_b: string               \# recipient

participants: \[uid\_a, uid\_b\] \# for array\_contains queries

status: "pending" | "accepted" | "declined"

type: "peer" | "mentor" | "mentee"

message: string

created\_at, updated\_at: ISO timestamps

## **8.4  All Planned Collections Summary**

| Collection Path | Description |
| :---- | :---- |
| /collab\_users/{uid} | User profiles |
| /collab\_users/{uid}/recommendations/{id} | Written recommendations |
| /collab\_users/{uid}/endorsements/{skill} | Skill endorsers |
| /collab\_users/{uid}/saved\_posts/{post\_id} | Bookmarked posts |
| /connections/{conn\_id} | Symmetric connections |
| /follows/{id} | Asymmetric follows |
| /posts/{post\_id} | Feed posts |
| /posts/{post\_id}/reactions/{uid} | Per-user reactions |
| /posts/{post\_id}/comments/{id} | Comments with threading |
| /articles/{article\_id} | Long-form articles |
| /hashtags/{tag} | Hashtag metadata |
| /groups/{group\_id} | Private and public groups |
| /groups/{group\_id}/members/{uid} | Group membership |
| /groups/{group\_id}/posts/{id} | Group forum posts |
| /groups/{group\_id}/files/{id} | Private group files |
| /groups/{group\_id}/goals/{id} | Private group goals |
| /groups/{group\_id}/folders/{id} | Public group folders |
| /groups/{group\_id}/chatrooms/{id} | Public group chatrooms |
| /groups/{group\_id}/events/{id} | Group events |
| /direct\_messages/{dm\_id} | DM thread metadata |
| /direct\_messages/{dm\_id}/messages/{id} | DM messages |
| /message\_requests/{id} | Non-connection message requests |
| /notifications/{id} | All notification types |

# **PART 9 — SECURITY CHECKLIST**

## **9.1  Current Issues (Must Fix)**

* 🔴 Debug routes (/debug/\*) active in production — mutate Firestore data — GATE WITH FLASK\_ENV CHECK

* 🔴 SocketIO cors\_allowed\_origins="\*" — allows any origin — CHANGE TO DOMAIN LIST

* 🔴 SECRET\_KEY fallback to hardcoded string — sessions forgeable — RAISE ERROR IF MISSING

* 🔴 No rate limiting — any authenticated user can spam posts/reactions/requests

* 🟡 No CSRF protection on write endpoints

* 🟡 post.content|safe in templates — bleach upstream but fragile pattern

* 🟡 Duplicate /api/collab/feed route — silent dead code

## **9.2  Planned Security Additions**

* Flask-Limiter: per-user per-minute limits on all write endpoints

* Flask-Talisman: CSP headers, HSTS, X-Frame-Options

* CSRF: custom X-CSRF-Token header check on state-changing AJAX calls

* Image validation: magic bytes check (not just extension) on upload

* Content-Disposition: attachment header on file downloads

* Firebase Storage rules: restrict read/write to authenticated users only

# **PART 10 — APPENDIX: UI DESIGN SYSTEM**

## **10.1  Design Tokens**

| Token | Value |
| :---- | :---- |
| \--bg-primary (dark) | \#0d0d0d |
| \--bg-island (dark) | \#161616 / \#1a1a1a |
| \--border (dark) | rgba(255,255,255,0.07) |
| \--text (dark) | \#f5f5f5 |
| \--text-muted (dark) | \#71717a |
| \--accent | \#22c55e (green) |
| \--accent-dim | rgba(34,197,94,0.12) |
| \--blue | \#3b82f6 |
| \--red | \#ef4444 |
| \--bg-primary (light) | \#f0f0ef |
| \--bg-island (light) | rgba(255,255,255,0.95) |
| Font | Sora (Google Fonts), fallback sans-serif |
| Border radius (island) | 1rem / 1.5rem |
| Shadow (island) | 0 4px 24px rgba(0,0,0,0.3) |

## **10.2  Component Patterns**

**Island Pattern:**

Every UI section is an "island" — a self-contained card with bg-island background, border, and rounded corners. Classname: .island. Padding variant: .island-pad.

**Button Variants:**

* .btn.btn-primary — accent green background, black text, pill border-radius

* .btn.btn-ghost — transparent background, muted text, hover darkens

* .btn.btn-sm — reduced padding, 0.8rem font size

**Avatar:**

* .avatar-init — circular div with gradient bg, initials as text, white colour

* .avatar — circular img with object-cover

**Chip/Tag:**

* .chip.chip-n — pill-shaped tag, accent-dim background, green text

## **10.3  Navigation Structure**

* Desktop top nav: Feed | Network | Groups | Messages \[badge\] | Notifications \[badge\] | Profile

* Mobile bottom nav (Phase 6): Feed | Network | Groups | Messages \[badge\] | Profile

* Active nav item: accent colour, slight background highlight

*ScleraCollab Master Technical Document  |  v3.0  |  Living Document*

This document should be updated after each phase completion.