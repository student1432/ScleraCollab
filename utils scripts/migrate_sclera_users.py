#!/usr/bin/env python3
"""
Sclera to ScleraCollab Migration Script
Migrates existing Sclera users to ScleraCollab profiles
"""

import os
import json
from firebase_config import db, fb_auth
from firebase_admin import auth
from collab_utils import initialize_collab_profile
from datetime import datetime

def get_all_sclera_users():
    """Get all users from original Sclera collection"""
    try:
        users_ref = db.collection('users')
        users = users_ref.stream()
        return [doc.to_dict() for doc in users]
    except Exception as e:
        print(f"Error getting Sclera users: {e}")
        return []

def get_all_auth_users():
    """Get all authenticated users from Firebase Auth"""
    try:
        users = auth.list_users()
        return {user.email: user for user in users.users}
    except Exception as e:
        print(f"Error getting auth users: {e}")
        return {}

def migrate_sclera_user(sclera_user, auth_user=None):
    """Migrate a single Sclera user to Collab profile"""
    email = sclera_user.get('email')
    uid = sclera_user.get('uid')
    
    if not email or not uid:
        print(f"⚠️  Skipping user missing email or UID: {sclera_user}")
        return False
    
    # Check if Collab profile already exists
    try:
        existing = db.collection('collab_users').document(uid).get()
        if existing.exists:
            print(f"⏭️  Collab profile already exists for {email}")
            return True
    except Exception as e:
        print(f"Error checking existing profile: {e}")
    
    # Create Collab profile from Sclera data
    try:
        profile = initialize_collab_profile(uid, sclera_user.get('name', ''), email)
        
        # Import Sclera-specific data
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
        
        # Mark as migrated
        profile['imported_from_sclera'] = True
        profile['sclera_import_date'] = datetime.utcnow().isoformat()
        profile['sclera_user_id'] = sclera_user.get('id')
        
        # Save profile
        db.collection('collab_users').document(uid).set(profile)
        print(f"✅ Migrated: {email} -> {uid}")
        return True
        
    except Exception as e:
        print(f"❌ Error migrating {email}: {e}")
        return False

def run_migration():
    """Run the complete migration process"""
    print("🔄 Sclera to ScleraCollab Migration")
    print("=" * 50)
    
    # Get all Sclera users
    sclera_users = get_all_sclera_users()
    print(f"📚 Found {len(sclera_users)} Sclera users")
    
    # Get all auth users for reference
    auth_users = get_all_auth_users()
    print(f"🔐 Found {len(auth_users)} authenticated users")
    
    if not sclera_users:
        print("❌ No Sclera users found to migrate")
        return
    
    # Migration statistics
    migrated = 0
    skipped = 0
    errors = 0
    
    for sclera_user in sclera_users:
        try:
            success = migrate_sclera_user(sclera_user)
            if success:
                migrated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"❌ Fatal error migrating user: {e}")
            errors += 1
    
    print(f"\n" + "=" * 50)
    print("📊 Migration Summary:")
    print(f"   ✅ Successfully migrated: {migrated}")
    print(f"   ⏭️  Skipped: {skipped}")
    print(f"   ❌ Errors: {errors}")
    print(f"   📚 Total Sclera users: {len(sclera_users)}")
    
    if migrated > 0:
        print(f"\n🎉 Migration completed! {migrated} users now have Collab profiles.")
        print("💡 Users can now login to ScleraCollab with their Sclera credentials.")

def check_migration_status():
    """Check current migration status"""
    print("📊 Migration Status Check")
    print("=" * 30)
    
    try:
        # Count Sclera users
        sclera_count = len(db.collection('users').get())
        
        # Count Collab users
        collab_count = len(db.collection('collab_users').get())
        
        # Count migrated users
        migrated_query = db.collection('collab_users').where('imported_from_sclera', '==', True).get()
        migrated_count = len(migrated_query)
        
        print(f"📚 Original Sclera users: {sclera_count}")
        print(f"👥 Total Collab users: {collab_count}")
        print(f"🔄 Migrated from Sclera: {migrated_count}")
        print(f"🆕 New Collab-only users: {collab_count - migrated_count}")
        
        if sclera_count > migrated_count:
            print(f"⚠️  {sclera_count - migrated_count} Sclera users still need migration")
        else:
            print("✅ All Sclera users have been migrated!")
            
    except Exception as e:
        print(f"❌ Error checking status: {e}")

if __name__ == "__main__":
    import uuid
    import sys
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            check_migration_status()
        elif sys.argv[1] == "migrate":
            print("🔄 Running migration...")
            run_migration()
        else:
            print("Usage: python migrate_sclera_users.py [status|migrate]")
    else:
        print("Choose an option:")
        print("1. Check migration status")
        print("2. Run full migration")
        print("3. Exit")
        
        choice = input("Enter choice (1-3): ").strip()
        
        if choice == "1":
            check_migration_status()
        elif choice == "2":
            confirm = input("⚠️  This will migrate all Sclera users. Continue? (y/n): ").lower()
            if confirm == 'y':
                run_migration()
            else:
                print("❌ Migration cancelled")
        elif choice == "3":
            print("👋 Goodbye!")
        else:
            print("❌ Invalid choice")
