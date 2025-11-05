from typing import List, Dict, Set, Tuple
from collections import defaultdict, Counter
import math
from data.database import Database
from processing.text_processing import TextProcessor


class Indexer:

    
    def __init__(self, db: Database, text_processor: TextProcessor):
        self.db = db
        self.text_processor = text_processor
    
    def index_question(self, question_id: int, title: str, body: str, tags: List[str]):
        full_text = f"{title} {title} {body}"
        

        tokens_with_positions = self.text_processor.process_with_positions(full_text)
        

        term_positions = defaultdict(list)
        for token, position in tokens_with_positions:
            term_positions[token].append(position)
        

        doc_length = len(tokens_with_positions)
        

        for term, positions in term_positions.items():
            frequency = len(positions)
            self.db.insert_index_term(term, question_id, 'question', frequency, positions)
        
        self.db.insert_doc_stats(question_id, 'question', doc_length)
        

        for tag in tags:
            tag_processed = self.text_processor.stem(tag.lower())
            self.db.insert_index_term(tag_processed, question_id, 'question_tag', 1, [0])
    
    def index_answer(self, answer_id: int, question_id: int, body: str):

        

        tokens_with_positions = self.text_processor.process_with_positions(body)
        

        term_positions = defaultdict(list)
        for token, position in tokens_with_positions:
            term_positions[token].append(position)
        

        doc_length = len(tokens_with_positions)


        for term, positions in term_positions.items():
            frequency = len(positions)
            self.db.insert_index_term(term, answer_id, 'answer', frequency, positions)
        
        self.db.insert_doc_stats(answer_id, 'answer', doc_length)
    
    def batch_index_questions_answers(self, questions_data: List[Dict]):

        
        for q_data in questions_data:

            question_id = q_data.get('question_id')
            title = q_data.get('title', '')
            body = q_data.get('body', '')
            tags = q_data.get('tags', [])
            
            self.index_question(question_id, title, body, tags)
            

            answers = q_data.get('answers', [])
            for answer in answers:
                answer_id = answer.get('answer_id')
                answer_body = answer.get('body', '')
                self.index_answer(answer_id, question_id, answer_body)


class QueryProcessor:
    """Simplified Query Processor - Only Query Optimization"""
    
    def __init__(self, db: Database, text_processor: TextProcessor):
        self.db = db
        self.text_processor = text_processor
    
    def process_query(self, query: str) -> List[str]:
        """Process query and return optimized terms"""
        tokens = self.text_processor.process(query)
        return tokens
    
    def optimize_query_terms(self, terms: List[str]) -> List[str]:
        """Optimize query terms by ordering them by frequency (rarest first)"""
        term_frequencies = []
        
        for term in terms:
            postings = self.db.get_postings(term)
            frequency = len(postings)
            term_frequencies.append((term, frequency))
        
        # Sort by frequency (ascending - rarest first for efficient retrieval)
        sorted_terms = sorted(term_frequencies, key=lambda x: x[1])
        
        return [term for term, _ in sorted_terms]

