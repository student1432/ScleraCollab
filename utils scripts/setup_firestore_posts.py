"""
setup_firestore_posts.py
========================
ScleraCollab — Firestore Setup Script for the Posts System

Covers every collection touched by Phase 2 (connections/follows),
Phase 3 (posts, comments, reactions), and the supporting indexes.

What this script does
---------------------
1.  Validates Firebase connection
2.  Seeds skeleton documents in every collection so Firestore
    registers the collections and their field types
3.  Prints a full checklist of every composite index that must exist
    and instructions to deploy them
4.  Optionally prints the firestore.indexes.json snippet for each
    index so you can paste / diff against your existing file

Usage
-----
    python setup_firestore_posts.py                  # seed + check
    python setup_firestore_posts.py --dry-run        # only print, don't write
    python setup_firestore_posts.py --seed-only      # only write docs, skip index report
    python setup_firestore_posts.py --index-only     # only print index report, skip seeding
    python setup_firestore_posts.py --cleanup        # delete the seeded test documents

Requirements
------------
    pip install firebase-admin python-dotenv
    Set FIREBASE_SERVICE_ACCOUNT_PATH or FIREBASE_SERVICE_ACCOUNT_JSON in your .env
"""

import sys
import json
import uuid
import argparse
from datetime import datetime, timedelta

# ── Bootstrap ──────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # optional

try:
    from firebase_config import db
except ImportError:
    print("✕  Could not import firebase_config.  "
          "Make sure firebase_config.py is in the same directory.")
    sys.exit(1)

try:
    from firebase_admin import firestore as fs
except ImportError:
    print("✕  firebase-admin is not installed.  Run: pip install firebase-admin")
    sys.exit(1)


# ── Constants ──────────────────────────────────────────────────────────────────
SEED_MARKER   = "__setup_seed__"   # tag added to every seeded doc for easy cleanup
NOW           = datetime.utcnow().isoformat()
WEEK_AGO      = (datetime.utcnow() - timedelta(days=7)).isoformat()

TEST_UID_A    = f"_seed_user_a_{uuid.uuid4().hex[:8]}"
TEST_UID_B    = f"_seed_user_b_{uuid.uuid4().hex[:8]}"
TEST_POST_ID  = f"_seed_post_{uuid.uuid4().hex[:8]}"
TEST_COMMENT_ID = f"_seed_comment_{uuid.uuid4().hex[:8]}"
TEST_CONN_ID  = f"{min(TEST_UID_A, TEST_UID_B)}_{max(TEST_UID_A, TEST_UID_B)}"
TEST_FOLLOW_ID = f"_seed_follow_{uuid.uuid4().hex[:8]}"

SEEDED_REFS   = []   # collect all refs written so --cleanup can remove them


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — COLLECTION SCHEMAS + SEEDING
# ══════════════════════════════════════════════════════════════════════════════

COLLECTIONS = {

    # ── /posts ────────────────────────────────────────────────────────────────
    "posts": {
        "description": "Feed posts and articles",
        "doc_id": TEST_POST_ID,
        "document": {
            "_seed": SEED_MARKER,
            "author_uid":  TEST_UID_A,
            "type":        "post",              # post | article
            "content":     "This is a seeded test post for index initialisation.",
            "images":      [],                  # list[str] — media filenames
            "links":       [],                  # list[str]
            "hashtags":    ["setup", "test"],   # list[str] — extracted by extract_hashtags()
            "visibility":  "public",            # public | connections | group
            "group_id":    None,                # str | None — for group posts (Phase 4)
            "reaction_counts": {
                "insightful": 0,
                "motivating": 0,
                "support":    0,
            },
            "comment_count": 0,
            "share_count":   0,
            "view_count":    0,
            "deleted":       False,             # soft-delete flag (NEVER hard-delete posts)
            "created_at":    NOW,
            "updated_at":    NOW,
        },
        "subcollections": {

            # ── /posts/{id}/comments ──────────────────────────────────────────
            "comments": {
                "description": "Threaded comments on a post",
                "doc_id": TEST_COMMENT_ID,
                "document": {
                    "_seed": SEED_MARKER,
                    "author_uid":        TEST_UID_A,
                    "content":           "Seeded test comment.",
                    "parent_comment_id": None,    # str | None — for 2-level threading
                    "reaction_counts": {
                        "insightful": 0,
                        "motivating": 0,
                        "support":    0,
                    },
                    "deleted":    False,
                    "created_at": NOW,
                    "updated_at": NOW,
                }
            },

            # ── /posts/{id}/reactions ─────────────────────────────────────────
            "reactions": {
                "description": "Per-user reaction on a post (doc ID = uid)",
                "doc_id": TEST_UID_A,            # doc ID is always the reacting user's uid
                "document": {
                    "_seed":         SEED_MARKER,
                    "user_uid":      TEST_UID_A,
                    "reaction_type": "insightful",  # insightful | motivating | support
                    "created_at":    NOW,
                }
            },
        }
    },

    # ── /connections ──────────────────────────────────────────────────────────
    "connections": {
        "description": "Symmetric user connections (peer / mentor / mentee)",
        "doc_id": TEST_CONN_ID,
        "document": {
            "_seed":        SEED_MARKER,
            "user_a":       TEST_UID_A,
            "user_b":       TEST_UID_B,
            "participants": [TEST_UID_A, TEST_UID_B],  # array field — enables array_contains queries
            "status":       "accepted",   # pending | accepted | declined | withdrawn
            "type":         "peer",       # peer | mentor | mentee
            "message":      "",           # optional personal note on the request
            "created_at":   NOW,
            "updated_at":   NOW,
            "accepted_by":  TEST_UID_B,
        }
    },

    # ── /follows ──────────────────────────────────────────────────────────────
    "follows": {
        "description": "Asymmetric follow relationships",
        "doc_id": TEST_FOLLOW_ID,
        "document": {
            "_seed":          SEED_MARKER,
            "follower_uid":   TEST_UID_A,
            "following_uid":  TEST_UID_B,
            "entity_type":    "user",    # user (future: group | institution)
            "created_at":     NOW,
        }
    },

    # ── /collab_users (minimal — only fields posts system reads) ──────────────
    "collab_users": {
        "description": "Extended user profiles (seed only author fields needed by feed)",
        "doc_id": TEST_UID_A,
        "document": {
            "_seed":           SEED_MARKER,
            "uid":             TEST_UID_A,
            "name":            "_Seed User A",
            "headline":        "Setup seed account",
            "profile_picture": None,
            "profile_banner":  None,
            "post_count":      0,
            "follower_count":  0,
            "following_count": 0,
            "connection_count":0,
            "skills":          [],
            "created_at":      NOW,
            "updated_at":      NOW,
        }
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — COMPOSITE INDEX DEFINITIONS
# Each entry maps directly to one entry in firestore.indexes.json
# ══════════════════════════════════════════════════════════════════════════════

INDEXES = [

    # ── posts ─────────────────────────────────────────────────────────────────
    {
        "name": "posts — feed (deleted + created_at)",
        "usage": "get_feed_posts(): .where('deleted','==',False).order_by('created_at',DESC)",
        "collectionGroup": "posts",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "deleted",    "order": "ASCENDING"},
            {"fieldPath": "created_at", "order": "DESCENDING"},
        ],
    },
    {
        "name": "posts — hashtag feed (deleted + hashtags array + created_at)",
        "usage": "get_hashtag_posts(): .where('deleted','==',False).where('hashtags','array_contains',x).order_by('created_at',DESC)",
        "collectionGroup": "posts",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "deleted",    "order": "ASCENDING"},
            {"fieldPath": "hashtags",   "arrayConfig": "CONTAINS"},
            {"fieldPath": "created_at", "order": "DESCENDING"},
        ],
    },
    {
        "name": "posts — trending hashtags (deleted + created_at range)",
        "usage": "get_trending_hashtags(): .where('deleted','==',False).where('created_at','>=',week_ago)",
        "collectionGroup": "posts",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "deleted",    "order": "ASCENDING"},
            {"fieldPath": "created_at", "order": "ASCENDING"},
        ],
    },
    {
        "name": "posts — user's own posts (author_uid + deleted + created_at)",
        "usage": "profile feed (Phase 3): .where('author_uid','==',x).where('deleted','==',False).order_by('created_at',DESC)",
        "collectionGroup": "posts",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "author_uid", "order": "ASCENDING"},
            {"fieldPath": "deleted",    "order": "ASCENDING"},
            {"fieldPath": "created_at", "order": "DESCENDING"},
        ],
    },
    {
        "name": "posts — group feed (group_id + deleted + created_at)",
        "usage": "group detail page (Phase 4): .where('group_id','==',x).where('deleted','==',False).order_by('created_at',DESC)",
        "collectionGroup": "posts",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "group_id",   "order": "ASCENDING"},
            {"fieldPath": "deleted",    "order": "ASCENDING"},
            {"fieldPath": "created_at", "order": "DESCENDING"},
        ],
    },
    {
        "name": "posts — public feed (visibility + deleted + created_at)",
        "usage": "public/explore feed: .where('visibility','==','public').where('deleted','==',False).order_by('created_at',DESC)",
        "collectionGroup": "posts",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "visibility", "order": "ASCENDING"},
            {"fieldPath": "deleted",    "order": "ASCENDING"},
            {"fieldPath": "created_at", "order": "DESCENDING"},
        ],
    },

    # ── comments subcollection ────────────────────────────────────────────────
    {
        "name": "comments — active ordered (deleted + created_at)",
        "usage": "post detail: filter deleted, sort chronologically",
        "collectionGroup": "comments",
        "queryScope": "COLLECTION_GROUP",
        "fields": [
            {"fieldPath": "deleted",    "order": "ASCENDING"},
            {"fieldPath": "created_at", "order": "ASCENDING"},
        ],
    },
    {
        "name": "comments — thread replies (parent_comment_id + deleted + created_at)",
        "usage": "comment threading: .where('parent_comment_id','==',x).where('deleted','==',False).order_by('created_at',ASC)",
        "collectionGroup": "comments",
        "queryScope": "COLLECTION_GROUP",
        "fields": [
            {"fieldPath": "parent_comment_id", "order": "ASCENDING"},
            {"fieldPath": "deleted",           "order": "ASCENDING"},
            {"fieldPath": "created_at",        "order": "ASCENDING"},
        ],
    },
    {
        "name": "comments — user activity log (author_uid + created_at)",
        "usage": "activity log (Phase 6): .where('author_uid','==',x).order_by('created_at',DESC)",
        "collectionGroup": "comments",
        "queryScope": "COLLECTION_GROUP",
        "fields": [
            {"fieldPath": "author_uid", "order": "ASCENDING"},
            {"fieldPath": "created_at", "order": "DESCENDING"},
        ],
    },

    # ── reactions subcollection ───────────────────────────────────────────────
    {
        "name": "reactions — user activity log (user_uid + created_at)",
        "usage": "activity log (Phase 6): .where('user_uid','==',x).order_by('created_at',DESC)",
        "collectionGroup": "reactions",
        "queryScope": "COLLECTION_GROUP",
        "fields": [
            {"fieldPath": "user_uid",   "order": "ASCENDING"},
            {"fieldPath": "created_at", "order": "DESCENDING"},
        ],
    },

    # ── connections ───────────────────────────────────────────────────────────
    {
        "name": "connections — participants + status (dashboard / network / feed)",
        "usage": "dashboard, network page, feed: .where('participants','array_contains',uid).where('status','==','accepted')",
        "collectionGroup": "connections",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "participants", "arrayConfig": "CONTAINS"},
            {"fieldPath": "status",       "order": "ASCENDING"},
        ],
    },
    {
        "name": "connections — user_a + status (outgoing, suggestions exclusion)",
        "usage": "get_smart_suggestions, network page: .where('user_a','==',uid).where('status','in',[...])",
        "collectionGroup": "connections",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "user_a",  "order": "ASCENDING"},
            {"fieldPath": "status",  "order": "ASCENDING"},
        ],
    },
    {
        "name": "connections — user_b + status (incoming, suggestions exclusion)",
        "usage": "get_smart_suggestions, network page: .where('user_b','==',uid).where('status','in',[...])",
        "collectionGroup": "connections",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "user_b",  "order": "ASCENDING"},
            {"fieldPath": "status",  "order": "ASCENDING"},
        ],
    },
    {
        "name": "connections — user_a + status + created_at (sent requests tab)",
        "usage": "network page Sent tab: .where('user_a','==',uid).where('status','==','pending').order_by('created_at',DESC)",
        "collectionGroup": "connections",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "user_a",     "order": "ASCENDING"},
            {"fieldPath": "status",     "order": "ASCENDING"},
            {"fieldPath": "created_at", "order": "DESCENDING"},
        ],
    },
    {
        "name": "connections — user_b + status + created_at (received requests tab)",
        "usage": "network page Received tab: .where('user_b','==',uid).where('status','==','pending').order_by('created_at',DESC)",
        "collectionGroup": "connections",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "user_b",     "order": "ASCENDING"},
            {"fieldPath": "status",     "order": "ASCENDING"},
            {"fieldPath": "created_at", "order": "DESCENDING"},
        ],
    },
    {
        "name": "connections — participants + type + status (mentorship filter)",
        "usage": "mentorship page: .where('participants','array_contains',uid).where('type','==','mentor').where('status','==','accepted')",
        "collectionGroup": "connections",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "participants", "arrayConfig": "CONTAINS"},
            {"fieldPath": "type",         "order": "ASCENDING"},
            {"fieldPath": "status",       "order": "ASCENDING"},
        ],
    },

    # ── follows ───────────────────────────────────────────────────────────────
    {
        "name": "follows — follower_uid + following_uid (check/unfollow)",
        "usage": "api_follow_user, api_unfollow_user: .where('follower_uid','==',x).where('following_uid','==',y)",
        "collectionGroup": "follows",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "follower_uid",  "order": "ASCENDING"},
            {"fieldPath": "following_uid", "order": "ASCENDING"},
        ],
    },
    {
        "name": "follows — follower_uid + created_at (list who I follow)",
        "usage": "profile follows tab: .where('follower_uid','==',x).order_by('created_at',DESC)",
        "collectionGroup": "follows",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "follower_uid", "order": "ASCENDING"},
            {"fieldPath": "created_at",   "order": "DESCENDING"},
        ],
    },
    {
        "name": "follows — following_uid + created_at (list my followers)",
        "usage": "profile followers tab: .where('following_uid','==',x).order_by('created_at',DESC)",
        "collectionGroup": "follows",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "following_uid", "order": "ASCENDING"},
            {"fieldPath": "created_at",    "order": "DESCENDING"},
        ],
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — FIELD OVERRIDES (suppress auto-indexing on large text fields)
# ══════════════════════════════════════════════════════════════════════════════

FIELD_OVERRIDES = [
    {
        "collectionGroup": "posts",
        "fieldPath": "content",
        "reason": "Large text field — never queried directly. Disabling saves index storage.",
        "indexes": []
    },
    {
        "collectionGroup": "comments",
        "fieldPath": "content",
        "reason": "Large text field — never queried directly.",
        "indexes": []
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def colour(text: str, code: int) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text

green  = lambda t: colour(t, 32)
yellow = lambda t: colour(t, 33)
cyan   = lambda t: colour(t, 36)
bold   = lambda t: colour(t, 1)
dim    = lambda t: colour(t, 2)

def banner(text: str):
    w = 72
    print("\n" + "═" * w)
    print(f"  {bold(text)}")
    print("═" * w)


def write_doc(collection: str, doc_id: str, data: dict, dry_run: bool) -> str:
    ref = db.collection(collection).document(doc_id)
    if not dry_run:
        ref.set(data, merge=True)
        SEEDED_REFS.append(ref)
    return ref.path


def write_subdoc(post_ref, sub: str, doc_id: str, data: dict, dry_run: bool) -> str:
    ref = post_ref.collection(sub).document(doc_id)
    if not dry_run:
        ref.set(data, merge=True)
        SEEDED_REFS.append(ref)
    return ref.path


# ══════════════════════════════════════════════════════════════════════════════
# TASKS
# ══════════════════════════════════════════════════════════════════════════════

def task_seed(dry_run: bool = False):
    banner("STEP 1 — SEEDING COLLECTIONS")
    print(dim("Writing one skeleton document per collection so Firestore registers the schema.\n"))

    label = "[DRY RUN] Would write" if dry_run else "Seeding"

    for coll_name, coll in COLLECTIONS.items():
        doc   = coll["document"]
        path  = write_doc(coll_name, coll["doc_id"], doc, dry_run)
        print(f"  {green('✓')}  {label}  {bold(path)}")
        print(f"        {dim(coll['description'])}")

        # Subcollections (currently only posts has them)
        if "subcollections" in coll:
            post_ref = db.collection(coll_name).document(coll["doc_id"])
            for sub_name, sub in coll["subcollections"].items():
                sub_path = write_subdoc(post_ref, sub_name, sub["doc_id"], sub["document"], dry_run)
                print(f"     {green('↳')}  {label}  {bold(sub_path)}")
                print(f"           {dim(sub['description'])}")

    print(f"\n  {green('Done.')} {len(COLLECTIONS)} top-level collections + subcollections seeded.")
    if dry_run:
        print(yellow("  (Dry run — nothing was actually written.)"))


def task_index_report():
    banner("STEP 2 — REQUIRED COMPOSITE INDEXES")
    print(dim("These indexes MUST exist in Firestore for the app to work correctly.\n"))
    print(dim("  Deploy with:  firebase deploy --only firestore:indexes"))
    print(dim("  Or create manually in the Firebase Console → Firestore → Indexes\n"))

    by_collection: dict[str, list] = {}
    for idx in INDEXES:
        cg = idx["collectionGroup"]
        by_collection.setdefault(cg, []).append(idx)

    total = 0
    for cg, idxs in by_collection.items():
        print(f"\n  {bold(cyan(cg.upper()))}  ({len(idxs)} indexes)")
        print("  " + "─" * 68)
        for idx in idxs:
            total += 1
            fields_str = ", ".join(
                f"{f['fieldPath']} {'▼' if f.get('order') == 'DESCENDING' else ('∈' if 'arrayConfig' in f else '▲')}"
                for f in idx["fields"]
            )
            scope = "Collection Group" if idx["queryScope"] == "COLLECTION_GROUP" else "Collection"
            print(f"  {green(str(total).rjust(2))}  {bold(idx['name'])}")
            print(f"       Fields : {fields_str}")
            print(f"       Scope  : {scope}")
            print(f"       Used by: {dim(idx['usage'])}")

    print(f"\n  {bold(str(total))} composite indexes required in total.")


def task_field_overrides():
    banner("STEP 3 — FIELD OVERRIDES (suppress auto-indexing)")
    print(dim("These fields should have auto-indexing DISABLED in the Firebase Console\n"
              "or via firestore.indexes.json fieldOverrides to save storage.\n"))
    for fo in FIELD_OVERRIDES:
        print(f"  {yellow('⚠')}  {bold(fo['collectionGroup'])}.{bold(fo['fieldPath'])}")
        print(f"       {dim(fo['reason'])}")


def task_export_json():
    banner("STEP 4 — firestore.indexes.json (deployable)")
    print(dim("You can deploy this file directly:  firebase deploy --only firestore:indexes\n"))

    clean_indexes = []
    for idx in INDEXES:
        clean = {
            "collectionGroup": idx["collectionGroup"],
            "queryScope":      idx["queryScope"],
            "fields":          [
                {k: v for k, v in f.items()}
                for f in idx["fields"]
            ],
        }
        clean_indexes.append(clean)

    clean_overrides = []
    for fo in FIELD_OVERRIDES:
        clean_overrides.append({
            "collectionGroup": fo["collectionGroup"],
            "fieldPath":       fo["fieldPath"],
            "indexes":         fo["indexes"],
        })

    output = {
        "indexes":        clean_indexes,
        "fieldOverrides": clean_overrides,
    }

    # Write to file alongside this script
    out_path = "firestore.indexes.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"  {green('✓')}  Written to {bold(out_path)}")
    print(f"       Contains {len(clean_indexes)} composite indexes and {len(clean_overrides)} field overrides.")


def task_verify():
    """
    Light verification — check the seed documents are readable
    and confirm the data shapes look correct.
    """
    banner("STEP 5 — VERIFICATION")
    print(dim("Reading back seeded documents to verify write succeeded.\n"))

    checks = [
        ("posts",        TEST_POST_ID,    ["author_uid", "deleted", "hashtags", "created_at"]),
        ("connections",  TEST_CONN_ID,    ["user_a", "user_b", "participants", "status"]),
        ("follows",      TEST_FOLLOW_ID,  ["follower_uid", "following_uid"]),
        ("collab_users", TEST_UID_A,      ["uid", "name"]),
    ]

    all_ok = True
    for coll, doc_id, required_fields in checks:
        doc = db.collection(coll).document(doc_id).get()
        if doc.exists:
            data = doc.to_dict()
            missing = [f for f in required_fields if f not in data]
            if missing:
                print(f"  {yellow('⚠')}  {coll}/{doc_id}  — missing fields: {missing}")
                all_ok = False
            else:
                print(f"  {green('✓')}  {coll}/{doc_id}  — all required fields present")
        else:
            print(f"  ✕  {coll}/{doc_id}  — NOT FOUND (write may have failed)")
            all_ok = False

    # Check post subcollections
    post_ref = db.collection("posts").document(TEST_POST_ID)
    for sub, doc_id in [("comments", TEST_COMMENT_ID), ("reactions", TEST_UID_A)]:
        doc = post_ref.collection(sub).document(doc_id).get()
        if doc.exists:
            print(f"  {green('✓')}  posts/{TEST_POST_ID}/{sub}/{doc_id}  — exists")
        else:
            print(f"  ✕  posts/{TEST_POST_ID}/{sub}/{doc_id}  — NOT FOUND")
            all_ok = False

    print()
    if all_ok:
        print(f"  {green(bold('All checks passed.'))}  Collections and schemas are correctly registered.")
    else:
        print(yellow("  Some checks failed — review the errors above."))

    return all_ok


def task_cleanup():
    banner("CLEANUP — Deleting seeded test documents")
    print(dim("Removing all documents tagged with _seed = '__setup_seed__'\n"))

    deleted = 0

    def try_delete(ref):
        nonlocal deleted
        try:
            ref.delete()
            print(f"  {green('✓')}  Deleted  {ref.path}")
            deleted += 1
        except Exception as e:
            print(f"  ✕  Could not delete {ref.path}: {e}")

    # Posts subcollections first
    post_ref = db.collection("posts").document(TEST_POST_ID)
    for sub, doc_id in [("comments", TEST_COMMENT_ID), ("reactions", TEST_UID_A)]:
        try_delete(post_ref.collection(sub).document(doc_id))

    # Top-level collections
    for coll, doc_id in [
        ("posts",         TEST_POST_ID),
        ("connections",   TEST_CONN_ID),
        ("follows",       TEST_FOLLOW_ID),
        ("collab_users",  TEST_UID_A),
    ]:
        try_delete(db.collection(coll).document(doc_id))

    print(f"\n  {green('Cleanup complete.')}  {deleted} document(s) deleted.")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="ScleraCollab — Firestore posts system setup script"
    )
    parser.add_argument("--dry-run",    action="store_true", help="Print what would happen; don't write")
    parser.add_argument("--seed-only",  action="store_true", help="Only seed documents, skip index report")
    parser.add_argument("--index-only", action="store_true", help="Only print index report, skip seeding")
    parser.add_argument("--cleanup",    action="store_true", help="Delete all seeded test documents")
    args = parser.parse_args()

    print()
    print(bold("ScleraCollab — Firestore Setup Script"))
    print(dim(f"  Running at {NOW}\n"))

    if args.cleanup:
        task_cleanup()
        return

    if not args.index_only:
        task_seed(dry_run=args.dry_run)

    if not args.seed_only:
        task_index_report()
        task_field_overrides()
        task_export_json()

    if not args.index_only and not args.dry_run:
        task_verify()

    banner("SETUP COMPLETE")
    print(dim("Next steps:"))
    print(f"  1.  {bold('firebase deploy --only firestore:indexes')}")
    print(f"      This deploys the generated {bold('firestore.indexes.json')} to your project.")
    print(f"  2.  Wait for indexes to build (can take 5–15 min in Firebase Console).")
    print(f"  3.  Run {bold('python setup_firestore_posts.py --cleanup')} to remove the seed documents.")
    print(f"  4.  Your posts system is ready.\n")


if __name__ == "__main__":
    main()
