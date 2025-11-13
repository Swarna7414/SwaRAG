import requests
import json
import re
import time
from typing import List, Dict, Optional
from html.parser import HTMLParser


class RAGIntegration:

    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_base = "https://api.replicate.com/v1"
        self.headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json"
        }
    
    def generate_answer(self, query: str, retrieved_contexts: List[Dict],
                       max_length: int = 500) -> Dict:


        context_text = self._format_contexts(retrieved_contexts)
        

        prompt = self._create_prompt(query, context_text)
        

        try:
            answer = self._call_llm(prompt, max_length)
            

            citations = self._extract_citations(retrieved_contexts)
            
            result = {
                'answer': answer,
                'citations': citations,
                'retrieved_count': len(retrieved_contexts),
                'success': True
            }
            
            return result
        
        except Exception as e:
            print(f"Error generating answer: {e}")
            return {
                'answer': 'Unable to generate answer. Please refer to the retrieved results.',
                'citations': [],
                'retrieved_count': len(retrieved_contexts),
                'success': False,
                'error': str(e)
            }
    
    def _format_contexts(self, contexts: List[Dict]) -> str:
        formatted = []
        
        for i, ctx in enumerate(contexts[:6], 1):  
            question_title = ctx.get('title', 'Unknown')
            question_body = ctx.get('body', '')[:500]  
            
            answers = ctx.get('answers', [])
            
            best_answer = None
            if answers:
                sorted_answers = sorted(answers, key=lambda x: (not x.get('is_accepted', False), -x.get('score', 0)))
                best_answer = sorted_answers[0]
            
            answer_text = ""
            if best_answer:
                answer_body = best_answer.get('body', '')       
                answer_text = answer_body[:2000]
            
            formatted.append(
                f"[Context {i}]\n"
                f"Question: {question_title}\n"
                f"Question Details: {question_body}\n"
                f"Best Answer: {answer_text}\n"
                f"Score: {ctx.get('score', 0)}\n"
                f"Link: {ctx.get('link', '')}\n"
            )
        
        return "\n\n".join(formatted)
    
    def _create_prompt(self, query: str, context_text: str) -> str:
        prompt = f"""You are an expert programming assistant. Analyze the following Stack Overflow questions and answers to provide a comprehensive, well-structured answer to the user's question.

User Question: {query}

Stack Overflow Contexts:
{context_text}

Instructions:
1. Synthesize information from multiple contexts to provide a complete answer
2. Focus on the most relevant information that directly answers the question
3. Structure your answer with clear sections if needed
4. Include code examples from the contexts when relevant (preserve code formatting)
5. Explain concepts clearly and provide actionable steps
6. Only use information from the provided contexts - don't make up information
7. If the contexts don't fully answer the question, acknowledge this but provide what you can

Provide a comprehensive answer:"""
        
        return prompt
    
    def _call_llm(self, prompt: str, max_length: int = 500) -> str:

        try:
            return self._generate_smart_answer(prompt)
        
        except Exception as e:
            print(f"Error generating answer: {e}")
            return self._fallback_answer(prompt)
    
    def _poll_prediction(self, prediction_id: str, max_attempts: int = 30) -> str:
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(
                    f"{self.api_base}/predictions/{prediction_id}",
                    headers=self.headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    prediction = response.json()
                    status = prediction.get('status')
                    
                    if status == 'succeeded':
                        output = prediction.get('output', [])
                        if isinstance(output, list):
                            return ''.join(output)
                        return str(output)
                    
                    elif status == 'failed':
                        return "Generation failed"
                
                time.sleep(2)
            
            except Exception as e:
                print(f"Error polling prediction: {e}")
                break
        
        return "Generation timed out"
    
    def _generate_smart_answer(self, prompt: str) -> str:
        
        class HTMLStripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []
                self.in_code = False
            def handle_data(self, data):
                if not self.in_code:
                    self.text.append(data)
            def handle_starttag(self, tag, attrs):
                if tag in ['code', 'pre']:
                    self.in_code = True
            def handle_endtag(self, tag):
                if tag in ['code', 'pre']:
                    self.in_code = False
                    self.text.append('\n')
            def get_text(self):
                return ''.join(self.text)
        
        def strip_html_preserve_structure(html):
            if not html:
                return ""
            
            code_blocks = []
            code_pattern = r'<code[^>]*>(.*?)</code>'
            for i, match in enumerate(re.finditer(code_pattern, html, re.DOTALL)):
                code_blocks.append(match.group(1))
                html = html.replace(match.group(0), f'__CODE_BLOCK_{i}__')
            
            html = re.sub(r'</p>', '\n\n', html)
            html = re.sub(r'<p[^>]*>', '', html)
            
            html = re.sub(r'<li[^>]*>', '• ', html)
            html = re.sub(r'</li>', '\n', html)
            
            stripper = HTMLStripper()
            try:
                stripper.feed(html)
                text = stripper.get_text()
            except:
                text = html
            
            text = re.sub(r'<[^>]+>', '', text)
            
            for i, code in enumerate(code_blocks):
                text = text.replace(f'__CODE_BLOCK_{i}__', code)
            
            text = re.sub(r'[ \t]+', ' ', text)  
            text = re.sub(r'\n{3,}', '\n\n', text)  
            return text.strip()
        
        query = prompt.split("User Question:")[1].split("Stack Overflow Contexts:")[0].strip()
        
        contexts_section = prompt.split("Stack Overflow Contexts:")[1].split("Instructions:")[0]
        context_blocks = contexts_section.split("[Context ")
        
        all_answers = []
        code_examples = []
        key_concepts = []
        step_by_step = []
        
        for block in context_blocks[1:]:
            if "Best Answer:" in block:
                question_match = re.search(r'Question:\s*(.+?)\n', block)
                question_title = question_match.group(1).strip() if question_match else ""
                
                answer_match = re.search(r'Best Answer:\s*(.+?)(?:\nScore:|$)', block, re.DOTALL)
                if answer_match:
                    answer_text = answer_match.group(1).strip()
                    
                    answer_clean = strip_html_preserve_structure(answer_text)
                    
                    code_patterns = [
                        r'<code[^>]*>(.*?)</code>',
                        r'```[\w]*\n(.*?)```',
                    ]
                    
                    for pattern in code_patterns:
                        matches = re.findall(pattern, answer_text, re.DOTALL)
                        for match in matches[:3]:  
                            code_clean = match.strip()
                            if code_clean and len(code_clean) > 30 and len(code_clean) < 1500:
                                lines = code_clean.split('\n')
                                if len(lines) >= 2 or any(keyword in code_clean for keyword in ['@', 'class', 'def ', 'function', 'public', 'private', 'import', 'package']):
                                    if code_clean not in code_examples:
                                        code_examples.append(code_clean)
                    
                    paragraphs = [p.strip() for p in answer_clean.split('\n\n') if p.strip()]
                    
                    sentence_endings = r'(?<=[.!?])\s+(?=[A-Z])'
                    all_sentences = []
                    
                    for para in paragraphs:
                        if len(para) < 20 or para.startswith('```'):
                            continue
                        
                        sentences = re.split(sentence_endings, para)
                        for sent in sentences:
                            sent = sent.strip()
                            if (len(sent) > 40 and len(sent) < 500 and 
                                sent.count(' ') >= 5 and  
                                not sent.endswith((' org', ' com', ' http', ' www', ' =', ' gradle', ' maven', ' jar', ' xml')) and
                                not any(skip in sent.lower() for skip in ['click here', 'see this', 'stackoverflow.com'])):
                                all_sentences.append(sent)
                    
                    for sent in all_sentences:
                        sent_lower = sent.lower()
                        action_phrases = ['create', 'add', 'configure', 'implement', 'use', 'define', 'annotate', 'write', 'build', 'set up']
                        if any(phrase in sent_lower for phrase in action_phrases):
                            query_words = [w for w in query.lower().split() if len(w) > 3]
                            if not query_words or any(word in sent_lower for word in query_words):
                                if sent not in step_by_step and len(step_by_step) < 8:
                                    step_by_step.append(sent)
                        elif any(phrase in sent_lower for phrase in ['important', 'note', 'remember', 'key', 'essential', 'required', 'must', 'should']):
                            if sent not in key_concepts and len(key_concepts) < 5:
                                key_concepts.append(sent)
                    
                    all_answers.append({
                        'question': question_title,
                        'answer': answer_clean,  
                        'paragraphs': paragraphs,
                        'sentences': all_sentences
                    })
        
        answer_parts = []
        
        if step_by_step:
            answer_parts.append("**Step-by-Step Approach:**\n")
            for i, step in enumerate(step_by_step[:5], 1):
                step_clean = step.rstrip('.,;:')
                answer_parts.append(f"{i}. {step_clean}.\n")
            answer_parts.append("\n")
        
        if key_concepts:
            answer_parts.append("**Key Concepts:**\n")
            for concept in key_concepts[:3]:
                answer_parts.append(f"• {concept}.\n")
            answer_parts.append("\n")
        
        if code_examples:
            best_code = ""
            for code in code_examples:
                score = len(code.split('\n'))
                if any(keyword in code for keyword in ['@RestController', '@GetMapping', '@PostMapping', '@RequestMapping', 'class ', 'public ']):
                    score += 10
                if score > 5:  
                    best_code = code
                    break
            
            if not best_code and code_examples:
                best_code = max(code_examples, key=len)

            if best_code and (len(best_code.split('\n')) >= 3 or len(best_code) > 80):
                answer_parts.append("**Code Example:**\n")
                if any(keyword in best_code for keyword in ['@RestController', '@RequestMapping', '@GetMapping', 'SpringBootApplication', 'import java']):
                    lang = "java"
                elif any(keyword in best_code for keyword in ['def ', 'import ', 'from ']):
                    lang = "python"
                elif any(keyword in best_code for keyword in ['function', 'const ', 'let ', '=>']):
                    lang = "javascript"
                else:
                    lang = ""
                
                answer_parts.append(f"```{lang}\n{best_code}\n```\n\n")
        
        if all_answers:
            answer_parts.append("**Additional Details:**\n")
            informative_paras = []
            for answer_data in all_answers[:3]:
                paragraphs = answer_data.get('paragraphs', [])
                for para in paragraphs[:2]:  
                    if (len(para) > 80 and len(para) < 400 and
                        para.count(' ') >= 10 and  
                        not any(skip in para.lower() for skip in ['http', 'www.', 'stackoverflow.com', 'click here', 'see link']) and
                        not para.startswith('```') and
                        not para.endswith((' org', ' com', ' =', ' gradle', ' maven'))):
                        informative_paras.append(para)
            
            seen = set()
            unique_paras = []
            for para in informative_paras:
                para_key = para[:100]  
                if para_key not in seen and len(unique_paras) < 5:
                    seen.add(para_key)
                    unique_paras.append(para)
            
            for para in unique_paras:
                answer_parts.append(f"{para}\n\n")
        
        result = ''.join(answer_parts)
        
        if len(result.strip()) < 150 and all_answers:
            best = all_answers[0]
            paragraphs = best.get('paragraphs', [])
            if paragraphs:
                result = '\n\n'.join(paragraphs[:3])
            else:
                sentences = best.get('sentences', [])
                if sentences:
                    result = '. '.join(sentences[:5]) + '.'
                else:
                    result = best.get('answer', '')[:1000]
        
        return result.strip()
    
    def _fallback_answer(self, prompt: str) -> str:
        return "Based on the retrieved Stack Overflow results, please review the provided answers for your question. The contexts above contain relevant information that may help solve your problem."
    
    def _extract_citations(self, contexts: List[Dict]) -> List[Dict]:
        citations = []
        
        for i, ctx in enumerate(contexts[:5], 1):
            citation = {
                'id': i,
                'title': ctx.get('title', ''),
                'link': ctx.get('link', ''),
                'score': ctx.get('score', 0)
            }
            citations.append(citation)
        
        return citations
    
    def summarize_answer(self, answer_text: str, max_length: int = 200) -> str:

        sentences = answer_text.split('. ')
        
        summary = []
        current_length = 0
        
        for sentence in sentences:
            if current_length + len(sentence) > max_length:
                break
            summary.append(sentence)
            current_length += len(sentence)
        
        return '. '.join(summary) + '.'


class LiveAssist:
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "https://api.stackexchange.com/2.3"
        self.confidence_threshold = 0.5
    
    def should_use_live_assist(self, local_results: List[Dict], 
                               confidence_threshold: float = None) -> bool:
        if confidence_threshold is None:
            confidence_threshold = self.confidence_threshold

        if not local_results:
            return True
        

        if local_results[0].get('bm25_score', 0) < confidence_threshold:
            return True
        

        top_result = local_results[0]
        answers = top_result.get('answers', [])
        has_accepted = any(a.get('is_accepted', False) for a in answers)
        
        if not has_accepted:
            return True
        
        return False
    
    def fetch_live_results(self, query: str, max_results: int = 5) -> List[Dict]:
        try:
            params = {
                'site': 'stackoverflow',
                'order': 'desc',
                'sort': 'relevance',
                'q': query,
                'filter': '!9_bDDxJY5',
                'pagesize': max_results
            }
            
            if self.api_key:
                params['key'] = self.api_key
            
            response = requests.get(
                f"{self.base_url}/search/advanced",
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
                        'tags': item.get('tags', []),
                        'is_answered': item.get('is_answered', False),
                        'answer_count': item.get('answer_count', 0),
                        'source': 'live'
                    }
                    results.append(result)
                
                return results
        
        except Exception as e:
            print(f"Error fetching live results: {e}")
        
        return []