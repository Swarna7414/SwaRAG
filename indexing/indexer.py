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
        

        tokens = [token for token, _ in tokens_with_positions]
        biwords = self.text_processor.create_biwords(tokens)
        
        biword_positions = defaultdict(list)
        for i, biword in enumerate(biwords):
            biword_positions[biword].append(i)
        
        for biword, positions in biword_positions.items():
            frequency = len(positions)
            self.db.insert_biword(biword, question_id, 'question', frequency, positions)
        

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
        

        tokens = [token for token, _ in tokens_with_positions]
        biwords = self.text_processor.create_biwords(tokens)
        
        biword_positions = defaultdict(list)
        for i, biword in enumerate(biwords):
            biword_positions[biword].append(i)
        
        for biword, positions in biword_positions.items():
            frequency = len(positions)
            self.db.insert_biword(biword, answer_id, 'answer', frequency, positions)
        

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

    
    def __init__(self, db: Database, text_processor: TextProcessor):
        self.db = db
        self.text_processor = text_processor
    
    def process_query(self, query: str) -> Dict:
        result = {
            'original': query,
            'terms': [],
            'phrases': [],
            'biwords': []
        }
        

        phrases = self.text_processor.extract_phrases(query)
        result['phrases'] = phrases
        

        query_without_phrases = query
        for phrase in phrases:
            query_without_phrases = query_without_phrases.replace(f'"{phrase}"', '')
        

        tokens = self.text_processor.process(query_without_phrases)
        result['terms'] = tokens
        

        biwords = self.text_processor.create_biwords(tokens)
        result['biwords'] = biwords
        
        return result
    
    def optimize_query_terms(self, terms: List[str]) -> List[str]:
        term_frequencies = []
        
        for term in terms:
            postings = self.db.get_postings(term)
            frequency = len(postings)
            term_frequencies.append((term, frequency))
        

        sorted_terms = sorted(term_frequencies, key=lambda x: x[1])
        
        return [term for term, _ in sorted_terms]
    
    def boolean_retrieval(self, terms: List[str]) -> Set[Tuple[int, str]]:
        if not terms:
            return set()
        

        optimized_terms = self.optimize_query_terms(terms)
        

        postings_lists = []
        for term in optimized_terms:
            postings = self.db.get_postings(term)
            doc_set = {(doc_id, doc_type) for doc_id, doc_type, _, _ in postings}
            postings_lists.append(doc_set)
        
        if not postings_lists:
            return set()
        

        result = postings_lists[0]
        for postings in postings_lists[1:]:
            result = result.intersection(postings)
        
        return result
    
    def phrase_search(self, phrase: str) -> Set[Tuple[int, str]]:
        tokens = self.text_processor.process(phrase)
        
        if len(tokens) < 2:
            if tokens:
                postings = self.db.get_postings(tokens[0])
                return {(doc_id, doc_type) for doc_id, doc_type, _, _ in postings}
            return set()
        

        first_term_postings = self.db.get_postings(tokens[0])
        
        matching_docs = set()
        
        for doc_id, doc_type, _, positions in first_term_postings:

            if self._check_phrase_match(tokens, doc_id, doc_type, positions):
                matching_docs.add((doc_id, doc_type))
        
        return matching_docs
    
    def _check_phrase_match(self, tokens: List[str], doc_id: int, 
                           doc_type: str, first_positions: List[int]) -> bool:

        
        for start_pos in first_positions:
            match = True
            

            for i, token in enumerate(tokens[1:], 1):
                expected_pos = start_pos + i
                

                postings = self.db.get_postings(token)
                

                doc_positions = None
                for p_doc_id, p_doc_type, _, p_positions in postings:
                    if p_doc_id == doc_id and p_doc_type == doc_type:
                        doc_positions = p_positions
                        break
                
                if doc_positions is None or expected_pos not in doc_positions:
                    match = False
                    break
            
            if match:
                return True
        
        return False
    
    def biword_search(self, terms: List[str]) -> Set[Tuple[int, str]]:
        biwords = self.text_processor.create_biwords(terms)
        
        if not biwords:
            return set()
        

        all_docs = None
        
        for biword in biwords:
            postings = self.db.get_biword_postings(biword)
            doc_set = {(doc_id, doc_type) for doc_id, doc_type, _, _ in postings}
            
            if all_docs is None:
                all_docs = doc_set
            else:
                all_docs = all_docs.intersection(doc_set)
        
        return all_docs if all_docs else set()

