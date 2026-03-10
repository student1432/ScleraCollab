#!/usr/bin/env python3
"""
Firebase Auth Users Importer
Lists all authenticated users from Firebase Auth
"""

import os
import json
from firebase_config import fb_auth
from firebase_admin import auth

def list_all_auth_users():
    """List all authenticated users from Firebase Auth"""
    print("🔐 Firebase Auth Users Inspector")
    print("=" * 50)
    
    try:
        # List all users
        users = auth.list_users()
        user_count = len(users.users)
        
        print(f"\n👥 Total Authenticated Users: {user_count}")
        print("-" * 40)
        
        if user_count == 0:
            print("❌ No authenticated users found")
            return
        
        # Display user information
        for i, user in enumerate(users.users, 1):
            print(f"\n👤 User #{i}")
            print(f"   📧 Email: {user.email}")
            print(f"   🆔 UID: {user.uid}")
            print(f"   📝 Display Name: {user.display_name or 'Not set'}")
            print(f"   📱 Phone: {user.phone_number or 'Not set'}")
            print(f"   📸 Photo URL: {user.photo_url or 'Not set'}")
            print(f"   ✅ Email Verified: {user.email_verified}")
            print(f"   🕒 Created: {user.user_metadata.creation_time}")
            print(f"   🔄 Last Sign-in: {user.user_metadata.last_sign_in_time}")
            print(f"   🔥 Provider: {user.provider_id}")
            
            # Check custom claims
            if user.custom_claims:
                print(f"   🎭 Custom Claims: {user.custom_claims}")
            
            # Check if user is disabled
            if user.disabled:
                print(f"   ⚠️  Status: DISABLED")
            else:
                print(f"   ✅ Status: Active")
        
        print(f"\n" + "=" * 50)
        print(f"✅ Successfully listed {user_count} authenticated users!")
        
        # Export to JSON for reference
        users_data = []
        for user in users.users:
            users_data.append({
                'uid': user.uid,
                'email': user.email,
                'display_name': user.display_name,
                'email_verified': user.email_verified,
                'created_at': user.user_metadata.creation_time.isoformat() if user.user_metadata.creation_time else None,
                'last_sign_in': user.user_metadata.last_sign_in_time.isoformat() if user.user_metadata.last_sign_in_time else None,
                'provider': user.provider_id,
                'disabled': user.disabled,
                'phone_number': user.phone_number,
                'photo_url': user.photo_url
            })
        
        # Save to file
        with open('auth_users_export.json', 'w', encoding='utf-8') as f:
            json.dump(users_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Exported user data to: auth_users_export.json")
        
    except Exception as e:
        print(f"❌ Error listing auth users: {e}")
        print("Make sure your Firebase Admin SDK has proper permissions")

def compare_auth_with_firestore():
    """Compare auth users with collab_users collection"""
    print("\n" + "=" * 50)
    print("🔄 Auth Users vs Firestore Comparison")
    print("=" * 50)
    
    try:
        from firebase_config import db
        
        # Get auth users
        auth_users = auth.list_users()
        auth_uids = {user.uid for user in auth_users.users}
        
        # Get collab_users
        collab_users = db.collection('collab_users').stream()
        collab_uids = {doc.id for doc in collab_users}
        
        print(f"\n📊 Comparison Summary:")
        print(f"   🔐 Auth Users: {len(auth_uids)}")
        print(f"   📄 Collab Users: {len(collab_uids)}")
        
        # Find differences
        auth_only = auth_uids - collab_uids
        collab_only = collab_uids - auth_uids
        common = auth_uids & collab_uids
        
        print(f"   ✅ Users in both: {len(common)}")
        print(f"   ⚠️  Auth only (no profile): {len(auth_only)}")
        print(f"   ⚠️  Collab only (no auth): {len(collab_only)}")
        
        if auth_only:
            print(f"\n⚠️  Auth users without collab profiles:")
            for uid in auth_only:
                user = next((u for u in auth_users.users if u.uid == uid), None)
                if user:
                    print(f"   📧 {user.email} ({uid})")
        
        if collab_only:
            print(f"\n⚠️  Collab profiles without auth users:")
            for uid in collab_only:
                print(f"   🆔 {uid}")
        
        # Get original users collection for comparison
        try:
            original_users = db.collection('users').stream()
            original_uids = {doc.id for doc in original_users}
            
            print(f"\n📚 Original users collection: {len(original_uids)}")
            
            original_only = original_uids - auth_uids
            if original_only:
                print(f"   ⚠️  Original users without auth: {len(original_only)}")
        
        except Exception as e:
            print(f"   ⚠️  Could not check original users collection: {e}")
            
    except Exception as e:
        print(f"❌ Error comparing users: {e}")

def create_missing_profiles():
    """Create collab profiles for auth users who don't have them"""
    print("\n" + "=" * 50)
    print("🔧 Profile Creation for Missing Users")
    print("=" * 50)
    
    try:
        from firebase_config import db
        from collab_utils import initialize_collab_profile
        
        # Get auth users
        auth_users = auth.list_users()
        
        # Get existing collab users
        collab_users = db.collection('collab_users').stream()
        existing_uids = {doc.id for doc in collab_users}
        
        created_count = 0
        for user in auth_users.users:
            if user.uid not in existing_uids:
                # Create profile
                profile_data = initialize_collab_profile(
                    uid=user.uid,
                    name=user.display_name or user.email.split('@')[0],
                    email=user.email
                )
                
                db.collection('collab_users').document(user.uid).set(profile_data)
                print(f"   ✅ Created profile for: {user.email}")
                created_count += 1
        
        print(f"\n🎉 Created {created_count} missing profiles!")
        
    except Exception as e:
        print(f"❌ Error creating profiles: {e}")

if __name__ == "__main__":
    # List all auth users
    list_all_auth_users()
    
    # Compare with Firestore
    compare_auth_with_firestore()
    
    # Ask if user wants to create missing profiles
    print(f"\n" + "=" * 50)
    response = input("🔧 Create missing collab profiles? (y/n): ").lower().strip()
    if response == 'y':
        create_missing_profiles()
    else:
        print("✅ Skipping profile creation")
