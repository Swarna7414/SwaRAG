from flask import Flask, request, jsonify
from flask_cors import CORS
from typing import Dict, List
import json
import os

from data.database import Database
from processing.text_processing import TextProcessor
from indexing.indexer import Indexer, QueryProcessor
from ranking.bm25_ranker import BM25Ranker
from rag.rag_integration import RAGIntegration, LiveAssist
from data.stackoverflow_downloader import StackOverflowDownloader



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
live_assist = LiveAssist(STACK_API_KEY)
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
        use_live_assist = data.get('use_live_assist', True)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        

        local_results = bm25_ranker.search_and_rank(query, max_results=max_results)
        

        should_use_live = (
            use_live_assist and 
            live_assist.should_use_live_assist(local_results)
        )
        
        live_results = []
        if should_use_live:
            live_results = live_assist.fetch_live_results(query, max_results=5)
            

            for result in live_results:
                _cache_live_result(result)
        

        response = {
            'query': query,
            'local_results': local_results,
            'live_results': live_results,
            'used_live_assist': should_use_live,
            'total_local': len(local_results),
            'total_live': len(live_results)
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
        use_live_assist = data.get('use_live_assist', True)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        

        local_results = bm25_ranker.search_and_rank(query, max_results=max_results)
        

        should_use_live = (
            use_live_assist and 
            live_assist.should_use_live_assist(local_results)
        )
        
        live_results = []
        if should_use_live:
            live_results = live_assist.fetch_live_results(query, max_results=5)
            

            for result in live_results:
                _cache_live_result(result)
        

        all_contexts = local_results + live_results
        

        rag_result = rag_integration.generate_answer(query, all_contexts)
        

        response = {
            'query': query,
            'generated_answer': rag_result.get('answer', ''),
            'citations': rag_result.get('citations', []),
            'local_results': local_results,
            'live_results': live_results,
            'used_live_assist': should_use_live,
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
        tags = data.get('tags', ['spring-boot', 'react', 'django', 'node.js'])
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


@app.route('/query_optimize', methods=['POST'])
def query_optimize():
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        

        processed_query = query_processor.process_query(query)
        

        optimized_terms = query_processor.optimize_query_terms(processed_query['terms'])
        

        retrieved_docs = query_processor.boolean_retrieval(optimized_terms)
        
        response = {
            'original_query': query,
            'processed_terms': processed_query['terms'],
            'optimized_terms': optimized_terms,
            'phrases': processed_query['phrases'],
            'biwords': processed_query['biwords'],
            'retrieved_docs_count': len(retrieved_docs)
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/phrase_search', methods=['POST'])
def phrase_search():

    try:
        data = request.get_json()
        phrase = data.get('phrase', '')
        
        if not phrase:
            return jsonify({'error': 'Phrase is required'}), 400
        

        matching_docs = query_processor.phrase_search(phrase)
        

        results = []
        for doc_id, doc_type in matching_docs:
            if doc_type == 'question':
                question = db.get_question(doc_id)
                if question:
                    results.append({
                        'question_id': doc_id,
                        'title': question.get('title', ''),
                        'link': question.get('link', ''),
                        'score': question.get('score', 0)
                    })
        
        response = {
            'phrase': phrase,
            'matches': results,
            'total_matches': len(results)
        }
        
        return jsonify(response)
    
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


def _cache_live_result(result: Dict):

    try:

        question_data = {
            'question_id': result.get('question_id'),
            'title': result.get('title', ''),
            'body': result.get('body', ''),
            'tags': result.get('tags', []),
            'score': result.get('score', 0),
            'view_count': result.get('view_count', 0),
            'answer_count': result.get('answer_count', 0),
            'creation_date': 0,
            'link': result.get('link', ''),
            'is_answered': result.get('is_answered', False)
        }
        
        db.insert_question(question_data)
        

        indexer.index_question(
            question_data['question_id'],
            question_data['title'],
            question_data['body'],
            question_data['tags']
        )
        
        print(f"Cached live result: {question_data['question_id']}")
    
    except Exception as e:
        print(f"Error caching live result: {e}")


@app.route('/', methods=['GET'])
def index():
    docs = {
        'name': 'SwaRAG - Stack Overflow RAG System',
        'version': '1.0.0',
        'endpoints': {
            '/health': {
                'method': 'GET',
                'description': 'Health check and status'
            },
            '/search': {
                'method': 'POST',
                'description': 'Search without RAG (returns ranked results only)',
                'body': {
                    'query': 'Your question here',
                    'max_results': 10,
                    'use_live_assist': True
                }
            },
            '/search_with_rag': {
                'method': 'POST',
                'description': 'Search with RAG (returns generated answer + ranked results)',
                'body': {
                    'query': 'Your question here',
                    'max_results': 10,
                    'use_live_assist': True
                }
            },
            '/download': {
                'method': 'POST',
                'description': 'Download Stack Overflow data and build index',
                'body': {
                    'tags': ['spring-boot', 'react', 'django', 'node.js'],
                    'max_pages': 5
                }
            },
            '/query_optimize': {
                'method': 'POST',
                'description': 'Test query optimization algorithms',
                'body': {
                    'query': 'Your query here'
                }
            },
            '/phrase_search': {
                'method': 'POST',
                'description': 'Search for exact phrases using positional index',
                'body': {
                    'phrase': 'Your phrase here'
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
    print("Starting SwaRAG API Server...")
    print(f"API Key configured: {STACK_API_KEY[:10]}...")
    print(f"Client ID: {CLIENT_ID}")
    print(f"Database: {DB_PATH}")
    print("\nEndpoints available at http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)