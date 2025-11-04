from flask import Flask, render_template_string, request, jsonify
import sqlite3
import json
import os

app = Flask(__name__)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "stackoverflow.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SwaRAG Database Console</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            color: #333;
        }
        
        .header {
            background: #5BA2F5;
            color: Black;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 28px;
            margin-bottom: 5px;
        }
        
        .header p {
            opacity: 0.9;
            font-size: 14px;
        }
        
        .header-btn {
            background: black;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
        }
        
        .container {
            display: flex;
            height: calc(100vh - 80px);
        }
        
        .sidebar {
            width: 280px;
            background: white;
            border-right: 1px solid #ddd;
            overflow-y: auto;
            padding: 20px;
        }
        
        .sidebar h3 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 16px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .table-list {
            list-style: none;
        }
        
        .table-item {
            padding: 12px;
            margin-bottom: 8px;
            background: #f8f9fa;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s;
            border-left: 3px solid transparent;
        }
        
        .table-item:hover {
            background: #e9ecef;
            border-left-color: #667eea;
            transform: translateX(5px);
        }
        
        .table-item.active {
            background: #667eea;
            color: white;
            border-left-color: #764ba2;
        }
        
        .table-name {
            font-weight: 600;
            font-size: 14px;
        }
        
        .table-count {
            font-size: 12px;
            opacity: 0.7;
            margin-top: 4px;
        }
        
        .main-content {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-left: 4px solid #667eea;
        }
        
        .stat-card h4 {
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        
        .stat-card .value {
            font-size: 28px;
            font-weight: bold;
            color: #667eea;
        }
        
        .query-panel {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        
        .query-panel h3 {
            color: #667eea;
            margin-bottom: 15px;
        }
        
        textarea {
            width: 100%;
            min-height: 120px;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            resize: vertical;
            transition: border-color 0.3s;
        }
        
        textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .btn {
            padding: 12px 30px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s;
            margin-top: 10px;
        }
        
        .btn-primary {
            background: #05F076;
            color: white;
        }
        
        .btn-primary:hover {
            background: #28a745;
        }
        
        .btn-secondary {
            background: #ff6b6b;
            color: white;
            margin-left: 10px;
        }
        
        .btn-secondary:hover {
            background: #dc3545;
        }
        
        .results-panel {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            max-height: 600px;
            overflow: auto;
        }
        
        .results-panel h3 {
            color: #667eea;
            margin-bottom: 15px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        
        th {
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            position: sticky;
            top: 0;
        }
        
        td {
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
        }
        
        tr:hover {
            background: #f8f9fa;
        }
        
        .error {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            border-radius: 6px;
            color: #856404;
            margin-top: 15px;
        }
        
        .success {
            background: #d4edda;
            border-left: 4px solid #28a745;
            padding: 15px;
            border-radius: 6px;
            color: #155724;
            margin-top: 15px;
        }
        
        .quick-queries {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 10px;
        }
        
        .quick-query-btn {
            padding: 8px 16px;
            background: #e9ecef;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.3s;
        }
        
        .quick-query-btn:hover {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>SwaRAG Database Console created by Swarna</h1>
        </div>
        <button class="header-btn" onclick="window.location.href='http://localhost:5000'">SwaRAG</button>
    </div>
    
    <div class="container">
        <div class="sidebar">
            <h3>Tables</h3>
            <ul class="table-list" id="tableList"></ul>
        </div>
        
        <div class="main-content">
            <div class="stats-grid" id="statsGrid"></div>
            
            <div class="query-panel">
                <h3>Please Enter the SQL Query</h3>
                <textarea id="sqlQuery" placeholder="Nadigiriki Vanakam,
                Nan dha Sai Sankar"></textarea>
                
                <div style="text-align: center; margin-top: 15px;">
                    <button class="btn btn-primary" onclick="executeQuery()">▶ Run </button>
                    <button class="btn btn-secondary" onclick="clearResults()">Clear</button>
                </div>
            </div>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>Executing query...</p>
            </div>
            
            <div class="results-panel" id="resultsPanel" style="display:none;">
                <h3>Results</h3>
                <div id="results"></div>
            </div>
        </div>
    </div>
    
    <script>
        // Load database info on page load
        window.onload = function() {
            loadDatabaseInfo();
            loadStats();
        };
        
        function loadDatabaseInfo() {
            fetch('/api/tables')
                .then(response => response.json())
                .then(data => {
                    const tableList = document.getElementById('tableList');
                    tableList.innerHTML = '';
                    
                    data.tables.forEach(table => {
                        const li = document.createElement('li');
                        li.className = 'table-item';
                        li.onclick = () => browseTable(table.name);
                        li.innerHTML = `
                            <div class="table-name">${table.name}</div>
                            <div class="table-count">${table.count.toLocaleString()} rows</div>
                        `;
                        tableList.appendChild(li);
                    });
                });
        }
        
        function loadStats() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    const statsGrid = document.getElementById('statsGrid');
                    statsGrid.innerHTML = `
                        <div class="stat-card">
                            <h4>Total Questions</h4>
                            <div class="value">${data.questions.toLocaleString()}</div>
                        </div>
                        <div class="stat-card">
                            <h4>Total Answers</h4>
                            <div class="value">${data.answers.toLocaleString()}</div>
                        </div>
                        <div class="stat-card">
                            <h4>Index Terms</h4>
                            <div class="value">${data.index_terms.toLocaleString()}</div>
                        </div>
                        <div class="stat-card">
                            <h4>Avg Length</h4>
                            <div class="value">${data.avg_doc_length}</div>
                        </div>
                    `;
                });
        }
        
        function browseTable(tableName) {
            const query = `SELECT * FROM ${tableName} LIMIT 50`;
            document.getElementById('sqlQuery').value = query;
            executeQuery();
            
            // Highlight active table
            document.querySelectorAll('.table-item').forEach(item => {
                item.classList.remove('active');
            });
            event.target.closest('.table-item').classList.add('active');
        }
        
        function setQuery(query) {
            document.getElementById('sqlQuery').value = query;
        }
        
        function executeQuery() {
            const query = document.getElementById('sqlQuery').value;
            
            if (!query.trim()) {
                alert('Please enter a SQL query');
                return;
            }
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('resultsPanel').style.display = 'none';
            
            fetch('/api/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query: query })
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('resultsPanel').style.display = 'block';
                
                if (data.error) {
                    document.getElementById('results').innerHTML = `
                        <div class="error">
                            <strong>Error:</strong> ${data.error}
                        </div>
                    `;
                } else {
                    displayResults(data);
                }
            })
            .catch(error => {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('resultsPanel').style.display = 'block';
                document.getElementById('results').innerHTML = `
                    <div class="error">
                        <strong>Error:</strong> ${error.message}
                    </div>
                `;
            });
        }
        
        function displayResults(data) {
            const resultsDiv = document.getElementById('results');
            
            if (data.rows.length === 0) {
                resultsDiv.innerHTML = '<div class="success">Query executed successfully. No rows returned.</div>';
                return;
            }
            
            const columns = data.columns;
            const rows = data.rows;
            
            let html = `
                <div class="success">
                    Query executed successfully. ${rows.length} row(s) returned.
                </div>
                <table>
                    <thead>
                        <tr>
                            ${columns.map(col => `<th>${col}</th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            rows.forEach(row => {
                html += '<tr>';
                columns.forEach(col => {
                    let value = row[col];
                    if (typeof value === 'string' && value.length > 200) {
                        value = value.substring(0, 200) + '...';
                    }
                    if (value === null) {
                        value = '<i style="color:#999">NULL</i>';
                    }
                    html += `<td>${value}</td>`;
                });
                html += '</tr>';
            });
            
            html += `
                    </tbody>
                </table>
            `;
            
            resultsDiv.innerHTML = html;
        }
        
        function clearResults() {
            document.getElementById('results').innerHTML = '';
            document.getElementById('resultsPanel').style.display = 'none';
            document.getElementById('sqlQuery').value = '';
        }
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/tables')
def get_tables():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = []
        
        for row in cursor.fetchall():
            table_name = row['name']
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            count = cursor.fetchone()['count']
            
            tables.append({
                'name': table_name,
                'count': count
            })
        
        conn.close()
        
        return jsonify({'tables': tables})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
def get_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM questions")
        question_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM answers")
        answer_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(DISTINCT term) as count FROM inverted_index")
        index_terms = cursor.fetchone()['count']
        
        cursor.execute("SELECT AVG(doc_length) as avg FROM doc_stats")
        avg_doc_length = cursor.fetchone()['avg']
        avg_doc_length = round(avg_doc_length, 2) if avg_doc_length else 0
        
        conn.close()
        
        return jsonify({
            'questions': question_count,
            'answers': answer_count,
            'index_terms': index_terms,
            'avg_doc_length': avg_doc_length
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/query', methods=['POST'])
def execute_query():
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({'error': 'No query provided'}), 400
        
        query_lower = query.lower().strip()
        if any(keyword in query_lower for keyword in ['drop', 'delete', 'update', 'insert', 'alter', 'create']):
            return jsonify({'error': 'Only SELECT queries are allowed'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(query)
        
        columns = [description[0] for description in cursor.description] if cursor.description else []
        
        rows = []
        for row in cursor.fetchall():
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                if isinstance(value, (list, dict)):
                    value = json.dumps(value)
                row_dict[col] = value
            rows.append(row_dict)
        
        conn.close()
        
        return jsonify({
            'columns': columns,
            'rows': rows,
            'count': len(rows)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("SwaRAG Database Console created by Swarna\n")
    print(" Starting web server...\n")
    print(f"Database: {os.path.abspath(DB_PATH)}\n")
    print("Access the console at: http://localhost:8080/  \n")
    
    app.run(debug=True, host='0.0.0.0', port=8080)