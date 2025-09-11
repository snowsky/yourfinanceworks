# Global Search System

A comprehensive search system that allows users to search across all data in the invoice management system using OpenSearch for indexing and full-text search capabilities.

## 🚀 Features

### Search Capabilities
- **Global Search** - Search across invoices, clients, payments, expenses, statements, and attachments
- **Real-time Search** - Instant search results with debounced queries
- **Fuzzy Matching** - Find results even with typos or partial matches
- **Highlighted Results** - Search terms are highlighted in results
- **Entity Type Filtering** - Filter results by specific entity types
- **Smart Ranking** - Results ranked by relevance score

### User Interface
- **Command Palette** - Press `Cmd+K` (Mac) or `Ctrl+K` (Windows) to open search
- **Modern UI** - Clean, responsive search dialog using cmdk
- **Entity Icons** - Visual indicators for different entity types
- **Quick Navigation** - Click results to navigate directly to entities
- **Loading States** - Visual feedback during search operations

### Backend Architecture
- **OpenSearch Integration** - Full-text search with advanced querying
- **Database Fallback** - Graceful degradation when OpenSearch is unavailable
- **Automatic Indexing** - Real-time indexing of data changes
- **Tenant Isolation** - Search results isolated per tenant
- **Performance Optimized** - Efficient indexing and querying

## 🏗️ Architecture

### Components

#### Frontend (React)
- `SearchProvider` - Context provider for search state management
- `SearchDialog` - Main search interface using cmdk
- `SearchStatus` - Admin component for monitoring search health
- `AppHeader` - Updated header with search trigger button

#### Backend (FastAPI)
- `SearchService` - Core search functionality with OpenSearch integration
- `SearchIndexer` - Automatic indexing of database changes
- `SearchRouter` - API endpoints for search operations

#### Infrastructure
- **OpenSearch** - Search engine for indexing and querying
- **OpenSearch Dashboards** - Optional UI for search analytics
- **Docker Integration** - Containerized deployment

### Data Flow

1. **Data Changes** → SQLAlchemy events trigger indexing
2. **User Search** → Frontend sends query to API
3. **API Processing** → SearchService queries OpenSearch or database
4. **Results** → Enhanced with URLs and metadata
5. **UI Display** → Results shown in search dialog

## 🔧 Configuration

### Environment Variables

```bash
# OpenSearch Configuration
OPENSEARCH_HOST=opensearch
OPENSEARCH_PORT=9200
OPENSEARCH_ENABLED=true
```

### Docker Services

The system includes OpenSearch services in `docker-compose.yml`:

```yaml
opensearch:
  image: opensearchproject/opensearch:2.11.1
  # ... configuration

opensearch-dashboards:
  image: opensearchproject/opensearch-dashboards:2.11.1
  # ... configuration
```

## 📊 Indexed Data

### Entity Types
- **Invoices** - Number, client name, description, status, amounts
- **Clients** - Name, email, company, address information
- **Payments** - Invoice references, amounts, payment methods
- **Expenses** - Vendor, category, descriptions, amounts
- **Statements** - Bank statements and transaction data
- **Attachments** - File names and associated entity information

### Search Fields
- **Primary Fields** - Names, numbers, descriptions
- **Searchable Text** - Combined searchable content
- **Metadata** - Dates, amounts, statuses, categories
- **Relationships** - Client-invoice associations, payment-invoice links

## 🚀 Usage

### For Users

#### Opening Search
- Press `Cmd+K` (Mac) or `Ctrl+K` (Windows)
- Click the search button in the top-right corner
- Search dialog opens with focus on input field

#### Searching
- Type your search query (minimum 1 character)
- Results appear instantly with debounced queries
- Use arrow keys to navigate results
- Press Enter or click to select a result
- Press Escape to close the dialog

#### Search Tips
- Search across all data types simultaneously
- Use partial matches - "inv" will find "Invoice"
- Search by client names, invoice numbers, amounts
- Results are ranked by relevance

### For Administrators

#### Monitoring Search Health
1. Go to **Settings** → **Search** tab
2. View OpenSearch connection status
3. Check cluster health and node information
4. Monitor search service availability

#### Reindexing Data
1. Use the **Reindex Data** button in Settings
2. Or run the script manually:
   ```bash
   # In Docker
   docker-compose exec api python scripts/reindex_search_data.py
   
   # Or use the shell script
   ./api/scripts/run_reindex_search.sh
   ```

#### Search Status API
```bash
GET /api/v1/search/status
```

Returns search service health information.

## 🔍 API Endpoints

### Global Search
```bash
GET /api/v1/search?q=query&types=invoices,clients&limit=50
```

**Parameters:**
- `q` - Search query (required)
- `types` - Comma-separated entity types (optional)
- `limit` - Maximum results (default: 50, max: 100)

**Response:**
```json
{
  "query": "search term",
  "results": [
    {
      "id": "123",
      "type": "invoices",
      "title": "Invoice INV-001",
      "subtitle": "Client: ABC Corp • $1,500",
      "url": "/invoices/edit/123",
      "score": 1.5,
      "highlights": {},
      "data": { ... }
    }
  ],
  "total": 1,
  "types_searched": ["invoices", "clients"]
}
```

### Search Suggestions
```bash
GET /api/v1/search/suggestions?q=partial&limit=10
```

### Reindex Data
```bash
POST /api/v1/search/reindex
```

Requires admin privileges.

### Search Status
```bash
GET /api/v1/search/status
```

## 🛠️ Development

### Adding New Entity Types

1. **Update SearchService mapping**:
   ```python
   def _get_mapping(self, entity_type: str):
       # Add new entity mapping
   ```

2. **Add indexing methods**:
   ```python
   def index_new_entity(self, entity):
       # Implement indexing logic
   ```

3. **Update SearchIndexer**:
   ```python
   # Add event listeners for new entity
   event.listen(NewEntity, 'after_insert', self._index_new_entity)
   ```

4. **Update search router**:
   ```python
   # Add URL generation logic for new entity type
   ```

### Testing Search

```bash
# Test search functionality
curl "http://localhost:8000/api/v1/search?q=test"

# Test search status
curl "http://localhost:8000/api/v1/search/status"

# Reindex data
curl -X POST "http://localhost:8000/api/v1/search/reindex" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🔧 Troubleshooting

### Common Issues

#### OpenSearch Connection Failed
- Check if OpenSearch container is running
- Verify network connectivity
- Check environment variables
- System falls back to database search automatically

#### Search Results Empty
- Verify data is indexed: check Settings → Search tab
- Run reindexing if needed
- Check tenant context is correct
- Verify user permissions

#### Slow Search Performance
- Check OpenSearch cluster health
- Consider increasing OpenSearch memory
- Review index mappings and queries
- Monitor search query patterns

### Logs and Debugging

```bash
# View search service logs
docker-compose logs api | grep -i search

# View OpenSearch logs
docker-compose logs opensearch

# Check search status
curl "http://localhost:8000/api/v1/search/status"
```

## 📈 Performance Considerations

### Indexing Performance
- Automatic indexing happens on data changes
- Bulk reindexing available for initial setup
- Consider indexing during off-peak hours for large datasets

### Search Performance
- OpenSearch provides sub-second search results
- Database fallback may be slower for large datasets
- Results are limited to prevent performance issues

### Resource Usage
- OpenSearch requires additional memory (512MB minimum)
- Disk space for search indices
- Network bandwidth for search queries

## 🔮 Future Enhancements

### Planned Features
- **Advanced Filters** - Date ranges, amount ranges, status filters
- **Search Analytics** - Track popular searches and performance
- **Saved Searches** - Save and reuse common search queries
- **Search Suggestions** - Auto-complete and query suggestions
- **File Content Search** - Index PDF and document contents
- **Search History** - Recent searches for quick access

### Technical Improvements
- **Search Caching** - Cache frequent search results
- **Index Optimization** - Optimize index structure for performance
- **Multi-language Support** - Support for different languages
- **Search API Rate Limiting** - Prevent search abuse
- **Advanced Analytics** - Search usage analytics and insights

## 📚 References

- [OpenSearch Documentation](https://opensearch.org/docs/)
- [cmdk Library](https://github.com/pacocoursey/cmdk)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Events](https://docs.sqlalchemy.org/en/14/core/events.html)

---

The global search system provides a powerful and user-friendly way to find information across the entire invoice management system, with robust fallback mechanisms and comprehensive monitoring capabilities.