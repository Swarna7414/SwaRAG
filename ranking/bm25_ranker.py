import math
from typing import List, Dict, Tuple, Set
from collections import defaultdict
from data.database import Database
from processing.text_processing import TextProcessor


class BM25Ranker:
    
    def __init__(self, db: Database, text_processor: TextProcessor, 
                 k1: float = 1.5, b: float = 0.75):
        self.db = db
        self.text_processor = text_processor
        self.k1 = k1
        self.b = b
        

        self.total_docs = None
        self.avg_doc_length = None
        self.idf_cache = {}
    
    def _get_total_docs(self) -> int:
        if self.total_docs is None:
            self.total_docs = self.db.get_total_docs()
        return self.total_docs
    
    def _get_avg_doc_length(self) -> float:
        if self.avg_doc_length is None:
            self.avg_doc_length = self.db.get_avg_doc_length()
        return self.avg_doc_length
    
    def _calculate_idf(self, term: str) -> float:
        if term in self.idf_cache:
            return self.idf_cache[term]
        
        postings = self.db.get_postings(term)
        df = len(postings)
        
        N = self._get_total_docs()
        
        if df == 0:
            idf = 0.0
        else:
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
        
        self.idf_cache[term] = idf
        return idf
    
    def _calculate_term_score(self, term: str, tf: int, doc_length: int) -> float:
        idf = self._calculate_idf(term)
        avgdl = self._get_avg_doc_length()
        

        numerator = tf * (self.k1 + 1)
        denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / avgdl))
        
        score = idf * (numerator / denominator)
        return score
    
    def score_document(self, query_terms: List[str], doc_id: int, 
                       doc_type: str, title_boost: float = 5.0) -> float:
        score = 0.0
        title_score = 0.0

        doc_length = self.db.get_doc_stats(doc_id, doc_type)
        if doc_length is None:
            doc_length = 1
        
        title_terms = []
        if doc_type == 'question':
            question = self.db.get_question(doc_id)
            if question and question.get('title'):
                title_terms = self.text_processor.process(question['title'])

        for term in query_terms:
            postings = self.db.get_postings(term)
            tf = 0
            
            for p_doc_id, p_doc_type, frequency, _ in postings:
                if p_doc_id == doc_id and p_doc_type == doc_type:
                    tf = frequency
                    break
            
            if tf > 0:
                term_score = self._calculate_term_score(term, tf, doc_length)
                
                if doc_type == 'question' and term in title_terms:
                    title_score += term_score * title_boost
                else:
                    score += term_score
        
        return score + title_score
    
    def rank_documents(self, query_terms: List[str], 
                      candidate_docs: Set[Tuple[int, str]],
                      field_weights: Dict[str, float] = None) -> List[Tuple[int, str, float]]:
        if field_weights is None:
            field_weights = {
                'question': 1.5,
                'answer': 1.0,
                'question_tag': 2.0
            }
        
        scored_docs = []
        
        for doc_id, doc_type in candidate_docs:
            base_score = self.score_document(query_terms, doc_id, doc_type)
            

            weight = field_weights.get(doc_type, 1.0)
            final_score = base_score * weight
            
            scored_docs.append((doc_id, doc_type, final_score))
        
        
        scored_docs.sort(key=lambda x: x[2], reverse=True)
        
        return scored_docs
    
    def search_and_rank(self, query: str, min_score: float = 20.0, tag: str = None) -> List[Dict]:
        
        query_terms = self.text_processor.process(query)
        
        if not query_terms:
            return []
        
        candidate_docs = set()
        
        for term in query_terms:
            postings = self.db.get_postings(term)
            for doc_id, doc_type, _, _ in postings:
                candidate_docs.add((doc_id, doc_type))
        
        if not candidate_docs:
            return []
        
        ranked_docs = self.rank_documents(query_terms, candidate_docs)
        
        results = self._collect_results(ranked_docs, min_score, tag)
        
        return results
    
    def _collect_results(self, ranked_docs: List[Tuple[int, str, float]], 
                        min_score: float, tag: str = None, max_results: int = 5) -> List[Dict]:
        question_scores = {}
        answer_scores = {}
        
        for doc_id, doc_type, score in ranked_docs:
            if doc_type == 'question':
                if doc_id not in question_scores:
                    question_scores[doc_id] = score
                else:
                    question_scores[doc_id] = max(question_scores[doc_id], score)
            
            elif doc_type == 'answer':
                answers = self.db.get_answers(doc_id)
                pass

        sorted_questions = sorted(question_scores.items(), 
                                 key=lambda x: x[1], reverse=True)
        
        results = []
        
        for question_id, score in sorted_questions:
            if len(results) >= max_results:
                break
                
            if score < min_score:
                break
                
            question = self.db.get_question(question_id)
            
            if question:
                if tag:
                    question_tags = question.get('tags', '').lower()
                    if tag.lower() not in question_tags:
                        continue
                
                answers = self.db.get_answers(question_id)
                
                result = {
                    'question_id': question_id,
                    'title': question.get('title', ''),
                    'body': question.get('body', ''),
                    'link': question.get('link', ''),
                    'score': question.get('score', 0),
                    'tags': question.get('tags', ''),
                    'bm25_score': score,
                    'answers': []
                }

                for answer in answers[:3]:
                    result['answers'].append({
                        'answer_id': answer.get('answer_id'),
                        'body': answer.get('body', ''),
                        'score': answer.get('score', 0),
                        'is_accepted': answer.get('is_accepted', False)
                    })
                
                results.append(result)
        
        return results
    
    def clear_cache(self):

        self.total_docs = None
        self.avg_doc_length = None
        self.idf_cache = {}