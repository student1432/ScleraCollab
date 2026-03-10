#!/usr/bin/env python3
"""
Debug script to check posts in the database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from firebase_config import db

def debug_posts():
    """Debug posts in the database"""
    print("🔍 Debugging Posts Database")
    print("=" * 40)
    
    try:
        # Get all posts (without deleted filter)
        all_posts = db.collection('posts').get()
        print(f"📊 Total posts in database: {len(all_posts)}")
        
        # Get non-deleted posts
        active_posts = db.collection('posts').where('deleted', '==', False).get()
        print(f"📊 Active (non-deleted) posts: {len(active_posts)}")
        
        # Get deleted posts
        deleted_posts = db.collection('posts').where('deleted', '==', True).get()
        print(f"📊 Deleted posts: {len(deleted_posts)}")
        
        # Analyze visibility of active posts
        visibility_counts = {'public': 0, 'connections': 0, 'private': 0, 'unspecified': 0}
        authors = set()
        
        for post in active_posts:
            post_data = post.to_dict()
            visibility = post_data.get('visibility', 'unspecified')
            visibility_counts[visibility] += 1
            authors.add(post_data.get('author_uid'))
        
        print(f"\n👥 Active post authors: {len(authors)}")
        print(f"👁️  Visibility breakdown:")
        for visibility, count in visibility_counts.items():
            print(f"   - {visibility}: {count}")
        
        # Show sample posts
        print(f"\n📝 Sample active posts (first 5):")
        for i, post in enumerate(active_posts[:5]):
            post_data = post.to_dict()
            print(f"   {i+1}. ID: {post.id}")
            print(f"      Author: {post_data.get('author_uid', 'N/A')}")
            print(f"      Visibility: {post_data.get('visibility', 'N/A')}")
            print(f"      Content: {(post_data.get('content', '')[:50])}...")
            print(f"      Created: {post_data.get('created_at', 'N/A')}")
            print()
        
    except Exception as e:
        print(f"❌ Error debugging posts: {e}")

if __name__ == "__main__":
    debug_posts()
