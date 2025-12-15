import requests
import json
import re
import time
import traceback
from typing import List, Dict, Optional, Tuple
from html.parser import HTMLParser
from collections import defaultdict


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
        
        for i, ctx in enumerate(contexts[:8], 1):  
            question_title = ctx.get('title', 'Unknown')
            question_body = ctx.get('body', '')[:600]  
            
            answers = ctx.get('answers', [])
            
            
            best_answer = None
            if answers:
                sorted_answers = sorted(
                    answers, 
                    key=lambda x: (not x.get('is_accepted', False), -x.get('score', 0))
                )
                best_answer = sorted_answers[0]
            
            answer_text = ""
            if best_answer:
                answer_body = best_answer.get('body', '')       
                answer_text = answer_body[:3000] 
            
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
8. Include necessary import statements with code examples
9. Provide multiple code approaches if available

Provide a comprehensive answer:"""
        
        return prompt
    
    def _call_llm(self, prompt: str, max_length: int = 500) -> str:
        
        try:
            return self._generate_smart_answer(prompt)
        
        except Exception as e:
            print(f"Error generating answer: {e}")
            return self._fallback_answer(prompt)
    
    def _generate_smart_answer(self, prompt: str) -> str:
        

        query = prompt.split("User Question:")[1].split("Stack Overflow Contexts:")[0].strip()
        query_lower = query.lower()
        query_keywords = set([w for w in query_lower.split() if len(w) > 3])
        

        contexts_section = prompt.split("Stack Overflow Contexts:")[1].split("Instructions:")[0]
        context_blocks = contexts_section.split("[Context ")
        
        print(f"[RAG] Processing {len(context_blocks) - 1} context blocks from multiple sources")

        all_answers = []
        code_examples = []
        key_concepts = []
        step_by_step = []
        explanations = []
        imports_found = set()
        

        for block in context_blocks[1:]:
            if "Best Answer:" not in block:
                continue
                
            question_match = re.search(r'Question:\s*(.+?)\n', block)
            question_title = question_match.group(1).strip() if question_match else ""
            
            answer_match = re.search(r'Best Answer:\s*(.+?)(?:\nScore:|$)', block, re.DOTALL)
            if not answer_match:
                continue
                
            answer_text = answer_match.group(1).strip()
            answer_clean = self._strip_html_preserve_structure(answer_text)
                    
            list_patterns = [
                r'\d+[\.\)]\s*(.+?)(?=\d+[\.\)]|$)',  
                r'[-•]\s*(.+?)(?=[-•]|$)',
                r'step\s+\d+[:\s]+(.+?)(?=step\s+\d+|$)',  
            ]
            
            for pattern in list_patterns:
                matches = re.finditer(pattern, answer_clean, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    step_text = match.group(1).strip()
                    if len(step_text) > 15 and len(step_text) < 500:
                        is_duplicate = any(step_text.lower() == s['text'].lower()[:len(step_text)] for s in step_by_step)
                        if not is_duplicate:
                            step_by_step.append({'text': step_text, 'score': 0.9})

            imports = self._extract_imports(answer_text)
            imports_found.update(imports)
            

            code_with_context = self._extract_code_with_context(answer_text, answer_clean, query_keywords)
            code_examples.extend(code_with_context)
            

            paragraphs = self._extract_relevant_paragraphs(answer_clean, query_keywords)
            

            sentences = self._extract_sentences_with_scores(paragraphs, query_keywords)
            

            for sent_data in sentences:
                sent = sent_data['text']
                score = sent_data['score']
                
                if score < 0.15:
                    continue
                
                sent_lower = sent.lower()
                

                action_phrases = ['create', 'add', 'configure', 'implement', 'use', 'define', 
                                'annotate', 'write', 'build', 'set up', 'install', 'run', 'execute',
                                'initialize', 'setup', 'enable', 'disable', 'import', 'export',
                                'register', 'declare', 'extend', 'override', 'inject', 'autowire',
                                'decorate', 'wrap', 'extract', 'parse', 'validate', 'transform',
                                'convert', 'map', 'filter', 'handle', 'catch', 'throw', 'return',
                                'pass', 'call', 'invoke', 'first', 'then', 'next', 'after', 'before']
                
                sequential_words = ['first', 'second', 'third', 'then', 'next', 'after', 'before',
                                  'finally', 'lastly', 'subsequently', 'following', 'previously']
                
                has_action = any(phrase in sent_lower for phrase in action_phrases)
                has_sequential = any(word in sent_lower for word in sequential_words)
                is_imperative = (sent[0].isupper() and 
                               any(sent_lower.startswith(phrase) for phrase in action_phrases[:20]))
                
                if has_action or has_sequential or is_imperative:
                    if ' and ' in sent_lower or ' also ' in sent_lower:
                        parts = re.split(r'\s+(and|also|or)\s+', sent, flags=re.IGNORECASE)
                        for part in parts:
                            part = part.strip()
                            if len(part) > 20 and any(phrase in part.lower() for phrase in action_phrases):
                                is_duplicate = any(part.lower() == s['text'].lower()[:len(part)] for s in step_by_step)
                                if not is_duplicate and len(step_by_step) < 25:
                                    step_by_step.append({'text': part, 'score': score * 0.9})
                    else:
                        is_duplicate = any(sent.lower() == s['text'].lower() for s in step_by_step)
                        if not is_duplicate and len(step_by_step) < 25:
                            step_by_step.append({'text': sent, 'score': score})
                

                elif any(phrase in sent_lower for phrase in ['important', 'note', 'remember', 'key', 
                                                              'essential', 'required', 'must', 'should', 
                                                              'need to', 'make sure']):
                    if sent not in [c['text'] for c in key_concepts] and len(key_concepts) < 6:
                        key_concepts.append({'text': sent, 'score': score})
                

                elif any(word in sent_lower for word in ['because', 'this is', 'means', 'allows', 
                                                         'enables', 'provides', 'help', 'works by']):
                    if sent not in [e['text'] for e in explanations] and len(explanations) < 6:
                        explanations.append({'text': sent, 'score': score})
            
            all_answers.append({
                'question': question_title,
                'answer': answer_clean,
                'paragraphs': paragraphs,
                'sentences': sentences
            })
        

        step_by_step.sort(key=lambda x: x['score'], reverse=True)
        key_concepts.sort(key=lambda x: x['score'], reverse=True)
        code_examples.sort(key=lambda x: x['score'], reverse=True)
        explanations.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"[RAG] Extracted {len(step_by_step)} steps, {len(code_examples)} code examples, {len(key_concepts)} concepts from {len(all_answers)} sources")
        
        code_examples = self._deduplicate_code(code_examples)
        

        answer_parts = []
        

        if any(word in query_lower for word in ['how', 'create', 'build', 'implement', 'make']):
            answer_parts.extend(self._build_steps_section(step_by_step[:20]))  
            answer_parts.extend(self._build_code_section(code_examples[:5], imports_found))  
            answer_parts.extend(self._build_concepts_section(key_concepts[:8]))  
        
        elif any(word in query_lower for word in ['what', 'explain', 'why', 'difference']):
            answer_parts.extend(self._build_concepts_section(key_concepts[:8]))  
            answer_parts.extend(self._build_explanation_section(explanations[:6]))  
            answer_parts.extend(self._build_code_section(code_examples[:4], imports_found))  
        
        elif any(word in query_lower for word in ['code', 'example', 'syntax', 'snippet']):
            answer_parts.extend(self._build_code_section(code_examples[:6], imports_found))  
            answer_parts.extend(self._build_steps_section(step_by_step[:15]))  
        
        else:
            answer_parts.extend(self._build_steps_section(step_by_step[:18]))  
            answer_parts.extend(self._build_code_section(code_examples[:5], imports_found))  
            answer_parts.extend(self._build_concepts_section(key_concepts[:8]))  
        
        if all_answers and len(''.join(answer_parts)) < 1000:
            answer_parts.extend(self._build_details_section(all_answers, query_keywords))
        
        result = ''.join(answer_parts).strip()
        
        if len(result.strip()) < 150 and all_answers:
            result = self._build_fallback_answer(all_answers, query_keywords)
        
        if len(result.strip()) < 100 and all_answers:
            print("[RAG] Warning: Very short response, using raw answer content")
            best_answer = all_answers[0]
            result = best_answer.get('answer', '')[:2000]
        
        return result
    
    def _strip_html_preserve_structure(self, html: str) -> str:
        if not html:
            return ""
        
        code_blocks = []
        code_pattern = r'<(?:code|pre)[^>]*>(.*?)</(?:code|pre)>'
        for i, match in enumerate(re.finditer(code_pattern, html, re.DOTALL | re.IGNORECASE)):
            code_blocks.append(match.group(1))
            html = html.replace(match.group(0), f'__CODE_BLOCK_{i}__')
        
        html = re.sub(r'</p>', '\n\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<p[^>]*>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<li[^>]*>', '• ', html, flags=re.IGNORECASE)
        html = re.sub(r'</li>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<h[1-6][^>]*>', '\n### ', html, flags=re.IGNORECASE)
        html = re.sub(r'</h[1-6]>', '\n', html, flags=re.IGNORECASE)
        
        html = re.sub(r'<[^>]+>', '', html)
        
        for i, code in enumerate(code_blocks):
            html = html.replace(f'__CODE_BLOCK_{i}__', code)
        
        html = re.sub(r'[ \t]+', ' ', html)
        html = re.sub(r'\n{3,}', '\n\n', html)
        
        return html.strip()
    
    def _extract_imports(self, html: str) -> List[str]:
        imports = []
        
        patterns = [
            r'import\s+[\w.]+(?:\s+as\s+\w+)?',  # Python
            r'from\s+[\w.]+\s+import\s+[\w,\s*]+',  # Python
            r'import\s+\{[^}]+\}\s+from\s+["\'][^"\']+["\']',  # JavaScript/TypeScript
            r'import\s+[\w]+\s+from\s+["\'][^"\']+["\']',  # JavaScript
            r'@import\s+[\w.]+',  # Java
            r'using\s+[\w.]+',  # C#
            r'require\(["\'][^"\']+["\']\)',  # Node.js
            r'#include\s*[<"][^>"]+[>"]',  # C/C++
        ]
        
        text = self._strip_html_preserve_structure(html)
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            imports.extend(matches)
        
        return list(set(imports))
    
    def _extract_code_with_context(self, html: str, text: str, query_keywords: set) -> List[Dict]:
        code_examples = []
        
        patterns = [
            (r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', 'block'),
            (r'<pre[^>]*>(.*?)</pre>', 'block'),
            (r'<code[^>]*>(.*?)</code>', 'inline'),
            (r'```[\w]*\n(.*?)```', 'block'),
        ]
        
        for pattern, code_type in patterns:
            matches = re.finditer(pattern, html, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                code = match.group(1).strip()
                
                if len(code) < 30 or len(code) > 2000:
                    continue
                
                if code_type == 'inline' and '\n' not in code:
                    continue
                
                code_indicators = ['@', 'class ', 'def ', 'function', 'public ', 'private ', 
                                  'import ', 'const ', 'let ', 'var ', '{', '}', '()', '=>', 
                                  'package ', 'using ', '#include']
                
                if not any(indicator in code for indicator in code_indicators):
                    continue
                
                start_pos = text.find(code)
                context_before = ""
                context_after = ""
                
                if start_pos != -1:
                    before_text = text[max(0, start_pos - 300):start_pos]
                    after_text = text[start_pos + len(code):start_pos + len(code) + 300]
                    
                    sentences_before = re.split(r'[.!?]\s+', before_text)
                    if sentences_before:
                        context_before = sentences_before[-1].strip()
                    
                    sentences_after = re.split(r'[.!?]\s+', after_text)
                    if sentences_after:
                        context_after = sentences_after[0].strip()
                
                score = self._calculate_code_relevance(code, context_before, context_after, query_keywords)
                
                code_examples.append({
                    'code': code,
                    'context_before': context_before,
                    'context_after': context_after,
                    'language': self._detect_language(code),
                    'score': score,
                    'type': code_type
                })
        
        return code_examples
    
    def _calculate_code_relevance(self, code: str, context_before: str, 
                                  context_after: str, query_keywords: set) -> float:
        score = 0.0
        
        combined_text = f"{context_before} {code} {context_after}".lower()
        
        keyword_matches = sum(1 for kw in query_keywords if kw in combined_text)
        score += keyword_matches * 0.2
        
        lines = code.split('\n')
        if len(lines) >= 3:
            score += 0.3
        
        if len(lines) >= 10:
            score += 0.2
        
        if '//' in code or '#' in code or '/*' in code:
            score += 0.1
        
        if len(context_before) > 20:
            score += 0.15
        
        if len(context_after) > 20:
            score += 0.15
        
        return min(score, 1.0)
    
    def _extract_relevant_paragraphs(self, text: str, query_keywords: set) -> List[Dict]:
        paragraphs = []
        
        for para in text.split('\n\n'):
            para = para.strip()
            
            if len(para) < 30 or para.startswith('```'):
                continue
            
            para_lower = para.lower()
            keyword_matches = sum(1 for kw in query_keywords if kw in para_lower)
            relevance = min(keyword_matches / max(len(query_keywords), 1), 1.0)
            
            if relevance < 0.1 and len(paragraphs) > 8:
                continue
            
            paragraphs.append({
                'text': para,
                'relevance': relevance,
                'length': len(para)
            })
        
        return paragraphs
    
    def _extract_sentences_with_scores(self, paragraphs: List[Dict], 
                                      query_keywords: set) -> List[Dict]:
        sentences = []
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        
        for para_data in paragraphs:
            para = para_data['text']
            para_relevance = para_data['relevance']
            
            sents = re.split(sentence_pattern, para)
            
            for sent in sents:
                sent = sent.strip()
                
                if (len(sent) < 30 or len(sent) > 600 or 
                    sent.count(' ') < 3 or
                    sent.endswith((' org', ' com', ' http', ' www')) or
                    any(skip in sent.lower() for skip in ['click here', 'see this', 'stackoverflow.com'])):
                    continue
                
                sent_lower = sent.lower()
                keyword_matches = sum(1 for kw in query_keywords if kw in sent_lower)
                sent_relevance = min(keyword_matches / max(len(query_keywords), 1), 1.0)
                
                combined_score = (sent_relevance * 0.6) + (para_relevance * 0.4)
                
                sentences.append({
                    'text': sent,
                    'score': combined_score
                })
        
        return sentences
    
    def _deduplicate_code(self, code_examples: List[Dict]) -> List[Dict]:
        if not code_examples:
            return []
        
        unique_codes = []
        seen_signatures = set()
        
        for example in code_examples:
            code = example['code']
            
            signature = code[:100].lower().replace(' ', '').replace('\n', '')
            
            is_duplicate = False
            for seen_sig in seen_signatures:
                common = sum(1 for c in signature if c in seen_sig)
                similarity = common / max(len(signature), len(seen_sig))
                
                if similarity > 0.7:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_codes.append(example)
                seen_signatures.add(signature)
        
        return unique_codes
    
    def _detect_language(self, code: str) -> str:   
        code_lower = code.lower()
        
        if any(kw in code for kw in ['@RestController', '@GetMapping', '@PostMapping', 
                                       '@RequestMapping', '@Autowired', 'SpringBootApplication']):
            return 'java'
        
        if any(kw in code for kw in ['public class', 'private class', 'public static void', 
                                      'System.out.', 'package ', 'import java.']):
            return 'java'
        
        if any(kw in code for kw in ['def ', 'import ', 'from ', '__init__', 'self.', 
                                      'elif ', 'raise ', 'except ']):
            return 'python'
        
        if any(kw in code for kw in ['function', 'const ', 'let ', '=>', 'var ', 
                                      'import {', 'export ', 'async ', 'await ']):
            return 'javascript'
        
        if any(kw in code for kw in ['using System', 'namespace ', 'public void', 
                                      'private void', 'async Task']):
            return 'csharp'
        
        if any(kw in code for kw in ['#include <', 'std::', 'cout <<', 'cin >>', 
                                      'namespace std']):
            return 'cpp'
        
        if any(kw in code for kw in ['func ', 'package main', 'import "', 'fmt.Print']):
            return 'go'
        
        if any(kw in code for kw in ['def ', 'end', 'require ', 'puts ', 'attr_']):
            return 'ruby'
        
        if '<?php' in code or any(kw in code for kw in ['$_GET', '$_POST', 'echo ', 'function ']):
            return 'php'
        
        if any(kw in code_lower for kw in ['select ', 'insert ', 'update ', 'delete ', 
                                            'create table', 'alter table']):
            return 'sql'
        
        if any(kw in code for kw in ['#!/bin/', 'sudo ', 'apt ', 'brew ', 'chmod ', 'chown ']):
            return 'bash'
        
        return ''
    
    def _build_steps_section(self, steps: List[Dict]) -> List[str]:
        if not steps:
            return []
        
        parts = ["**Step-by-Step Approach:**\n"]
        for i, step_data in enumerate(steps, 1):
            step = step_data['text'].rstrip('.,;:')
            parts.append(f"{i}. {step}.\n")
        parts.append("\n")
        
        return parts
    
    def _build_code_section(self, code_examples: List[Dict], imports: set) -> List[str]:
        if not code_examples:
            return []
        
        parts = []
        
        if imports:
            parts.append("**Required Imports:**\n```\n")
            for imp in sorted(list(imports))[:5]:
                parts.append(f"{imp}\n")
            parts.append("```\n\n")
        
        if len(code_examples) == 1:
            parts.append("**Code Example:**\n")
        else:
            parts.append("**Code Examples:**\n")
        
        for i, example in enumerate(code_examples[:3], 1):
            if example['context_before'] and len(example['context_before']) > 20:
                parts.append(f"*{example['context_before']}*\n\n")
            
            lang = example['language']
            if len(code_examples) > 1:
                parts.append(f"**Approach {i}:**\n")
            
            parts.append(f"```{lang}\n{example['code']}\n```\n")
            
            if example['context_after'] and len(example['context_after']) > 20:
                parts.append(f"*{example['context_after']}*\n")
            
            parts.append("\n")
        
        return parts
    
    def _build_concepts_section(self, concepts: List[Dict]) -> List[str]:
        if not concepts:
            return []
        
        parts = ["**Key Concepts:**\n"]
        for concept_data in concepts:
            concept = concept_data['text'].rstrip('.,;:')
            parts.append(f"• {concept}.\n")
        parts.append("\n")
        
        return parts
    
    def _build_explanation_section(self, explanations: List[Dict]) -> List[str]:
        if not explanations:
            return []
        
        parts = ["**Explanation:**\n"]
        for exp_data in explanations:
            parts.append(f"{exp_data['text']}\n\n")
        
        return parts
    
    def _build_details_section(self, all_answers: List[Dict], query_keywords: set) -> List[str]:
        parts = ["**Additional Details:**\n"]
        
        informative_paras = []
        for answer_data in all_answers[:3]:
            paragraphs = answer_data.get('paragraphs', [])
            for para_data in paragraphs[:2]:
                para = para_data['text']
                
                if (len(para) > 80 and len(para) < 400 and
                    para.count(' ') >= 10 and
                    not any(skip in para.lower() for skip in ['http', 'www.', 'stackoverflow.com', 
                                                                'click here', 'see link']) and
                    not para.startswith('```')):
                    
                    relevance = sum(1 for kw in query_keywords if kw in para.lower())
                    informative_paras.append((para, relevance))
        
        informative_paras.sort(key=lambda x: x[1], reverse=True)
        
        seen = set()
        for para, _ in informative_paras:
            para_key = para[:100]
            if para_key not in seen and len(seen) < 4:
                seen.add(para_key)
                parts.append(f"{para}\n\n")
        
        return parts if len(seen) > 0 else []
    
    def _build_fallback_answer(self, all_answers: List[Dict], query_keywords: set) -> str:
        best = all_answers[0] if all_answers else None
        
        if not best:
            return "Based on the Stack Overflow results, please review the provided answers."
        
        paragraphs = best.get('paragraphs', [])
        
        if paragraphs:
            relevant = [(p['text'], p.get('relevance', 0)) for p in paragraphs if len(p.get('text', '')) > 30]
            relevant.sort(key=lambda x: x[1], reverse=True)
            
            if relevant:
                return '\n\n'.join([p[0] for p in relevant[:4]])
        
        sentences = best.get('sentences', [])
        if sentences:       
            top_sentences = sorted(sentences, key=lambda x: x.get('score', 0), reverse=True)[:8]
            if top_sentences:
                return '. '.join([s['text'] for s in top_sentences]) + '.'
        
    
        return best.get('answer', '')[:1500]
    
    def _fallback_answer(self, prompt: str) -> str:
        return "Based on the retrieved Stack Overflow results, please review the provided answers for your question. The contexts contain relevant information that may help solve your problem."
    
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
    
    def analyze_single_document(self, question_title: str, question_body: str, 
                                 answer_body: str, query: str = "") -> Dict:

        try:
            
            document = {
                'title': question_title,
                'body': question_body[:600] if question_body else '',
                'answers': [{'body': answer_body, 'is_accepted': True, 'score': 0}],
                'link': '',
                'score': 0
            }
            
            analysis_query = query if query else question_title
            
            answer_clean = self._strip_html_preserve_structure(answer_body)
            query_keywords = set([w for w in analysis_query.lower().split() if len(w) > 3])
            
            imports = self._extract_imports(answer_body)
            
            code_examples = self._extract_code_with_context(answer_body, answer_clean, query_keywords)
            code_examples.sort(key=lambda x: x['score'], reverse=True)
            code_examples = self._deduplicate_code(code_examples)
            
            paragraphs = self._extract_relevant_paragraphs(answer_clean, query_keywords)
            
            sentences = self._extract_sentences_with_scores(paragraphs, query_keywords)
            
            step_by_step = []
            key_concepts = []
            important_notes = []
            explanations = []
            
            list_patterns = [
                r'\d+[\.\)]\s*(.+?)(?=\d+[\.\)]|$)',  
                r'[-•]\s*(.+?)(?=[-•]|$)',  
                r'step\s+\d+[:\s]+(.+?)(?=step\s+\d+|$)',  
            ]
            
            for pattern in list_patterns:
                matches = re.finditer(pattern, answer_clean, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    step_text = match.group(1).strip()
                    if len(step_text) > 20 and len(step_text) < 500:
                        step_by_step.append({'text': step_text, 'score': 0.8})
            
            for sent_data in sentences:
                sent = sent_data['text']
                score = sent_data['score']
                
                if score < 0.15:
                    continue
                
                sent_lower = sent.lower()
                
                action_phrases = ['create', 'add', 'configure', 'implement', 'use', 'define', 
                                 'annotate', 'write', 'build', 'set up', 'install', 'run', 
                                 'execute', 'step', 'first', 'then', 'next', 'finally', 'after',
                                 'before', 'initialize', 'setup', 'enable', 'disable', 'import',
                                 'export', 'register', 'declare', 'extend', 'override', 'inject',
                                 'autowire', 'annotate', 'decorate', 'wrap', 'extract', 'parse',
                                 'validate', 'transform', 'convert', 'map', 'filter', 'handle',
                                 'catch', 'throw', 'return', 'pass', 'call', 'invoke']
                
                sequential_words = ['first', 'second', 'third', 'then', 'next', 'after', 'before',
                                  'finally', 'lastly', 'subsequently', 'following', 'previously']
                
                has_action = any(phrase in sent_lower for phrase in action_phrases)
                has_sequential = any(word in sent_lower for word in sequential_words)
                
                is_imperative = (sent[0].isupper() and 
                               any(sent_lower.startswith(phrase) for phrase in action_phrases[:15]))
                
                if has_action or has_sequential or is_imperative:
                    if ' and ' in sent_lower or ' also ' in sent_lower:
                        parts = re.split(r'\s+(and|also|or)\s+', sent, flags=re.IGNORECASE)
                        for part in parts:
                            part = part.strip()
                            if len(part) > 30 and any(phrase in part.lower() for phrase in action_phrases):
                                if part not in [s['text'] for s in step_by_step]:
                                    step_by_step.append({'text': part, 'score': score * 0.9})
                    else:
                        if sent not in [s['text'] for s in step_by_step] and len(step_by_step) < 25:
                            step_by_step.append({'text': sent, 'score': score})
                
                elif any(phrase in sent_lower for phrase in ['important', 'note', 'remember', 'key', 
                                                           'essential', 'required', 'must', 'should', 
                                                           'need to', 'make sure', 'crucial']):
                    if sent not in [c['text'] for c in key_concepts] and len(key_concepts) < 10:
                        key_concepts.append({'text': sent, 'score': score})
                
                elif any(phrase in sent_lower for phrase in ['warning', 'caution', 'avoid', 'don\'t', 
                                                           'never', 'always', 'ensure', 'be careful']):
                    if sent not in [n['text'] for n in important_notes] and len(important_notes) < 8:
                        important_notes.append({'text': sent, 'score': score})
                
                elif any(word in sent_lower for word in ['because', 'this is', 'means', 'allows', 
                                                         'enables', 'provides', 'help', 'works by', 
                                                         'reason', 'why']):
                    if sent not in [e['text'] for e in explanations] and len(explanations) < 8:
                        explanations.append({'text': sent, 'score': score})
            
            step_by_step.sort(key=lambda x: x['score'], reverse=True)
            key_concepts.sort(key=lambda x: x['score'], reverse=True)
            important_notes.sort(key=lambda x: x['score'], reverse=True)
            explanations.sort(key=lambda x: x['score'], reverse=True)
            
            result = {
                'original_question': question_title,
                'step_by_step_solution': [step['text'].strip() for step in step_by_step[:12]],
                'code_examples': [
                    {
                        'code': ex['code'],
                        'language': ex['language'],
                        'context_before': ex['context_before'],
                        'context_after': ex['context_after']
                    }
                    for ex in code_examples[:5]
                ],
                'key_concepts': [concept['text'].strip() for concept in key_concepts[:8]],
                'important_notes': [note['text'].strip() for note in important_notes[:6]],
                'explanations': [exp['text'].strip() for exp in explanations[:6]],
                'imports': list(imports)[:10],
                'success': True
            }
            
            return result
            
        except Exception as e:
            print(f"Error analyzing document: {e}")
            traceback.print_exc()
            return {
                'original_question': question_title,
                'step_by_step_solution': [],
                'code_examples': [],
                'key_concepts': [],
                'important_notes': [],
                'explanations': [],
                'imports': [],
                'success': False,
                'error': str(e)
            }


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