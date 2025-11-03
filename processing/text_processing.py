import re
import string
from typing import List, Set
from collections import Counter


class TextProcessor:
    
    def __init__(self):
        self.stopwords = self._load_stopwords()
    
    def _load_stopwords(self) -> Set[str]:
        stopwords = {
            'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 
            'any', 'are', 'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 
            'between', 'both', 'but', 'by', 'can', 'cannot', 'could', 'did', 'do', 'does', 
            'doing', 'down', 'during', 'each', 'few', 'for', 'from', 'further', 'had', 'has', 
            'have', 'having', 'he', 'her', 'here', 'hers', 'herself', 'him', 'himself', 'his', 
            'how', 'i', 'if', 'in', 'into', 'is', 'it', 'its', 'itself', 'just', 'me', 'might', 
            'more', 'most', 'must', 'my', 'myself', 'no', 'nor', 'not', 'now', 'of', 'off', 
            'on', 'once', 'only', 'or', 'other', 'our', 'ours', 'ourselves', 'out', 'over', 
            'own', 'same', 'she', 'should', 'so', 'some', 'such', 'than', 'that', 'the', 
            'their', 'theirs', 'them', 'themselves', 'then', 'there', 'these', 'they', 'this', 
            'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'we', 
            'were', 'what', 'when', 'where', 'which', 'while', 'who', 'whom', 'why', 'will', 
            'with', 'would', 'you', 'your', 'yours', 'yourself', 'yourselves'
        }
        return stopwords
    
    def tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        

        text = re.sub(r'<[^>]+>', ' ', text)
        

        text = re.sub(r'```.*?```', ' ', text, flags=re.DOTALL)
        text = re.sub(r'`[^`]+`', ' ', text)
        

        text = text.lower()
        

        text = re.sub(r'[^\w\s\+\#\-]', ' ', text)
        
        # Tokenize
        tokens = text.split()
        
        return tokens
    
    def remove_stopwords(self, tokens: List[str]) -> List[str]:

        return [token for token in tokens if token not in self.stopwords]
    
    def stem(self, word: str) -> str:
        if len(word) < 3:
            return word
        

        if word.endswith('sses'):
            word = word[:-2]
        elif word.endswith('ies'):
            word = word[:-3] + 'i'
        elif word.endswith('ss'):
            pass
        elif word.endswith('s'):
            word = word[:-1]
        

        if word.endswith('eed'):
            if len(word) > 4:
                word = word[:-1]
        elif word.endswith('ed'):
            if len(word) > 3:
                word = word[:-2]
        elif word.endswith('ing'):
            if len(word) > 4:
                word = word[:-3]
        

        if word.endswith('ational'):
            word = word[:-7] + 'ate'
        elif word.endswith('tional'):
            word = word[:-6] + 'tion'
        elif word.endswith('ization'):
            word = word[:-7] + 'ize'
        elif word.endswith('ation'):
            word = word[:-5] + 'ate'
        elif word.endswith('ness'):
            word = word[:-4]
        elif word.endswith('ment'):
            word = word[:-4]
        elif word.endswith('ity'):
            word = word[:-3]
        elif word.endswith('er'):
            if len(word) > 3:
                word = word[:-2]
        elif word.endswith('ly'):
            if len(word) > 3:
                word = word[:-2]
        
        return word
    
    def process(self, text: str, remove_stopwords: bool = True, apply_stemming: bool = True) -> List[str]:
        tokens = self.tokenize(text)
        
        if remove_stopwords:
            tokens = self.remove_stopwords(tokens)
        
        if apply_stemming:
            tokens = [self.stem(token) for token in tokens]
        
        return tokens
    
    def process_with_positions(self, text: str, remove_stopwords: bool = True, 
                               apply_stemming: bool = True) -> List[tuple]:
        raw_tokens = self.tokenize(text)
        
        processed_tokens = []
        for position, token in enumerate(raw_tokens):
            processed_token = token
            
            if remove_stopwords and token in self.stopwords:
                continue
            
            if apply_stemming:
                processed_token = self.stem(token)
            
            processed_tokens.append((processed_token, position))
        
        return processed_tokens
    
    def extract_phrases(self, text: str) -> List[str]:
        phrases = re.findall(r'"([^"]+)"', text)
        return phrases
    
    def create_biwords(self, tokens: List[str]) -> List[str]:

        if len(tokens) < 2:
            return []
        
        biwords = []
        for i in range(len(tokens) - 1):
            biwords.append(f"{tokens[i]}_{tokens[i+1]}")
        
        return biwords
    
    def spell_correct(self, word: str, vocabulary: Set[str]) -> str:
        if word in vocabulary:
            return word
        

        candidates = self._edits1(word)
        valid_candidates = candidates.intersection(vocabulary)
        
        if valid_candidates:

            return sorted(valid_candidates)[0]
        
        return word
    
    def _edits1(self, word: str) -> Set[str]:

        letters = string.ascii_lowercase + string.digits
        splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        deletes = [L + R[1:] for L, R in splits if R]
        transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
        replaces = [L + c + R[1:] for L, R in splits if R for c in letters]
        inserts = [L + c + R for L, R in splits for c in letters]
        return set(deletes + transposes + replaces + inserts)

