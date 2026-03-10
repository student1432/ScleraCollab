# ScleraCollab — Product Requirements Document
### LinkedIn for Students · Built on the Sclera Platform

---

## Table of Contents
1. [Product Overview](#1-product-overview)
2. [Design Philosophy](#2-design-philosophy)
3. [Feature Specification (PRD)](#3-feature-specification)
4. [User Flow](#4-user-flow)
5. [Logic Flow](#5-logic-flow)
6. [Tech Stack](#6-tech-stack)
7. [Data Models](#7-data-models)
8. [API Contract](#8-api-contract)
9. [Implementation Plan — Phased](#9-implementation-plan)

---

## 1. Product Overview

### What is ScleraCollab?

ScleraCollab is the **community and professional networking slice** of the Sclera platform. It is a standalone Flask app extracted from the monolithic `app.py` and elevated into a full "LinkedIn for students" — complete with professional profiles, a content feed, direct messaging, groups, mentorship, and career-aware networking.

### Who is it for?

| Persona | Need |
|---|---|
| High-school student | Build early professional presence, find peers studying the same exams |
| College-bound student | Showcase projects, get recommendations from teachers |
| Student job/intern seeker | Surface work experience, discover opportunities from ScleraCareer |
| Teacher / Mentor | Write recommendations, moderate groups, broadcast to class |

### Goals
- Replace the thin "community" page in app.py with a rich, standalone social platform.
- Become the canonical social graph layer shared between Sclera Academic, ScleraCollab, and ScleraCareer.
- Feel fast, polished, and distinctly student-focused — not a generic clone.

---

## 2. Design Philosophy

All UI must match the screenshot provided and the existing Sclera design language exactly.

### Core Principles

| Principle | Implementation |
|---|---|
| **Island Layout** | Every content block lives in a rounded, glassy card ("island"). No full-bleed sections. |
| **Dark / Light Duality** | CSS variable system (`--bg`, `--surface`, `--text-primary`, etc.) toggled via a single class on `<body>`. |
| **Glassmorphism** | `backdrop-filter: blur(20px)` + semi-transparent backgrounds on cards and modals. |
| **Mobile-first** | Tailwind-style breakpoints. Sidebar collapses to bottom nav on mobile. |
| **Minimal Chrome** | Navigation stays in the single top bar used across all Sclera slices. |

### Color Tokens (Dark Mode)
```css
--bg:           #0a0a0a
--surface:      rgba(255,255,255,0.05)
--surface-hover:rgba(255,255,255,0.08)
--border:       rgba(255,255,255,0.08)
--text-primary: #ffffff
--text-muted:   rgba(255,255,255,0.5)
--accent:       #22c55e   /* green — matches Sclera brand */
--accent-soft:  rgba(34,197,94,0.15)
--danger:       #ef4444
```

### Light Mode overrides
```css
body.light {
  --bg:          #f4f4f5
  --surface:     rgba(255,255,255,0.8)
  --border:      rgba(0,0,0,0.08)
  --text-primary:#09090b
  --text-muted:  #71717a
}
```

---

## 3. Feature Specification

### 3.1 Professional Profile

#### Fields added on top of existing Sclera user doc

| Section | Fields |
|---|---|
| Work Experience | company, role, start/end date, description, employment_type |
| Education | institution, degree, field, start/end year, gpa, achievements |
| Volunteer Work | org, role, cause, dates, description |
| Projects | title, description, url, github_url, media_urls[], tech_stack[] |
| Publications | title, publisher, date, url |
| Languages | language, proficiency (basic/conversational/fluent/native) |
| Awards & Honors | title, issuer, date, description |
| Skills (enhanced) | skill_name, endorsement_count, endorsed_by[] |
| Recommendations | author_uid, author_name, relationship, body, date, approved |
| Certifications | name, issuer, date, credential_url |

#### Profile Completion Meter
A score (0–100) computed from field completeness, shown as a progress arc on the profile page. Milestones unlock a "badge" (Starter → Rising → Pro → All-Star).

#### Privacy Granularity
Each section has a `visibility` enum: `public | connections | only_me`.

---

### 3.2 Networking & Connections

| Feature | Detail |
|---|---|
| Follow (one-way) | Follow institutions, companies, or public profiles without mutual approval. |
| Connect (two-way) | Existing mutual connection model from app.py, preserved and enhanced. |
| Alumni Network | Auto-surface users with matching `school.institution` or `education[].institution`. |
| Mentorship | Separate connection type. Mentors set a `mentorship_available` flag and up to 3 focus areas. Students send a `mentorship_request` with a 200-char note. |
| Suggestions | Computed server-side: shared school > shared exam > shared career interests > mutual connections. |
| Connection Card | Quick-action: Connect / Follow / Message / View Profile. |

---

### 3.3 Content & Feed

| Feature | Detail |
|---|---|
| Post types | Text (max 3000 chars), Article (rich text, titled), Resource (file/link share) |
| Media | Images (max 4), single video (upload or YouTube embed) |
| Engagement | Reactions (👍 Insightful / 🎯 Helpful / 🔥 Great), Comments (threaded 2-level), Shares |
| Feed types | Home (algorithmic), Following (chronological), Trending (hashtag-based) |
| Hashtags | `#tag` auto-linked in posts; hashtag follow for discovery |
| Save / Bookmark | Users save posts to private collection |
| Visibility | Post can be Public / Connections-only / Group-only |

---

### 3.4 Groups (evolved Bubbles)

| Feature | Detail |
|---|---|
| Types | Private (invite only) / Public (anyone can join) |
| Roles | Owner > Moderator > Member |
| Features | Pinned posts, announcements, group rules, events within group |
| Carry-over from Bubbles | Group chat (SocketIO rooms), shared todos, file sharing |
| Public groups | Browsable catalog with search by topic/interest |

---

### 3.5 Messaging

| Feature | Detail |
|---|---|
| Direct Messages (DM) | One-to-one text, emoji, file attachment |
| Group Chat | Ad-hoc multi-user chat (not tied to a Group/Bubble) |
| Message states | Sent → Delivered → Read (double-tick pattern) |
| Reactions | React to individual messages with emoji |
| File sharing | Images, PDFs, docs (max 20MB per file, same validation as bubble files) |
| Typing indicator | Real-time via SocketIO |
| Notifications | Badge count on nav icon; push via browser Notification API |

---

### 3.6 Notifications & Activity

| Type | Trigger |
|---|---|
| Connection request | Someone sends a connect |
| Post reaction | Someone reacts to your post |
| Post comment | Comment on your post |
| Mention | @mention in post or comment |
| Endorsement | Someone endorses your skill |
| Recommendation request | Someone requests a recommendation |
| Mentorship request | Mentor request received |
| Group invite | Invited to a private group |
| Event reminder | 24h / 1h before event you RSVP'd |
| New follower | Someone follows your profile |

All notifications stored in `notifications` collection, with `read` boolean. Polled every 30s or pushed via SocketIO channel.

---

## 4. User Flow

### 4.1 Onboarding (New User from Sclera)

```
Landing / Login (shared auth)
  │
  ├─ [First visit to /collab] → Profile Setup Wizard
  │     Step 1: Import from Sclera (education, skills auto-filled)
  │     Step 2: Add headline & profile photo
  │     Step 3: Add first work experience or project (optional, skippable)
  │     Step 4: Connection suggestions (based on same school)
  │     Step 5: Follow 3 groups to get started
  │
  └─ [Returning user] → Feed (/collab/feed)
```

### 4.2 Profile Flow

```
My Profile (/collab/profile/<uid>)
  ├── Edit Profile → Modal overlays per section (inline edit)
  ├── Skills → Endorsement panel (connections only)
  ├── Recommendations
  │     ├── Request from connection → sends notification
  │     └── Write for someone → their approval required before publish
  ├── Projects → Add/edit with media upload
  └── Share Profile → copy public URL / toggle visibility
```

### 4.3 Feed & Post Flow

```
Feed (/collab/feed)
  ├── Post Composer (top of feed)
  │     ├── Text post
  │     ├── + Image (drag & drop)
  │     ├── + Hashtags (suggested as you type)
  │     └── Audience picker (Public / Connections / Group)
  │
  ├── Post Card
  │     ├── React → increment reaction count (optimistic UI)
  │     ├── Comment → inline thread expands
  │     │     └── Reply to comment (1 level nesting)
  │     ├── Share → repost to own feed or to a Group
  │     └── Save → added to bookmarks
  │
  └── Sidebar (desktop)
        ├── Profile completion island
        ├── Suggested connections (3 cards)
        └── Trending hashtags
```

### 4.4 Messaging Flow

```
Messages (/collab/messages)
  ├── Conversation List (left panel)
  │     ├── DMs sorted by last message time
  │     └── New Message button → search for connection
  │
  └── Chat Window (right panel)
        ├── Message history (paginated, scroll-up to load more)
        ├── Typing indicator
        ├── File attach button
        └── Emoji picker
```

### 4.5 Groups Flow

```
Groups (/collab/groups)
  ├── My Groups tab
  ├── Discover tab (public groups catalog)
  │
  └── Group Page (/collab/groups/<group_id>)
        ├── Feed (posts within group)
        ├── Chat (SocketIO room)
        ├── Members list
        ├── Files
        ├── Todos
        └── Events
```

---

## 5. Logic Flow

### 5.1 Feed Algorithm (Server-side)

```
generate_feed(uid):
  1. get_connection_uids(uid)           → list of ~500 connected UIDs
  2. get_following_uids(uid)            → one-way follows
  3. get_joined_group_ids(uid)          → group feed posts
  4. recent_posts = firestore query:
       posts WHERE author_uid IN [connections + following]
         OR group_id IN joined_groups
         AND deleted == False
         ORDER BY created_at DESC
         LIMIT 100
  5. score_posts(posts, uid):
       score = recency_score(created_at)       × 0.5
             + engagement_score(reactions+comments) × 0.3
             + relevance_score(hashtags ∩ user_interests) × 0.2
  6. return top 30 scored posts
```

### 5.2 Skill Endorsement Logic

```
endorse_skill(endorser_uid, target_uid, skill_name):
  1. Check endorser is connected to target (403 if not)
  2. Check endorser hasn't already endorsed this skill (idempotent)
  3. db.users.target_uid.skills[skill_name].endorsed_by.append(endorser_uid)
  4. db.users.target_uid.skills[skill_name].endorsement_count += 1
  5. create notification(target_uid, type='endorsement', from=endorser_uid)
```

### 5.3 Recommendation Flow

```
request_recommendation(requester_uid, author_uid, context):
  1. Create rec_request doc: {status: 'pending', requester, author, context}
  2. Notify author
  author writes recommendation → {body, relationship, approved: False}
  3. Notify requester for approval
  requester approves → approved: True → visible on profile
  requester rejects → doc stays, not visible
```

### 5.4 Mentorship Match Logic

```
get_mentor_suggestions(uid):
  user = get_user_data(uid)
  career_interests = user.interests.careers
  1. query mentors WHERE mentorship_available == True
       AND focus_areas ARRAY_CONTAINS_ANY career_interests
  2. boost mentors from same school (alumni bonus)
  3. boost mentors with > 3 endorsements
  4. return top 5
```

### 5.5 Real-time Messaging (SocketIO)

```
Client: connect → join_user_room(uid)

send_dm(sender_uid, receiver_uid, content):
  1. Rate-limit check (20 msgs/min)
  2. Validate content (same message_validator as bubbles)
  3. db.direct_messages.add({sender, receiver, content, timestamp, read: False})
  4. socketio.emit('new_dm', payload, room=f'user_{receiver_uid}')
  5. If receiver offline → increment badge_count in db.users.receiver_uid.unread_dms

mark_dm_read(viewer_uid, conversation_id):
  1. batch update all unread msgs in conversation WHERE receiver == viewer → read: True
  2. socketio.emit('dms_read', {conversation_id}, room=f'user_{sender_uid}')
```

### 5.6 Notification Dispatch

```
create_notification(recipient_uid, type, payload):
  1. db.notifications.add({recipient_uid, type, payload, read: False, created_at})
  2. socketio.emit('notification', {type, payload}, room=f'user_{recipient_uid}')
  3. increment db.users.recipient_uid.unread_notifications_count
```

---

## 6. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| **Backend** | Flask 2.x | Same as app.py; extracted into `collab.py` Blueprint |
| **Realtime** | Flask-SocketIO (threading mode) | Existing socketio instance shared or new instance |
| **Database** | Firebase Firestore | Same project; new collections prefixed with no change |
| **Auth** | Firebase Admin Auth + Flask session | Shared session; same `require_login` decorator |
| **File Storage** | Local `uploads/` + `serve_upload` route | Same pattern as bubble file sharing |
| **Rate Limiting** | Flask-Limiter (memory://) | Shared limiter instance |
| **Security** | Flask-Talisman CSP | Shared Talisman config |
| **Frontend** | Jinja2 templates + Vanilla JS | Same as existing; no React needed |
| **Styling** | Tailwind CDN + custom CSS variables | Island glassmorphism system |
| **Icons** | Lucide Icons (CDN) | Consistent with existing UI |
| **Rich Text** | Tiptap (CDN) or Quill | For article editor |
| **Image Processing** | Pillow | Already installed; used for banner/pfp |

### File / Module Structure

```
sclera_collab/
├── collab.py              ← Flask Blueprint (all routes)
├── collab_socketio.py     ← SocketIO event handlers
├── collab_feed.py         ← Feed generation algorithm
├── collab_notifications.py← Notification dispatch helpers
├── templates/
│   ├── collab_base.html       ← extends sclera base; adds collab nav
│   ├── collab_feed.html
│   ├── collab_profile.html
│   ├── collab_profile_edit.html
│   ├── collab_messages.html
│   ├── collab_groups.html
│   ├── collab_group_detail.html
│   ├── collab_discover.html
│   └── collab_notifications.html
└── static/
    └── collab.css             ← island / glassmorphism tokens
```

---

## 7. Data Models

### 7.1 Enhanced User (delta fields added to existing `users` collection)

```json
{
  "headline": "CBSE Class 12 · Aspiring Software Engineer",
  "location": "Mumbai, India",
  "website": "https://mysite.com",
  "work_experience": [
    {
      "id": "uuid",
      "company": "Google",
      "role": "SWE Intern",
      "employment_type": "Internship",
      "start": "2024-06",
      "end": null,
      "current": true,
      "description": "...",
      "visibility": "public"
    }
  ],
  "education": [...],
  "projects": [...],
  "languages": [...],
  "awards": [...],
  "certifications": [...],
  "recommendations_received": ["rec_id_1"],
  "mentorship_available": false,
  "mentorship_focus_areas": [],
  "following": ["uid1", "uid2"],
  "followers": ["uid3"],
  "profile_completion_score": 72,
  "unread_notifications_count": 3,
  "unread_dms_count": 1
}
```

### 7.2 Post

```
Collection: posts
Document ID: auto
{
  post_id, author_uid, author_name, author_headline,
  type: "post" | "article" | "resource",
  title (articles only),
  content (text/HTML),
  media_urls: [],
  hashtags: ["#AI", "#Internship"],
  visibility: "public" | "connections" | "group",
  group_id (if group post),
  reactions: { insightful: 5, helpful: 2, great: 1 },
  reaction_by: { "uid": "insightful" },
  comment_count, share_count, save_count,
  created_at, updated_at, deleted: false
}
```

### 7.3 Comment

```
Collection: posts/{post_id}/comments
{
  comment_id, author_uid, author_name,
  content, parent_comment_id (null = top-level),
  reactions: {},
  created_at, deleted: false
}
```

### 7.4 Direct Message

```
Collection: conversations/{conversation_id}/messages
Conversation doc:
{
  conversation_id, participant_uids: [uid1, uid2],
  last_message, last_message_at, created_at
}
Message doc:
{
  message_id, sender_uid, content,
  media_url (optional), message_type: "text"|"file",
  read: false, created_at, reactions: {}
}
```

### 7.5 Notification

```
Collection: notifications
{
  notification_id, recipient_uid,
  type: "connection_request"|"reaction"|"comment"|"mention"|
        "endorsement"|"recommendation_request"|"mentorship_request"|
        "group_invite"|"new_follower",
  payload: { actor_uid, actor_name, post_id?, group_id?, ... },
  read: false,
  created_at
}
```

### 7.6 Group (enhanced Bubble)

```
Collection: groups
{
  group_id, name, description, avatar_url, cover_url,
  type: "private" | "public",
  creator_uid, moderator_uids: [],
  member_uids: [], member_count,
  rules: ["Be respectful", ...],
  pinned_post_ids: [],
  topics: ["#MachineLearning"],
  invite_code (private groups only),
  created_at
}
```

### 7.7 Skill Endorsement (embedded in user doc)

```json
"skills_enhanced": [
  {
    "name": "Python",
    "endorsed_by": ["uid1", "uid2"],
    "endorsement_count": 2
  }
]
```

### 7.8 Recommendation

```
Collection: recommendations
{
  rec_id, requester_uid, author_uid, author_name,
  relationship: "Teacher" | "Peer" | "Mentor" | "Manager",
  body, approved: false,
  created_at, approved_at
}
```

---

## 8. API Contract

### Profile APIs
```
GET  /api/collab/profile/<uid>                 → public profile
PUT  /api/collab/profile                       → update own profile
POST /api/collab/profile/experience            → add work experience
PUT  /api/collab/profile/experience/<id>       → edit
DELETE /api/collab/profile/experience/<id>     → delete
POST /api/collab/profile/project               → add project
PUT  /api/collab/profile/skills/endorse        → endorse a skill {target_uid, skill}
GET  /api/collab/profile/<uid>/completion      → profile score
```

### Feed & Posts
```
GET  /api/collab/feed                          → paginated feed (cursor-based)
POST /api/collab/posts                         → create post
GET  /api/collab/posts/<post_id>               → single post
DELETE /api/collab/posts/<post_id>             → soft delete
POST /api/collab/posts/<post_id>/react         → {reaction_type}
DELETE /api/collab/posts/<post_id>/react       → remove reaction
POST /api/collab/posts/<post_id>/comments      → add comment
GET  /api/collab/posts/<post_id>/comments      → get comments
POST /api/collab/posts/<post_id>/save          → bookmark
GET  /api/collab/bookmarks                     → user's saved posts
```

### Networking
```
POST /api/collab/follow/<uid>                  → follow user/institution
DELETE /api/collab/follow/<uid>                → unfollow
POST /api/collab/connections/send              → (existing, migrated)
POST /api/collab/mentorship/request            → {target_uid, note}
POST /api/collab/mentorship/respond            → {request_id, action: accept|decline}
GET  /api/collab/suggestions/connections       → 10 suggested users
GET  /api/collab/suggestions/mentors           → 5 suggested mentors
GET  /api/collab/alumni                        → alumni from same school
```

### Messaging
```
GET  /api/collab/conversations                 → list conversations
POST /api/collab/conversations                 → create DM {target_uid}
GET  /api/collab/conversations/<id>/messages   → paginated messages
POST /api/collab/conversations/<id>/messages   → send message
POST /api/collab/conversations/<id>/read       → mark as read
```

### Groups
```
GET  /api/collab/groups                        → user's groups
GET  /api/collab/groups/discover               → public groups catalog
POST /api/collab/groups                        → create group
GET  /api/collab/groups/<id>                   → group detail
POST /api/collab/groups/<id>/join              → join public group
POST /api/collab/groups/<id>/leave             → leave
POST /api/collab/groups/<id>/posts             → post to group
GET  /api/collab/groups/<id>/posts             → group feed
```

### Notifications
```
GET  /api/collab/notifications                 → paginated list
POST /api/collab/notifications/<id>/read       → mark read
POST /api/collab/notifications/read_all        → mark all read
```

### Recommendations
```
POST /api/collab/recommendations/request       → {author_uid, context}
POST /api/collab/recommendations/write         → {requester_uid, body, relationship}
POST /api/collab/recommendations/<id>/approve  → requester approves
DELETE /api/collab/recommendations/<id>        → reject/delete
```

### SocketIO Events

```
Client → Server:
  join_user_room          {uid}
  join_group_chat         {group_id}
  leave_group_chat        {group_id}
  send_dm                 {conversation_id, content, media_url?}
  dm_read                 {conversation_id}
  typing_start_dm         {conversation_id}
  typing_stop_dm          {conversation_id}
  send_group_message      {group_id, content}
  typing_start_group      {group_id}
  typing_stop_group       {group_id}

Server → Client:
  new_dm                  {message, conversation_id}
  dm_read_receipt         {conversation_id, reader_uid}
  dm_typing               {conversation_id, uid, action}
  new_group_message       {group_id, message}
  group_typing            {group_id, uid, action}
  new_notification        {notification}
  notification_count      {count}
```

---

## 9. Implementation Plan

The project is split into **6 phases**, each independently buildable and testable. Each phase produces a working slice of ScleraCollab.

---

### PHASE 1 — Foundation & Enhanced Profile
**Goal:** Standalone Flask Blueprint, auth shared with Sclera, enhanced profile page working.

**Deliverables:**
- `collab.py` Blueprint registered in main `app.py` under `/collab` prefix
- `collab_base.html` template extending Sclera's nav
- Profile page (`/collab/profile/<uid>`) with all new sections
- Profile edit with inline section modals
- Work experience, education, projects, languages CRUD
- Profile completion score calculation
- Skills endorsement (UI + logic)
- Public/private toggle per section
- `collab.css` with island tokens matching screenshot

**New Firestore collections:** none (delta fields on existing `users` doc)

**Estimated prompt size:** Large (profile template + CSS + routes)

**Split suggestion:**
- Prompt 1A: `collab.py` Blueprint scaffold + CSS + base template
- Prompt 1B: Profile page template (all sections)
- Prompt 1C: Profile edit modals + completion score

---

### PHASE 2 — Feed & Content
**Goal:** Working social feed with post creation, reactions, comments.

**Deliverables:**
- Feed page (`/collab/feed`) with algorithmic score
- Post composer (text, image upload, hashtag suggestions)
- Post card component (reactions, comment toggle, share, save)
- Comment thread (2-level, nested)
- Bookmarks page
- Hashtag pages (`/collab/hashtag/<tag>`)
- `collab_feed.py` feed scoring module

**New Firestore collections:** `posts`, `posts/{id}/comments`, `bookmarks`

**Estimated prompt size:** Large

**Split suggestion:**
- Prompt 2A: `collab_feed.py` + POST creation API + feed route
- Prompt 2B: Feed template + post card component (reactions, comments)
- Prompt 2C: Image upload, hashtag suggestions, bookmarks

---

### PHASE 3 — Networking (Connections + Follow + Mentorship)
**Goal:** Full social graph: connections (existing migrated), follows, alumni, mentorship.

**Deliverables:**
- Migrate existing connection logic from `app.py` to `collab.py`
- Follow/unfollow (one-way)
- Connection suggestions widget
- Alumni network page (`/collab/alumni`)
- Mentorship request + accept/decline flow
- Mentor discovery page (`/collab/mentors`)
- Recommendation request + write + approve flow

**New Firestore collections:** `follows`, `mentorship_requests`, `recommendations`

**Estimated prompt size:** Medium

**Split suggestion:**
- Prompt 3A: Follow system + connection migration + suggestions
- Prompt 3B: Mentorship flow (request, accept, mentor profile badge)
- Prompt 3C: Recommendations (request, write, approve, display on profile)

---

### PHASE 4 — Groups (Enhanced Bubbles)
**Goal:** Upgrade existing Bubble system to full Groups with public catalog, roles, pinned posts, events.

**Deliverables:**
- Groups page with My Groups + Discover tabs
- Public group catalog (searchable/filterable)
- Group roles (owner/moderator/member)
- Group feed (posts within group)
- Pinned posts + announcements
- Group events (create, RSVP)
- Carry-over: group chat, file sharing, todos (migrated from bubbles)
- Group rules + moderation (delete member post, remove member)

**New Firestore collections:** Migrate `bubbles` → `groups`; add `group_events`

**Estimated prompt size:** Large

**Split suggestion:**
- Prompt 4A: Group model migration + discover page + group detail shell
- Prompt 4B: Group feed (posts, reactions, comments within group)
- Prompt 4C: Events system + roles + moderation

---

### PHASE 5 — Direct Messaging
**Goal:** Full private DM system with real-time via SocketIO.

**Deliverables:**
- Messages page (`/collab/messages`) — split-pane layout
- Conversation list with unread badges
- Chat window with scroll-up pagination
- Typing indicators (SocketIO)
- File/image attachments in DMs
- Message reactions (emoji)
- Read receipts (double-tick)
- New conversation flow (search connections)
- Unread DM badge in top nav

**New Firestore collections:** `conversations`, `conversations/{id}/messages`

**Estimated prompt size:** Large

**Split suggestion:**
- Prompt 5A: `collab_socketio.py` DM events + conversation API routes
- Prompt 5B: Messages page template (split pane, conversation list)
- Prompt 5C: Chat window (pagination, file attach, reactions, receipts)

---

### PHASE 6 — Notifications, Polish & Integration
**Goal:** Full notification system, activity log, final UI polish, cross-slice integrations.

**Deliverables:**
- Notification center page (`/collab/notifications`)
- Real-time notification badge in nav (SocketIO)
- `collab_notifications.py` dispatch helper
- Activity feed on profile (recent endorsements, new connections)
- Cross-slice: profile completion hints linking to ScleraCareer internships
- Cross-slice: group posts can reference Sclera academic chapters
- PWA manifest + service worker for push notifications (optional stretch)
- Final mobile responsiveness pass
- Onboarding wizard for first-time collab users

**New Firestore collections:** `notifications` (migrate from existing institution notifications)

**Estimated prompt size:** Medium

**Split suggestion:**
- Prompt 6A: `collab_notifications.py` + notification routes + badge system
- Prompt 6B: Notification center page template
- Prompt 6C: Onboarding wizard + cross-slice integration + mobile polish

---

## Phase Summary Table

| Phase | Feature | Prompts | Priority |
|---|---|---|---|
| 1 | Enhanced Profile + CSS Foundation | 3 | 🔴 Critical |
| 2 | Feed & Posts | 3 | 🔴 Critical |
| 3 | Networking (Follow, Mentorship, Recommendations) | 3 | 🟠 High |
| 4 | Groups (Enhanced Bubbles) | 3 | 🟠 High |
| 5 | Direct Messaging | 3 | 🟡 Medium |
| 6 | Notifications + Polish | 3 | 🟡 Medium |
| **Total** | | **~18 prompts** | |

---

## Appendix A — Shared Infrastructure (Reuse from app.py)

The following are **copied unchanged** from `app.py` into the new `collab.py` app:

- `require_login` decorator
- `get_user_data(uid)` helper
- `PasswordManager` (auth)
- `login_rate_limiter`
- `bubble_rate_limiter` (rename to `collab_rate_limiter`)
- `message_validator`
- `file_upload_security`
- Firebase `db`, `auth`, `admin_auth` imports
- `socketio` instance (shared or new)
- `_get_account_type()` and `_get_any_profile(uid)`

---

## Appendix B — Migration Notes (Bubbles → Groups)

When ScleraCollab is deployed alongside the existing Sclera app:

1. Existing `bubbles` collection docs are readable by both apps.
2. A one-time migration script will copy `bubbles` → `groups` with a `migrated: true` flag.
3. Old bubble URLs (`/bubble/<id>`) redirect → `/collab/groups/<id>`.
4. User `bubbles` array field is read alongside new `groups` array field during transition.

---

## Appendix C — How to Start Each Prompt

Use this prefix when starting each implementation prompt:

```
"Implement ScleraCollab Phase X, Prompt Y:
[description].

Constraints:
- Flask Blueprint registered at /collab prefix
- Use same Firestore db instance from firebase_config import
- Use same session/auth pattern as app.py (require_login decorator)
- Templates extend collab_base.html
- Island glassmorphism CSS as defined in PRD Section 2
- Mobile-first, dark/light mode via CSS variables
- Match the UI from the Sclera dashboard screenshot"
```
