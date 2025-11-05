import sqlite3
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class Database:

    
    def __init__(self, db_path: str = "stackoverflow.db"):
        self.db_path = db_path
        self.conn = None
        self.initialize_database()
    
    def get_connection(self):

        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def initialize_database(self):

        conn = self.get_connection()
        cursor = conn.cursor()
        

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                question_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                tags TEXT,
                score INTEGER DEFAULT 0,
                view_count INTEGER DEFAULT 0,
                answer_count INTEGER DEFAULT 0,
                creation_date INTEGER,
                link TEXT,
                is_answered BOOLEAN DEFAULT 0
            )
        """)
        

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS answers (
                answer_id INTEGER PRIMARY KEY,
                question_id INTEGER,
                body TEXT NOT NULL,
                score INTEGER DEFAULT 0,
                is_accepted BOOLEAN DEFAULT 0,
                creation_date INTEGER,
                FOREIGN KEY (question_id) REFERENCES questions(question_id)
            )
        """)
        

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inverted_index (
                term TEXT NOT NULL,
                doc_id INTEGER NOT NULL,
                doc_type TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                positions TEXT,
                PRIMARY KEY (term, doc_id, doc_type)
            )
        """)
        

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doc_stats (
                doc_id INTEGER NOT NULL,
                doc_type TEXT NOT NULL,
                doc_length INTEGER DEFAULT 0,
                PRIMARY KEY (doc_id, doc_type)
            )
        """)
        

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inverted_term ON inverted_index(term)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_answers_question ON answers(question_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_tags ON questions(tags)")
        
        conn.commit()
    
    def insert_question(self, question_data: Dict) -> bool:

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO questions 
                (question_id, title, body, tags, score, view_count, answer_count, 
                 creation_date, link, is_answered)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                question_data.get('question_id'),
                question_data.get('title', ''),
                question_data.get('body', ''),
                json.dumps(question_data.get('tags', [])),
                question_data.get('score', 0),
                question_data.get('view_count', 0),
                question_data.get('answer_count', 0),
                question_data.get('creation_date', 0),
                question_data.get('link', ''),
                question_data.get('is_answered', False)
            ))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting question: {e}")
            return False
    
    def insert_answer(self, answer_data: Dict) -> bool:

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO answers 
                (answer_id, question_id, body, score, is_accepted, creation_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                answer_data.get('answer_id'),
                answer_data.get('question_id'),
                answer_data.get('body', ''),
                answer_data.get('score', 0),
                answer_data.get('is_accepted', False),
                answer_data.get('creation_date', 0)
            ))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error inserting answer: {e}")
            return False
    
    def insert_index_term(self, term: str, doc_id: int, doc_type: str, 
                         frequency: int, positions: List[int]):

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO inverted_index 
                (term, doc_id, doc_type, frequency, positions)
                VALUES (?, ?, ?, ?, ?)
            """, (term, doc_id, doc_type, frequency, json.dumps(positions)))
            
            conn.commit()
        except Exception as e:
            print(f"Error inserting index term: {e}")
    
    def insert_biword(self, biword: str, doc_id: int, doc_type: str, 
                     frequency: int, positions: List[int]):

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO biword_index 
                (biword, doc_id, doc_type, frequency, positions)
                VALUES (?, ?, ?, ?, ?)
            """, (biword, doc_id, doc_type, frequency, json.dumps(positions)))
            
            conn.commit()
        except Exception as e:
            print(f"Error inserting biword: {e}")
    
    def insert_doc_stats(self, doc_id: int, doc_type: str, doc_length: int):

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO doc_stats 
                (doc_id, doc_type, doc_length)
                VALUES (?, ?, ?)
            """, (doc_id, doc_type, doc_length))
            
            conn.commit()
        except Exception as e:
            print(f"Error inserting doc stats: {e}")
    
    def get_postings(self, term: str) -> List[Tuple[int, str, int, List[int]]]:

        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT doc_id, doc_type, frequency, positions
            FROM inverted_index
            WHERE term = ?
        """, (term,))
        
        results = []
        for row in cursor.fetchall():
            positions = json.loads(row[3]) if row[3] else []
            results.append((row[0], row[1], row[2], positions))
        
        return results
    
    def get_biword_postings(self, biword: str) -> List[Tuple[int, str, int, List[int]]]:

        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT doc_id, doc_type, frequency, positions
            FROM biword_index
            WHERE biword = ?
        """, (biword,))
        
        results = []
        for row in cursor.fetchall():
            positions = json.loads(row[3]) if row[3] else []
            results.append((row[0], row[1], row[2], positions))
        
        return results
    
    def get_question(self, question_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM questions WHERE question_id = ?
        """, (question_id,))
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def get_answers(self, question_id: int) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM answers 
            WHERE question_id = ? 
            ORDER BY is_accepted DESC, score DESC
        """, (question_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_doc_stats(self, doc_id: int, doc_type: str) -> Optional[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT doc_length FROM doc_stats 
            WHERE doc_id = ? AND doc_type = ?
        """, (doc_id, doc_type))
        
        row = cursor.fetchone()
        return row[0] if row else None
    
    def get_total_docs(self) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM doc_stats")
        return cursor.fetchone()[0]
    
    def get_avg_doc_length(self) -> float:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT AVG(doc_length) FROM doc_stats")
        result = cursor.fetchone()[0]
        return result if result else 0.0
    
    def get_question_count(self) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM questions")
        return cursor.fetchone()[0]
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

