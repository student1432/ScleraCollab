#!/usr/bin/env python3
"""
Debug script to check author profiles
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from firebase_config import db

def debug_authors():
    """Debug author profiles"""
    print("🔍 Debugging Author Profiles")
    print("=" * 40)
    
    try:
        # Check specific authors
        authors_to_check = [
            'test_user_123',
            'okKc2L8CMZT7uk3fmBBncIDxtm63',
            'xP1vMIxRydadezndHJHpq9APS423',
            '_seed_user_a_8a11c4b4'
        ]
        
        for author_uid in authors_to_check:
            print(f"\n👤 Checking author: {author_uid}")
            
            # Check collab_users collection
            author_doc = db.collection('collab_users').document(author_uid).get()
            if author_doc.exists:
                author_data = author_doc.to_dict()
                print(f"   ✅ Found in collab_users")
                print(f"   📝 Name: {author_data.get('name', 'N/A')}")
                print(f"   🎓 Headline: {author_data.get('headline', 'N/A')}")
                print(f"   ✅ Verified: {author_data.get('verified', False)}")
            else:
                print(f"   ❌ NOT found in collab_users")
            
            # Check users collection (original Sclera)
            user_doc = db.collection('users').document(author_uid).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                print(f"   ✅ Found in users collection")
                print(f"   📧 Email: {user_data.get('email', 'N/A')}")
                print(f"   📝 Name: {user_data.get('name', 'N/A')}")
            else:
                print(f"   ❌ NOT found in users collection")
        
        # List all users in collab_users
        print(f"\n📋 All users in collab_users:")
        all_users = db.collection('collab_users').get()
        for user in all_users:
            user_data = user.to_dict()
            print(f"   - {user.id}: {user_data.get('name', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error debugging authors: {e}")

if __name__ == "__main__":
    debug_authors()
