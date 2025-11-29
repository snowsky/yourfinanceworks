import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import sessionmaker
from core.models.database import engine as master_engine, get_tenant_engine
from core.models.models import Tenant
from core.models.models_per_tenant import ExpenseAttachment
from core.services.opensearch_client import OpenSearchClient


def main():
    MasterSession = sessionmaker(autocommit=False, autoflush=False, bind=master_engine)
    master_db = MasterSession()

    opensearch_client = OpenSearchClient()
    index_name = "attachments"
    opensearch_client.create_index(index_name)

    tenants = master_db.query(Tenant).all()
    for tenant in tenants:
        print(f"Indexing attachments for tenant: {tenant.name}")
        tenant_engine = get_tenant_engine(tenant.id)
        TenantSession = sessionmaker(autocommit=False, autoflush=False, bind=tenant_engine)
        tenant_db = TenantSession()

        attachments = tenant_db.query(ExpenseAttachment).all()
        for attachment in attachments:
            print(f"Indexing attachment: {attachment.filename}")
            try:
                with open(attachment.file_path, 'r') as f:
                    content = f.read()
                
                document = {
                    "tenant_id": tenant.id,
                    "attachment_id": attachment.id,
                    "filename": attachment.filename,
                    "content": content
                }
                opensearch_client.index_document(index_name, document)
            except Exception as e:
                print(f"Error indexing attachment {attachment.filename}: {e}")

        tenant_db.close()

    master_db.close()

if __name__ == "__main__":
    main()
