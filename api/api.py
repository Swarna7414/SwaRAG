from flask import Flask, request, jsonify
from flask_cors import CORS
from typing import Dict, List
import json
import os

from data.database import Database
from processing.text_processing import TextProcessor
from indexing.indexer import Indexer, QueryProcessor
from ranking.bm25_ranker import BM25Ranker
from rag.rag_integration import RAGIntegration
from data.stackoverflow_downloader import StackOverflowDownloader
import requests



app = Flask(__name__)
CORS(app)


STACK_API_KEY = "rl_fGs2ccsxwAxAuDAQ3EjWyXknM"
CLIENT_ID = "35343"
DB_PATH = "stackoverflow.db"


db = Database(DB_PATH)
text_processor = TextProcessor()
indexer = Indexer(db, text_processor)
query_processor = QueryProcessor(db, text_processor)
bm25_ranker = BM25Ranker(db, text_processor)
rag_integration = RAGIntegration(STACK_API_KEY)
stackoverflow_downloader = StackOverflowDownloader(api_key=STACK_API_KEY, client_id=CLIENT_ID)


@app.route('/health', methods=['GET'])
def health_check():

    question_count = db.get_question_count()
    
    return jsonify({
        'status': 'healthy',
        'database': 'connected',
        'questions_indexed': question_count
    })


@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        query = data.get('query', '')
        max_results = data.get('max_results', 10)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Step 1: Search local database
        results = bm25_ranker.search_and_rank(query, max_results=max_results)
        
        # Step 2: If NO results, fetch from Stack Overflow API (Live Assist)
        used_live = False
        if len(results) == 0:
            print(f"⚠️ No local results found for query: '{query}'")
            results = _fetch_live_results(query, max_results=max_results)
            used_live = True
        
        response = {
            'query': query,
            'results': results,
            'total_results': len(results),
            'source': 'live' if used_live else 'local',
            'used_live_assist': used_live
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/search_with_rag', methods=['POST'])
def search_with_rag():
    try:
        data = request.get_json()
        query = data.get('query', '')
        max_results = data.get('max_results', 10)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        
        search_results = bm25_ranker.search_and_rank(query, max_results=max_results)
        
        used_live = False
        if len(search_results) == 0:
            print(f"⚠️ No local results found for query: '{query}'")
            search_results = _fetch_live_results(query, max_results=max_results)
            used_live = True
        
        rag_result = rag_integration.generate_answer(query, search_results)
        
        response = {
            'query': query,
            'generated_answer': rag_result.get('answer', ''),
            'citations': rag_result.get('citations', []),
            'search_results': search_results,
            'source': 'live' if used_live else 'local',
            'used_live_assist': used_live,
            'rag_success': rag_result.get('success', False),
            'total_contexts_used': rag_result.get('retrieved_count', 0)
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download', methods=['POST'])
def download_data():

    try:
        data = request.get_json()
        tags = data.get('tags', ['spring-boot', 'react', 'django', 'node.js', 'flutter'])
        max_pages = data.get('max_pages', 5)
        

        stackoverflow_downloader.download_and_store(db, tags, max_pages_per_tag=max_pages)
        

        print("Building index...")
        _build_index()
        
        question_count = db.get_question_count()
        
        return jsonify({
            'success': True,
            'message': f'Downloaded and indexed data for tags: {tags}',
            'total_questions': question_count
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    try:
        total_questions = db.get_question_count()
        total_docs = db.get_total_docs()
        avg_doc_length = db.get_avg_doc_length()
        
        return jsonify({
            'total_questions': total_questions,
            'total_documents': total_docs,
            'avg_document_length': avg_doc_length
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _build_index():
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
        tags = json.loads(q_dict.get('tags', '[]'))
        
        indexer.index_question(question_id, title, body, tags)
        
        answers = db.get_answers(question_id)
        for answer in answers:
            answer_id = answer['answer_id']
            answer_body = answer['body']
            indexer.index_answer(answer_id, question_id, answer_body)
        
        if (i + 1) % 100 == 0:
            print(f"  Indexed {i + 1} questions...")
    
    print("Indexing complete!")
    
    bm25_ranker.clear_cache()


def _fetch_live_results(query: str, max_results: int = 5) -> List[Dict]:
    """Fetch live results from Stack Overflow API when local search fails"""
    try:
        print(f"No local results found. Fetching live data from Stack Overflow API...")
        
        params = {
            'site': 'stackoverflow',
            'order': 'desc',
            'sort': 'relevance',
            'q': query,
            'filter': '!9_bDDxJY5',
            'pagesize': max_results
        }
        
        if STACK_API_KEY:
            params['key'] = STACK_API_KEY
        
        response = requests.get(
            "https://api.stackexchange.com/2.3/search/advanced",
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            
            results = []
            for item in items:
                result = {
                    'question_id': item.get('question_id'),
                    'title': item.get('title', ''),
                    'body': item.get('body', ''),
                    'link': item.get('link', ''),
                    'score': item.get('score', 0),
                    'tags': json.dumps(item.get('tags', [])),
                    'bm25_score': 0.0,
                    'answers': [],
                    'source': 'live'
                }
                results.append(result)
                
                _cache_live_result(item)
            
            print(f"✓ Fetched {len(results)} live results from Stack Overflow")
            return results
        else:
            print(f"Stack Overflow API returned status: {response.status_code}")
            return []
    
    except Exception as e:
        print(f"Error fetching live results: {e}")
        return []


def _cache_live_result(item: Dict):
    try:
        question_data = {
            'question_id': item.get('question_id'),
            'title': item.get('title', ''),
            'body': item.get('body', ''),
            'tags': item.get('tags', []),
            'score': item.get('score', 0),
            'view_count': item.get('view_count', 0),
            'answer_count': item.get('answer_count', 0),
            'creation_date': item.get('creation_date', 0),
            'link': item.get('link', ''),
            'is_answered': item.get('is_answered', False)
        }
        
        db.insert_question(question_data)
        
        indexer.index_question(
            question_data['question_id'],
            question_data['title'],
            question_data['body'],
            question_data['tags']
        )
        
        print(f"✓ Cached question {question_data['question_id']} to local database")
    
    except Exception as e:
        print(f"Warning: Could not cache result: {e}")


@app.route('/', methods=['GET'])
def index():
    docs = {
        'name': 'SwaRAG - Stack Overflow RAG System',
        'version': '2.1.0',
        'description': 'RAG system with Inverted Index + BM25 Ranking + Live Assist Fallback',
        'algorithms': ['Inverted Index', 'Query Optimization', 'BM25 Ranking', 'RAG Integration', 'Live Assist (Fallback)'],
        'features': [
            'Local search with BM25 ranking',
            'Automatic fallback to Stack Overflow API when no local results',
            'Live results are cached for future queries',
            'AI-powered answer generation with RAG'
        ],
        'endpoints': {
            '/health': {
                'method': 'GET',
                'description': 'Health check and status'
            },
            '/search': {
                'method': 'POST',
                'description': 'Search using Inverted Index + BM25 (returns ranked results)',
                'body': {
                    'query': 'Your question here',
                    'max_results': 10
                }
            },
            '/search_with_rag': {
                'method': 'POST',
                'description': 'Search with RAG (returns AI-generated answer + ranked results)',
                'body': {
                    'query': 'Your question here',
                    'max_results': 10
                }
            },
            '/download': {
                'method': 'POST',
                'description': 'Download Stack Overflow data and build inverted index',
                'body': {
                    'tags': ['spring-boot', 'react', 'django', 'node.js', 'flutter'],
                    'max_pages': 5
                }
            },
            '/stats': {
                'method': 'GET',
                'description': 'Get database and index statistics'
            }
        }
    }
    
    return jsonify(docs)


if __name__ == '__main__':
    print("Endpoints available at http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)