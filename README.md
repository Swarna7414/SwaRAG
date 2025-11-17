---
title: SwaRAG
colorFrom: blue
colorTo: purple
sdk: docker
sdk_version: "latest"
app_file: app.py
pinned: false
---

# SwaRAG - Stack Overflow Search Engine with RAG Integration

SwaRAG is an intelligent search engine that combines local indexing, BM25 ranking, and Retrieval Augmented Generation (RAG) to provide comprehensive answers to programming questions. The system indexes Stack Overflow questions and answers locally, uses advanced ranking algorithms to find relevant content, and leverages RAG to synthesize coherent, structured answers from multiple sources.

## Overview

SwaRAG addresses the challenge of finding and understanding programming solutions by combining the speed of local search with the intelligence of AI-powered answer generation. The system maintains a local database of Stack Overflow content, indexes it using inverted indexes, ranks results using BM25 with title boosting, and generates comprehensive answers using RAG techniques.

## Architecture

The SwaRAG system follows a modular architecture with distinct components handling data collection, indexing, ranking, and answer generation. The architecture is designed for scalability, maintainability, and performance.

### System Components

#### 1. Data Collection Layer

The data collection layer is responsible for fetching questions and answers from Stack Overflow using the Stack Exchange API. The `StackOverflowDownloader` class handles API interactions, rate limiting, and data retrieval.

- **StackOverflowDownloader**: Downloads questions and answers by tags from Stack Overflow API
- **Rate Limiting**: Implements backoff strategies and respects API rate limits
- **Data Storage**: Stores raw questions and answers in SQLite database

#### 2. Database Layer

The database layer uses SQLite to store all indexed content and metadata. The `Database` class provides an abstraction for database operations.

**Database Schema:**
- **questions**: Stores question metadata (title, body, tags, scores, links)
- **answers**: Stores answer content linked to questions
- **inverted_index**: Stores term-to-document mappings with frequencies and positions
- **doc_stats**: Stores document length statistics for BM25 calculations

The database uses indexes on frequently queried columns to optimize search performance.

#### 3. Text Processing Layer

The text processing layer normalizes and prepares text for indexing and searching. The `TextProcessor` class handles tokenization, stemming, stopword removal, and code keyword extraction.

**Processing Pipeline:**
1. HTML tag removal
2. Code block extraction and preservation
3. Lowercasing
4. Tokenization
5. Stopword removal
6. Stemming (Porter-style algorithm)
7. Code keyword extraction (annotations, class names, method names)

#### 4. Indexing Layer

The indexing layer builds and maintains search indexes. The `Indexer` class processes questions and answers to create inverted indexes.

**Indexing Process:**
1. Text processing (tokenization, stemming)
2. Position tracking for each term
3. Frequency calculation
4. Inverted index construction
5. Document statistics calculation

The system indexes questions with title boosting (title terms appear twice in the full text), answers separately, and tags as special document types for enhanced tag-based filtering.

#### 5. Ranking Layer

The ranking layer implements BM25 (Best Matching 25) algorithm with enhancements for programming content. The `BM25Ranker` class scores and ranks documents based on query relevance.

**BM25 Scoring:**
- Uses standard BM25 formula with k1=1.5 and b=0.75
- Calculates IDF (Inverse Document Frequency) for each term
- Applies term frequency normalization based on document length
- Implements title boosting (5x weight for title matches)
- Applies Stack Overflow score and recency boosts

**Quality Filtering:**
- Minimum score threshold (20.0) to filter low-quality results
- Tag-based filtering for framework-specific searches
- Stack Overflow score and recency considerations

#### 6. RAG Integration Layer

The RAG (Retrieval Augmented Generation) layer synthesizes answers from retrieved contexts. The `RAGIntegration` class processes multiple Stack Overflow answers to generate coherent, structured responses.

**RAG Process:**
1. Context retrieval from search results
2. HTML cleaning with structure preservation
3. Content extraction (sentences, paragraphs, code blocks)
4. Information synthesis into structured sections
5. Answer generation with citations

**Answer Structure:**
- Step-by-Step Approach
- Key Concepts
- Code Examples (with language detection)
- Additional Details

#### 7. API Layer

The API layer exposes REST endpoints for search and RAG functionality. Built with Flask, it provides CORS support and JSON responses.

**Key Endpoints:**
- `/health`: System health and database status
- `/search`: Local BM25 search with optional tag filtering
- `/ragsearch`: RAG-powered answer generation
- `/stats`: Database and index statistics
- `/db-console`: Web-based database console UI

## How SwaRAG Works

### Data Flow

#### 1. Initial Setup and Indexing

When setting up SwaRAG, the system follows these steps:

1. **Data Download**: The `StackOverflowDownloader` fetches questions and answers from Stack Overflow API for specified tags (e.g., spring-boot, react, django, node.js, flask)
2. **Database Storage**: Questions and answers are stored in SQLite with all metadata
3. **Indexing**: The `Indexer` processes each question and answer:
   - Extracts and processes text (tokenization, stemming)
   - Builds inverted index entries with term frequencies and positions
   - Calculates document statistics (length, term counts)
4. **Index Completion**: The system builds complete inverted indexes for fast retrieval

#### 2. Search Query Processing

When a user submits a search query:

1. **Query Processing**: The query is tokenized, stemmed, and stopwords are removed
2. **Term Lookup**: Each query term is looked up in the inverted index to find candidate documents
3. **Document Scoring**: BM25 algorithm scores each candidate document:
   - Calculates term frequency (TF) for each query term
   - Calculates inverse document frequency (IDF) for each term
   - Applies document length normalization
   - Applies title boosting (5x multiplier for title matches)
   - Adds Stack Overflow score and recency boosts
4. **Result Collection**: Top-scoring questions are collected with their answers
5. **Quality Filtering**: Results below the minimum score threshold are filtered out
6. **Tag Filtering**: If a tag is specified, only questions with that tag are returned

#### 3. RAG Answer Generation

When using the RAG endpoint:

1. **Query Enhancement**: The query is improved with framework-specific terms and synonyms
2. **Live Search**: The system fetches current results from Stack Overflow API (not just local index)
3. **Relevance Filtering**: Results are filtered for relevance to the query
4. **Context Formatting**: Top results are formatted with question titles, bodies, and best answers
5. **Content Extraction**: The RAG system extracts:
   - Complete sentences and paragraphs
   - Code examples with language detection
   - Key concepts and step-by-step instructions
6. **Answer Synthesis**: Information is synthesized into structured sections:
   - Step-by-step approach
   - Key concepts
   - Code examples
   - Additional details
7. **Response Generation**: A coherent answer is generated with citations to source questions

### Search Modes

#### Local Search Mode

The `/search` endpoint uses the local indexed database for fast retrieval. This mode:
- Searches only the pre-indexed Stack Overflow content
- Uses BM25 ranking with title boosting
- Applies quality score thresholds
- Falls back to live Stack Overflow API if no quality local results are found

#### RAG Mode

The `/ragsearch` endpoint combines live Stack Overflow API results with RAG synthesis. This mode:
- Fetches current results from Stack Overflow API
- Filters results for relevance
- Generates comprehensive answers using RAG
- Provides structured, synthesized responses

### Performance Optimizations

1. **Inverted Index**: Fast term-to-document lookups
2. **IDF Caching**: Caches IDF values to avoid repeated calculations
3. **Document Statistics Caching**: Caches total documents and average document length
4. **Query Optimization**: Processes query terms in order of selectivity
5. **Early Termination**: Stops processing when sufficient high-quality results are found

## Deployment

SwaRAG is deployed and hosted on Hugging Face Spaces, making it accessible via a web interface and REST API endpoints. The application is fully functional and ready to use without any local setup required.

### Accessing the Application

The SwaRAG application is available at:
- **Hugging Face Space**: `https://huggingface.co/spaces/SaiSankarSwarna/SwaRAG`

### Available Services

Once deployed, the following services are accessible:

1. **REST API Endpoints**: All API endpoints are available at the Hugging Face Space URL
2. **Database Console**: Web-based UI for browsing the database at `/db-console`
3. **Health Monitoring**: System health checks at `/health`
4. **Statistics**: Database and index statistics at `/stats`

### Deployment Architecture

The application runs on Hugging Face Spaces infrastructure:
- **Container**: Docker-based deployment with Python 3.13
- **Web Server**: Gunicorn with 2 workers for handling concurrent requests
- **Port**: 7860 (Hugging Face default)
- **Database**: Pre-populated SQLite database (stackoverflow.db) with indexed content
- **Auto-deployment**: GitHub Actions workflow for automated deployments from the Live branch

### Deployment Process

The deployment process includes:
1. Database verification before deployment to ensure data integrity
2. Upload of all files including the pre-populated database to Hugging Face
3. Application startup on port 7860 (Hugging Face default)
4. Gunicorn serving the Flask application with 2 workers for optimal performance

### Environment Variables

The following environment variables are configured in the Hugging Face Space:
- `HF_TOKEN`: Hugging Face authentication token for deployment
- `STACK_API_KEY`: Stack Overflow API key for live search functionality
- `DB_PATH`: Path to SQLite database (default: stackoverflow.db)

## API Endpoints

### Health Check

**GET** `/health`

Returns system health and database status.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "questions_indexed": 1012
}
```

### Search

**POST** `/search`

Searches the local index using BM25 ranking.

**Request Body:**
```json
{
  "query": "how to create rest api",
  "tag": "spring-boot"
}
```

**Response:**
```json
{
  "query": "how to create rest api",
  "results": [
    {
      "question_id": 12345,
      "title": "How to create REST API in Spring Boot",
      "body": "...",
      "link": "https://stackoverflow.com/questions/12345",
      "score": 15,
      "tags": "spring-boot rest api",
      "bm25_score": 45.23,
      "answers": [...]
    }
  ],
  "used_live": false
}
```

### Search with RAG

**POST** `/ragsearch`

Generates AI-powered answers using RAG.

**Request Body:**
```json
{
  "query": "how to create rest api in springBoot",
  "tag": "spring-boot"
}
```

**Response:**
```json
{
  "question": "how to create rest api in springBoot",
  "rag_response": "**Step-by-Step Approach:**\n1. Create a Spring Boot project...\n\n**Key Concepts:**\n• Use @RestController annotation...\n\n**Code Example:**\n```java\n@RestController\npublic class ApiController {...}\n```",
  "references": [
    {
      "title": "How to create REST API in Spring Boot",
      "link": "https://stackoverflow.com/questions/12345",
      "score": 15
    }
  ]
}
```

### Statistics

**GET** `/stats`

Returns database and index statistics.

**Response:**
```json
{
  "questions": 1012,
  "answers": 1251,
  "index_terms": 24718,
  "avg_doc_length": 170.25
}
```

### Database Console

**GET** `/db-console`

Web-based UI for browsing the database, viewing tables, and executing SQL queries.

## Technical Details

### BM25 Algorithm

The BM25 ranking algorithm uses the following formula:

```
score = IDF(q) * (TF(q, d) * (k1 + 1)) / (TF(q, d) + k1 * (1 - b + b * (|d| / avgdl)))
```

Where:
- `IDF(q)`: Inverse document frequency of query term
- `TF(q, d)`: Term frequency in document
- `k1`: Term frequency saturation parameter (1.5)
- `b`: Length normalization parameter (0.75)
- `|d|`: Document length
- `avgdl`: Average document length

### Text Processing

The text processing pipeline includes:
- HTML tag removal while preserving structure
- Code block extraction and preservation
- Porter-style stemming algorithm
- Stopword removal (common English words)
- Code keyword extraction (annotations, class names, SQL keywords)

### RAG Answer Generation

The RAG system:
1. Extracts complete sentences and paragraphs from HTML content
2. Identifies code examples with language detection
3. Categorizes content into steps, concepts, and examples
4. Synthesizes information into structured sections
5. Preserves code formatting and structure

## Project Structure

```
SwaRAG/
├── api/
│   └── api.py              # Flask API endpoints
├── data/
│   ├── database.py         # Database abstraction layer
│   ├── db_console.py        # Database console UI
│   └── stackoverflow_downloader.py  # API data fetcher
├── indexing/
│   └── indexer.py          # Index building logic
├── processing/
│   └── text_processing.py  # Text normalization
├── ranking/
│   └── bm25_ranker.py      # BM25 ranking algorithm
├── rag/
│   └── rag_integration.py  # RAG answer generation
├── main.py                  # CLI entry point
├── app.py                   # Hugging Face entry point
├── Dockerfile              # Container configuration
├── requirements.txt        # Python dependencies
└── stackoverflow.db        # SQLite database
```

## Configuration

### Environment Variables

- `STACK_API_KEY`: Stack Overflow API key for live search
- `CLIENT_ID`: Stack Overflow API client ID
- `DB_PATH`: Path to SQLite database file
- `PORT`: Server port (default: 7860 for Hugging Face)

### Search Parameters

- `min_score`: Minimum BM25 score threshold (default: 20.0)
- `title_boost`: Title match multiplier (default: 5.0)
- `k1`: BM25 term frequency parameter (default: 1.5)
- `b`: BM25 length normalization parameter (default: 0.75)

## Limitations and Future Improvements

### Current Limitations

1. Local search is limited to pre-indexed content
2. RAG uses live Stack Overflow API, which has rate limits
3. Database size is limited by available storage
4. Single-threaded indexing process

### Potential Improvements

1. Distributed indexing for larger datasets
2. Semantic search using embeddings
3. Caching layer for frequently asked questions
4. Multi-language support
5. Real-time index updates
6. Advanced query expansion using word embeddings

## License

This project is developed for educational and research purposes.

## Author

Sai Sankar Swarna

## Acknowledgments

- Stack Overflow for providing the API and community content
- Hugging Face for hosting infrastructure
- The open-source community for various libraries and tools