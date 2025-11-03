"""
SwaRAG - Stack Overflow RAG System
Main entry point for the application

This system provides:
1. Stack Overflow Q&A download and indexing
2. Query optimization using algorithms (Boolean retrieval, positional index, biword index)
3. BM25 ranking for relevance scoring
4. Live Assist feature for real-time API queries
5. RAG (Retrieval-Augmented Generation) for answer generation
6. API endpoints for search (with and without RAG)
"""

import sys
import argparse
from data.database import Database
from processing.text_processing import TextProcessor
from indexing.indexer import Indexer
from ranking.bm25_ranker import BM25Ranker
from rag.rag_integration import RAGIntegration, LiveAssist
from data.stackoverflow_downloader import StackOverflowDownloader
import json


# Configuration
STACK_API_KEY = "rl_fGs2ccsxwAxAuDAQ3EjWyXknM"
CLIENT_ID = "35343"
DB_PATH = "stackoverflow.db"


def download_and_index(tags, max_pages=5):
    """Download Stack Overflow data and build index"""
    print("=" * 80)
    print("STEP 1: Downloading Stack Overflow Q&A Data")
    print("=" * 80)
    
    db = Database(DB_PATH)
    downloader = StackOverflowDownloader(api_key=STACK_API_KEY, client_id=CLIENT_ID)
    
    # Download data
    downloader.download_and_store(db, tags, max_pages_per_tag=max_pages)
    
    print("\n" + "=" * 80)
    print("STEP 2: Building Inverted Index, Biword Index, and Positional Index")
    print("=" * 80)
    
    # Build index
    text_processor = TextProcessor()
    indexer = Indexer(db, text_processor)
    
    # Get all questions
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions")
    questions = cursor.fetchall()
    
    print(f"Indexing {len(questions)} questions...")
    
    for i, question in enumerate(questions):
        q_dict = dict(question)
        question_id = q_dict['question_id']
        title = q_dict['title']
        body = q_dict['body']
        tags_json = json.loads(q_dict.get('tags', '[]'))
        
        # Index question
        indexer.index_question(question_id, title, body, tags_json)
        
        # Index answers
        answers = db.get_answers(question_id)
        for answer in answers:
            answer_id = answer['answer_id']
            answer_body = answer['body']
            indexer.index_answer(answer_id, question_id, answer_body)
        
        if (i + 1) % 100 == 0:
            print(f"  Indexed {i + 1} questions...")
    
    print("Indexing complete!")
    print(f"Total questions indexed: {len(questions)}")
    
    db.close()


def search_local(query, max_results=10):
    """Search local index without RAG"""
    print("\n" + "=" * 80)
    print(f"SEARCHING LOCAL INDEX: {query}")
    print("=" * 80)
    
    db = Database(DB_PATH)
    text_processor = TextProcessor()
    bm25_ranker = BM25Ranker(db, text_processor)
    
    # Search and rank
    results = bm25_ranker.search_and_rank(query, max_results=max_results)
    
    print(f"\nFound {len(results)} results:\n")
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['title']}")
        print(f"   Score: {result['bm25_score']:.4f}")
        print(f"   Link: {result['link']}")
        print(f"   Answers: {len(result['answers'])}")
        
        if result['answers']:
            best_answer = result['answers'][0]
            answer_preview = best_answer['body'][:150].replace('\n', ' ')
            print(f"   Top Answer: {answer_preview}...")
        
        print()
    
    db.close()
    return results


def search_with_rag(query, max_results=10):
    """Search and generate answer using RAG"""
    print("\n" + "=" * 80)
    print(f"SEARCHING WITH RAG: {query}")
    print("=" * 80)
    
    db = Database(DB_PATH)
    text_processor = TextProcessor()
    bm25_ranker = BM25Ranker(db, text_processor)
    rag = RAGIntegration(STACK_API_KEY)
    
    # Search and rank
    results = bm25_ranker.search_and_rank(query, max_results=max_results)
    
    print(f"\nFound {len(results)} results from local index")
    
    if results:
        print("\n" + "-" * 80)
        print("GENERATING ANSWER USING RAG...")
        print("-" * 80)
        
        # Generate answer
        rag_result = rag.generate_answer(query, results)
        
        print("\n**Generated Answer:**\n")
        print(rag_result['answer'])
        
        print("\n**Citations:**")
        for citation in rag_result['citations']:
            print(f"  [{citation['id']}] {citation['title']}")
            print(f"      {citation['link']}")
            print()
    
    db.close()


def search_with_live_assist(query, max_results=10):
    """Search with live assist fallback"""
    print("\n" + "=" * 80)
    print(f"SEARCHING WITH LIVE ASSIST: {query}")
    print("=" * 80)
    
    db = Database(DB_PATH)
    text_processor = TextProcessor()
    bm25_ranker = BM25Ranker(db, text_processor)
    live_assist = LiveAssist(STACK_API_KEY)
    
    # Search local
    local_results = bm25_ranker.search_and_rank(query, max_results=max_results)
    
    print(f"\nLocal results: {len(local_results)}")
    
    # Check if we should use live assist
    should_use_live = live_assist.should_use_live_assist(local_results)
    
    if should_use_live:
        print("\nConfidence low. Using Live Assist...")
        live_results = live_assist.fetch_live_results(query, max_results=5)
        
        print(f"\nLive results: {len(live_results)}\n")
        
        for i, result in enumerate(live_results, 1):
            print(f"{i}. {result['title']}")
            print(f"   Link: {result['link']}")
            print(f"   Score: {result['score']}")
            print()
    else:
        print("\nLocal results are sufficient. Not using Live Assist.\n")
        
        for i, result in enumerate(local_results[:5], 1):
            print(f"{i}. {result['title']}")
            print(f"   Score: {result['bm25_score']:.4f}")
            print(f"   Link: {result['link']}")
            print()
    
    db.close()


def show_stats():
    """Show database statistics"""
    print("\n" + "=" * 80)
    print("DATABASE STATISTICS")
    print("=" * 80)
    
    db = Database(DB_PATH)
    
    question_count = db.get_question_count()
    total_docs = db.get_total_docs()
    avg_doc_length = db.get_avg_doc_length()
    
    print(f"Total Questions: {question_count}")
    print(f"Total Documents (questions + answers): {total_docs}")
    print(f"Average Document Length: {avg_doc_length:.2f} terms")
    
    db.close()


def interactive_mode():
    """Interactive command-line interface"""
    print("\n" + "=" * 80)
    print("SwaRAG - Interactive Mode")
    print("=" * 80)
    print("\nCommands:")
    print("  search <query>     - Search local index")
    print("  rag <query>        - Search with RAG")
    print("  live <query>       - Search with live assist")
    print("  stats              - Show statistics")
    print("  quit               - Exit")
    print()
    
    while True:
        try:
            user_input = input("\nSwaRAG> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'quit':
                break
            
            if user_input.lower() == 'stats':
                show_stats()
                continue
            
            parts = user_input.split(' ', 1)
            if len(parts) < 2:
                print("Invalid command. Use: <command> <query>")
                continue
            
            command = parts[0].lower()
            query = parts[1]
            
            if command == 'search':
                search_local(query)
            elif command == 'rag':
                search_with_rag(query)
            elif command == 'live':
                search_with_live_assist(query)
            else:
                print(f"Unknown command: {command}")
        
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='SwaRAG - Stack Overflow RAG System',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--download', action='store_true',
                       help='Download Stack Overflow data and build index')
    parser.add_argument('--tags', nargs='+', 
                       default=['spring-boot', 'react', 'django', 'node.js'],
                       help='Tags to download (default: spring-boot react django node.js)')
    parser.add_argument('--max-pages', type=int, default=5,
                       help='Maximum pages per tag to download (default: 5)')
    
    parser.add_argument('--search', type=str,
                       help='Search query (local index only)')
    parser.add_argument('--rag', type=str,
                       help='Search query with RAG answer generation')
    parser.add_argument('--live', type=str,
                       help='Search query with live assist')
    
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics')
    
    parser.add_argument('--api', action='store_true',
                       help='Start API server')
    
    parser.add_argument('--interactive', action='store_true',
                       help='Start interactive mode')
    
    args = parser.parse_args()
    
    # Handle commands
    if args.download:
        download_and_index(args.tags, args.max_pages)
    
    elif args.search:
        search_local(args.search)
    
    elif args.rag:
        search_with_rag(args.rag)
    
    elif args.live:
        search_with_live_assist(args.live)
    
    elif args.stats:
        show_stats()
    
    elif args.api:
        print("Starting API server...")
        from api.api import app
        app.run(debug=True, host='0.0.0.0', port=5000)
    
    elif args.interactive:
        interactive_mode()
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

