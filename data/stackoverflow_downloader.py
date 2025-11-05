import requests
import time
import json
from typing import List, Dict, Optional
from datetime import datetime
from .database import Database


class StackOverflowDownloader:
    def __init__(self, api_key: str = None, client_id: str = None):
        self.api_key = api_key
        self.client_id = client_id
        self.base_url = "https://api.stackexchange.com/2.3"
        self.rate_limit_remaining = 10000
        self.backoff_time = 0
    
    def _make_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
        params['site'] = 'stackoverflow'
        if self.api_key:
            params['key'] = self.api_key

        if self.backoff_time > 0:
            time.sleep(self.backoff_time)
            self.backoff_time = 0
        
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, params=params, timeout=30)

            self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
            
            if response.status_code == 200:
                data = response.json()

                if 'backoff' in data:
                    self.backoff_time = data['backoff']
                    print(f"API backoff requested: {self.backoff_time} seconds")
                
                return data
            
            elif response.status_code == 429:
                print("Rate limit exceeded. Waiting 60 seconds...")
                time.sleep(60)
                return self._make_request(endpoint, params)
            
            else:
                print(f"API request failed with status {response.status_code}")
                return None
        
        except Exception as e:
            print(f"Error making API request: {e}")
            return None
    
    def download_questions_by_tags(self, tags: List[str], max_pages: int = 10, 
                                   pagesize: int = 100, max_questions_per_tag: int = None) -> List[Dict]:
        questions = []
        
        for tag in tags:
            print(f"Downloading questions for tag: {tag}")
            tag_questions = []
            
            for page in range(1, max_pages + 1):
                if max_questions_per_tag and len(tag_questions) >= max_questions_per_tag:
                    print(f"  Reached limit of {max_questions_per_tag} questions for {tag}")
                    break
                
                params = {
                    'page': page,
                    'pagesize': pagesize,
                    'order': 'desc',
                    'sort': 'creation',
                    'tagged': tag,
                    'site': 'stackoverflow',
                    'filter': 'withbody',
                    'min': 1
                }
                
                data = self._make_request('questions', params)
                
                if not data or 'items' not in data:
                    break
                
                items = data['items']
                
                answered_items = [q for q in items if q.get('answer_count', 0) > 0]
                
                if max_questions_per_tag:
                    remaining = max_questions_per_tag - len(tag_questions)
                    answered_items = answered_items[:remaining]
                
                print(f"  Page {page}: Retrieved {len(items)} questions ({len(answered_items)} answered)")
                
                tag_questions.extend(answered_items)

                if not data.get('has_more', False) or (max_questions_per_tag and len(tag_questions) >= max_questions_per_tag):
                    break

                time.sleep(0.5)
            
            questions.extend(tag_questions)
        
        print(f"Total questions downloaded: {len(questions)}")
        return questions
    
    def download_answers_for_questions(self, question_ids: List[int], 
                                      batch_size: int = 100) -> Dict[int, List[Dict]]:

        answers_by_question = {}
        

        for i in range(0, len(question_ids), batch_size):
            batch = question_ids[i:i + batch_size]
            question_ids_str = ';'.join(map(str, batch))
            
            print(f"Downloading answers for questions {i+1} to {i+len(batch)}")
            
            params = {
                'order': 'desc',
                'sort': 'votes',
                'filter': 'withbody',
                'site': 'stackoverflow'
            }
            
            data = self._make_request(f'questions/{question_ids_str}/answers', params)
            
            if not data or 'items' not in data:
                continue
            

            for answer in data['items']:
                q_id = answer.get('question_id')
                if q_id not in answers_by_question:
                    answers_by_question[q_id] = []
                answers_by_question[q_id].append(answer)
            

            time.sleep(0.5)
        
        print(f"Downloaded answers for {len(answers_by_question)} questions")
        return answers_by_question
    
    def search_questions(self, query: str, max_results: int = 50) -> List[Dict]:
        results = []
        pagesize = min(max_results, 100)
        
        params = {
            'page': 1,
            'pagesize': pagesize,
            'order': 'desc',
            'sort': 'relevance',
            'q': query,
            'site': 'stackoverflow',
            'filter': 'withbody'
        }
        
        data = self._make_request('search/advanced', params)
        
        if data and 'items' in data:
            all_items = data['items']
            results = [q for q in all_items if q.get('answer_count', 0) > 0]
            print(f"Live search found {len(results)} answered results (from {len(all_items)} total)")
        
        return results
    
    def download_and_store(self, db: Database, tags: List[str], 
                          max_pages_per_tag: int = 10, max_questions_per_tag: int = None):
        print("Starting Stack Overflow data download...")
        print(f"Tags: {tags}")
        print(f"Max pages per tag: {max_pages_per_tag}")
        if max_questions_per_tag:
            print(f"Max questions per tag: {max_questions_per_tag}")
        
        questions = self.download_questions_by_tags(tags, max_pages=max_pages_per_tag, 
                                                    max_questions_per_tag=max_questions_per_tag)
        
        if not questions:
            print("No questions downloaded")
            return

        question_ids = [q['question_id'] for q in questions]
        

        answers_by_question = self.download_answers_for_questions(question_ids)
        

        print("Storing data in database...")
        
        stored_questions = 0
        stored_answers = 0
        skipped_questions = 0
        
        for question in questions:
            q_id = question['question_id']

            if q_id not in answers_by_question or len(answers_by_question[q_id]) == 0:
                skipped_questions += 1
                continue
            
            question_data = {
                'question_id': q_id,
                'title': question.get('title', ''),
                'body': question.get('body', ''),
                'tags': question.get('tags', []),
                'score': question.get('score', 0),
                'view_count': question.get('view_count', 0),
                'answer_count': question.get('answer_count', 0),
                'creation_date': question.get('creation_date', 0),
                'link': question.get('link', ''),
                'is_answered': question.get('is_answered', False)
            }
            
            db.insert_question(question_data)
            stored_questions += 1
        
            for answer in answers_by_question[q_id]:
                answer_data = {
                    'answer_id': answer['answer_id'],
                    'question_id': q_id,
                    'body': answer.get('body', ''),
                    'score': answer.get('score', 0),
                    'is_accepted': answer.get('is_accepted', False),
                    'creation_date': answer.get('creation_date', 0)
                }
                db.insert_answer(answer_data)
                stored_answers += 1
        
        print(f"Successfully stored {stored_questions} questions with {stored_answers} answers")
        print(f"⏭Skipped {skipped_questions} questions (no downloadable answers)")
        print(f"Rate limit remaining: {self.rate_limit_remaining}")

