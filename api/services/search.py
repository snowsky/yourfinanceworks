from .opensearch_client import OpenSearchClient

class SearchService:
    def __init__(self):
        self.opensearch_client = OpenSearchClient()
        self.index_name = "attachments"

    def search(self, q: str):
        query = {
            "query": {
                "match": {
                    "content": q
                }
            }
        }
        response = self.opensearch_client.search(self.index_name, query)
        
        results = []
        for hit in response["hits"]["hits"]:
            results.append({
                "id": hit["_id"],
                "title": hit["_source"]["filename"],
                "url": f"/attachments/{hit['_source']['attachment_id']}"
            })
        
        return results
