#!/usr/bin/env python3
"""
Firebase Collections Inspector
Lists all collections in your Firestore database
"""

import os
import json
from firebase_config import db
from firebase_admin import firestore

def list_all_collections():
    """Recursively list all collections and subcollections"""
    print("🔍 Firebase Firestore Collections Inspector")
    print("=" * 50)
    
    collections = {}
    
    # Get top-level collections
    try:
        top_level_collections = db.collections()
        print("\n📁 Top-Level Collections:")
        print("-" * 30)
        
        for collection_ref in top_level_collections:
            collection_name = collection_ref.id
            print(f"📂 /{collection_name}")
            
            # Get sample documents to check for subcollections
            try:
                docs = collection_ref.limit(3).stream()
                subcollections = set()
                
                for doc in docs:
                    # Get subcollections for this document
                    try:
                        subcolls = doc.reference.collections()
                        for subcoll in subcolls:
                            subcollections.add(subcoll.id)
                    except Exception as e:
                        print(f"   ⚠️  Error getting subcollections for doc {doc.id}: {e}")
                
                if subcollections:
                    for subcoll in sorted(subcollections):
                        print(f"   📄 /{collection_name}/{{doc_id}}/{subcoll}")
                
                # Count documents
                try:
                    doc_count = len(list(collection_ref.stream()))
                    print(f"   📊 Documents: {doc_count}")
                except Exception as e:
                    print(f"   ⚠️  Error counting documents: {e}")
                    
            except Exception as e:
                print(f"   ⚠️  Error accessing collection: {e}")
            
            print()
            
    except Exception as e:
        print(f"❌ Error accessing Firestore: {e}")
        return
    
    print("\n" + "=" * 50)
    print("✅ Collection listing complete!")

def get_collection_stats(collection_name):
    """Get detailed stats for a specific collection"""
    try:
        collection_ref = db.collection(collection_name)
        docs = list(collection_ref.stream())
        
        print(f"\n📊 Detailed Stats for: {collection_name}")
        print("-" * 40)
        print(f"Total Documents: {len(docs)}")
        
        if docs:
            # Show sample document structure
            sample_doc = docs[0].to_dict()
            print(f"\nSample Document Fields:")
            for key, value in sample_doc.items():
                if isinstance(value, dict):
                    print(f"  📁 {key}: {{object}}")
                    for subkey in value.keys():
                        print(f"    └─ {subkey}")
                elif isinstance(value, list):
                    print(f"  📋 {key}: [{len(value)} items]")
                else:
                    print(f"  📝 {key}: {type(value).__name__}")
        
    except Exception as e:
        print(f"❌ Error getting stats for {collection_name}: {e}")

if __name__ == "__main__":
    list_all_collections()
    
    # Optional: Get detailed stats for main collections
    main_collections = ['collab_users', 'connections', 'follows', 'posts']
    
    print("\n" + "=" * 50)
    print("📈 Detailed Statistics for Main Collections:")
    print("=" * 50)
    
    for collection in main_collections:
        try:
            get_collection_stats(collection)
        except Exception as e:
            print(f"⚠️  Could not get stats for {collection}: {e}")
