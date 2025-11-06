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
    """
    Enhanced BM25 Search with:
    - Title boosting (5x weight for title matches)
    - Quality threshold (only shows relevant results)
    - Tag filtering (search within specific framework)
    - Automatic Live Assist fallback if no quality local results
    - Returns 1, 2, or many results based on actual relevance
    """
    try:
        data = request.get_json()
        query = data.get('query', '')
        tag = data.get('tag', None)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        
        if tag:
            print(f"[SEARCH] Query: '{query}' | Tag: '{tag}'")
        else:
            print(f"[SEARCH] Query: '{query}' | Tag: All")
        

        results = bm25_ranker.search_and_rank(query, min_score=20.0, tag=tag)
        

        used_live = False
        if len(results) == 0:
            print(f"[WARNING] No quality local results for: '{query}' - Using Live Assist")
            results = _fetch_live_results(query, tag=tag, max_results=10)
            used_live = True
        else:
            
            results_with_answers = sum(1 for r in results if len(r.get('answers', [])) > 0)
            answer_percentage = (results_with_answers / len(results)) * 100
            
            
            if answer_percentage < 60:
                print(f"[WARNING] Only {results_with_answers}/{len(results)} results have answers ({answer_percentage:.0f}%) - Using Live Assist")
                original_results = results  # Keep local results as final fallback
                results = _fetch_live_results(query, tag=tag, max_results=10)
                used_live = True
                
                
                if len(results) == 0 or sum(1 for r in results if len(r.get('answers', [])) > 0) == 0:
                    if tag:
                        print(f"[FALLBACK] No results with tag, trying WITHOUT tag for broader results...")
                        results = _fetch_live_results(query, tag=None, max_results=10)
                    
                    
                    if len(results) == 0 or sum(1 for r in results if len(r.get('answers', [])) > 0) == 0:
                        simplified_query = _simplify_query(query, None)
                        if simplified_query != query:
                            print(f"[FALLBACK] Trying simplified query: '{simplified_query}'")
                            results = _fetch_live_results(simplified_query, tag=None, max_results=10)
                        
                        
                        if len(results) == 0 or sum(1 for r in results if len(r.get('answers', [])) > 0) == 0:
                            print(f"[FALLBACK] Live Assist exhausted, returning {len(original_results)} local results")
                            results = original_results
                            used_live = False
            else:
                print(f"[SUCCESS] Found {len(results)} quality local result(s) with answers for: '{query}'")
        
        
        all_answers = []
        for result in results:
            for answer in result.get('answers', []):
                all_answers.append({
                    'answer_id': answer.get('answer_id'),
                    'answer_body': answer.get('body', ''),
                    'answer_score': answer.get('score', 0),
                    'is_accepted': answer.get('is_accepted', False),
                    'question_title': result.get('title', ''),
                    'question_link': result.get('link', ''),
                    'bm25_score': result.get('bm25_score', 0)
                })
        
        response = {
            'query': query,
            'answers': all_answers,
            'total_answers': len(all_answers),
            'tag': tag if tag else 'all',
            'source': 'live' if used_live else 'local'
        }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/search_with_rag', methods=['POST'])
def search_with_rag():
    """
    AI-Powered RAG Search - ALWAYS uses LIVE Stack Overflow data
    - Fetches fresh data from Stack Overflow API
    - Analyzes answers using AI (Meta Llama 3 70B)
    - Generates comprehensive answer based on live data
    - Tag filtering for specific frameworks
    """
    try:
        data = request.get_json()
        query = data.get('query', '')
        tag = data.get('tag', None)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        
        if tag:
            print(f"[RAG] Query: '{query}' | Tag: '{tag}' | Source: LIVE ONLY")
        else:
            print(f"[RAG] Query: '{query}' | Tag: All | Source: LIVE ONLY")
        
       
        print(f"[RAG] Fetching LIVE data from Stack Overflow API...")
        search_results = _fetch_live_results(query, tag=tag, max_results=10)
        
        if len(search_results) == 0:
            
            if tag:
                print(f"[RAG] No results with tag, trying broader search...")
                search_results = _fetch_live_results(query, tag=None, max_results=10)
        
        if len(search_results) == 0:
            return jsonify({
                'question': query,
                'rag_response': 'No relevant information found on Stack Overflow for this query. Please try rephrasing your question.'
            })
        
        
        print(f"[RAG] Analyzing {len(search_results)} Stack Overflow answers with AI...")
        rag_result = rag_integration.generate_answer(query, search_results)
        
        
        referenced_links = []
        for i, result in enumerate(search_results[:5], 1):  # Top 5 contexts used
            if result.get('answers') and len(result.get('answers', [])) > 0:
                referenced_links.append({
                    'title': result.get('title', ''),
                    'link': result.get('link', ''),
                    'score': result.get('score', 0)
                })
        
        response = {
            'question': query,
            'rag_response': rag_result.get('answer', 'Unable to generate answer'),
            'references': referenced_links
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


def _simplify_query(query: str, tag: str = None) -> str:
    """Simplify query by removing common words and focusing on key terms"""
    
    stop_words = ['how', 'to', 'the', 'in', 'a', 'an', 'is', 'are', 'can', 'do', 'does', 'what', 'where', 'when', 'why', 'with']
    words = query.lower().split()
    key_words = [w for w in words if w not in stop_words and len(w) > 2]
    
    
    if tag and tag not in ' '.join(key_words):
        key_words.append(tag.replace('-', ' '))
    
    simplified = ' '.join(key_words[:5])  # Limit to 5 key terms
    return simplified if simplified else query


def _fetch_live_results(query: str, tag: str = None, max_results: int = 5) -> List[Dict]:
    
    try:
        print(f"[LIVE ASSIST] Fetching from Stack Overflow API...")
        
        
        search_query = f"{query} [{tag}]" if tag else query
        
        params = {
            'site': 'stackoverflow',
            'order': 'desc',
            'sort': 'relevance',
            'q': search_query,
            'filter': 'withbody',
            'pagesize': max_results,
            'answers': 1  # Only return questions with at least 1 answer
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
            total_answers_fetched = 0
            
            for item in items:
                question_id = item.get('question_id')
                
                
                answers = _fetch_answers_for_question(question_id)
                total_answers_fetched += len(answers)
                
                result = {
                    'question_id': question_id,
                    'title': item.get('title', ''),
                    'body': item.get('body', ''),
                    'link': item.get('link', ''),
                    'score': item.get('score', 0),
                    'tags': json.dumps(item.get('tags', [])),
                    'bm25_score': 0.0,
                    'answers': answers
                }
                results.append(result)
                
                _cache_live_result(item, answers)
            
            print(f"[LIVE ASSIST] Fetched {len(results)} questions with {total_answers_fetched} total answers from Stack Overflow")
            return results
        else:
            print(f"[LIVE ASSIST] Stack Overflow API returned status: {response.status_code}")
            return []
    
    except Exception as e:
        print(f"[LIVE ASSIST] Error: {e}")
        return []


def _fetch_answers_for_question(question_id: int) -> List[Dict]:
    """Fetch answers for a specific question from Stack Overflow API"""
    try:
        import time
        time.sleep(0.2)  
        
        params = {
            'site': 'stackoverflow',
            'order': 'desc',
            'sort': 'votes',
            'filter': 'withbody',
            'pagesize': 3
        }
        
        if STACK_API_KEY:
            params['key'] = STACK_API_KEY
        
        response = requests.get(
            f"https://api.stackexchange.com/2.3/questions/{question_id}/answers",
            params=params,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            
            
            if 'error_id' in data:
                print(f"[LIVE ASSIST] API Error for question {question_id}: {data.get('error_message', 'Unknown error')}")
                return []
            
            items = data.get('items', [])
            
            if not items:
                print(f"[LIVE ASSIST] Question {question_id} has no answers in Stack Overflow")
            
            answers = []
            for item in items:
                answers.append({
                    'answer_id': item.get('answer_id'),
                    'body': item.get('body', ''),
                    'score': item.get('score', 0),
                    'is_accepted': item.get('is_accepted', False)
                })
            
            return answers
        else:
            print(f"[LIVE ASSIST] Failed to fetch answers for question {question_id}: HTTP {response.status_code}")
            if response.status_code == 429:
                print(f"[LIVE ASSIST] RATE LIMITED! Waiting before next request...")
            return []
    
    except Exception as e:
        print(f"[LIVE ASSIST] Exception fetching answers for question {question_id}: {e}")
        return []


def _cache_live_result(item: Dict, answers: List[Dict] = None):
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
        
        
        if answers:
            for answer in answers:
                answer_data = {
                    'answer_id': answer.get('answer_id'),
                    'question_id': question_data['question_id'],
                    'body': answer.get('body', ''),
                    'score': answer.get('score', 0),
                    'is_accepted': answer.get('is_accepted', False),
                    'creation_date': item.get('creation_date', 0)
                }
                db.insert_answer(answer_data)
                indexer.index_answer(
                    answer_data['answer_id'],
                    answer_data['question_id'],
                    answer_data['body']
                )
        
        print(f"[CACHE] Stored question {question_data['question_id']} with {len(answers) if answers else 0} answers")
    
    except Exception as e:
        print(f"Warning: Could not cache result: {e}")


@app.route('/', methods=['GET'])
def index():
    docs = {
        'name': 'SwaRAG - Stack Overflow Search Engine with RAG Integration',
        'version': '3.4.0',
        'developer': 'Sai Sankar Swarna',
        'description': 'Enhanced RAG system with Title Boosting + Strict Quality Filtering + Tag Filter + Live Assist',
        'algorithms': [
            'Inverted Index', 
            'Query Optimization', 
            'BM25 Ranking with Title Boosting (5x)', 
            'Quality Score Threshold', 
            'RAG Integration', 
            'Live Assist (Smart Fallback)'
        ],
        'features': [
            'Smart local search with BM25 + title boosting (5x weight)',
            'STRICT quality threshold filtering (score >= 20.0)',
            'Tag-based filtering (search within specific framework)',
            'Automatic fallback to Stack Overflow API when no quality local results',
            'Live results cached for future queries',
            'AI-powered answer generation with RAG',
            'Returns 1, 2, or many results based on actual relevance (no fixed limits)'
        ],
        'improvements': {
            'v3.4.0': [
                'INCREASED quality threshold from 8.0 to 20.0 for MUCH better results',
                'Added tag filtering (search within spring-boot, react, django, etc.)',
                'Now returns ONLY highly relevant results (no more garbage)',
                'Title matches get 5x higher weight',
                'Smart Live Assist triggers only when local quality is poor'
            ],
            'v3.3.3': [
                'Title matches now get 5x higher weight for better relevance',
                'Quality score threshold prevents irrelevant results',
                'Removed max_results - system shows what is actually relevant',
                'Enhanced logging for transparency'
            ]
        },
        'endpoints': {
            '/health': {
                'method': 'GET',
                'description': 'Health check and status'
            },
            '/search': {
                'method': 'POST',
                'description': 'Enhanced BM25 search with title boosting, quality filtering & tag filtering',
                'body': {
                    'query': 'how to create rest api',
                    'tag': 'spring-boot'
                },
                'note': 'Tag parameter is optional. Returns only relevant results (could be 1, 2, or many). Automatically uses Live Assist if no quality local results.',
                'available_tags': ['spring-boot', 'react', 'django', 'node.js', 'flask']
            },
            '/search_with_rag': {
                'method': 'POST',
                'description': 'AI-powered search with RAG (generates answer using LLM) + tag filtering',
                'body': {
                    'query': 'how to create rest api',
                    'tag': 'spring-boot'
                },
                'note': 'Tag parameter is optional. Uses enhanced search + LLM for answer generation',
                'available_tags': ['spring-boot', 'react', 'django', 'node.js', 'flask']
            },
            '/stats': {
                'method': 'GET',
                'description': 'Database and index statistics'
            }
        }
    }
    
    return jsonify(docs)


if __name__ == '__main__':
    print("Endpoints available at http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)