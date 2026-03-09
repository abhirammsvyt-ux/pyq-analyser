#!/usr/bin/env python
"""
Download required AI models for PYQ Analyzer.
Run this script after installing dependencies.
"""
import sys


def download_embedding_model():
    """Download the sentence-transformer embedding model."""
    print("Downloading embedding model (all-MiniLM-L6-v2)...")
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✓ Embedding model downloaded successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to download embedding model: {e}")
        return False


def download_spacy_model():
    """Download the spaCy NLP model."""
    print("Downloading spaCy model (en_core_web_sm)...")
    try:
        import spacy
        try:
            spacy.load('en_core_web_sm')
            print("✓ spaCy model already installed")
        except OSError:
            from spacy.cli import download
            download('en_core_web_sm')
            print("✓ spaCy model downloaded successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to download spaCy model: {e}")
        return False


def main():
    print("=" * 50)
    print("PYQ Analyzer - Model Download Script")
    print("=" * 50)
    print()
    
    success = True
    
    success &= download_embedding_model()
    print()
    success &= download_spacy_model()
    
    print()
    print("=" * 50)
    if success:
        print("All models downloaded successfully!")
    else:
        print("Some models failed to download. Check errors above.")
        sys.exit(1)


if __name__ == '__main__':
    main()
