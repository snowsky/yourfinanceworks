from opensearchpy import OpenSearch

class OpenSearchClient:
    def __init__(self, hosts=None):
        if hosts is None:
            hosts = [{"host": "opensearch", "port": 9200}]
        self.client = OpenSearch(hosts=hosts)

    def create_index(self, index_name):
        if not self.client.indices.exists(index=index_name):
            self.client.indices.create(index=index_name)

    def index_document(self, index_name, document, doc_id=None):
        return self.client.index(index=index_name, body=document, id=doc_id, refresh=True)

    def search(self, index_name, query):
        return self.client.search(index=index_name, body=query)
