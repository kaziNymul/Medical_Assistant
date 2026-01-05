#!/usr/bin/env python3
"""
Test Databricks Connection.

Verifies:
1. Connection to Databricks workspace
2. User authentication
3. Cluster/warehouse availability
"""

import os
import sys

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_connection():
    """Test Databricks connection."""
    print("=" * 50)
    print("  Databricks Connection Test")
    print("=" * 50)
    print()
    
    # Try to get credentials from Vault first
    host = None
    token = None
    
    try:
        vault_addr = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
        vault_token = os.getenv("VAULT_TOKEN", "dev-token-medical")
        
        import hvac
        client = hvac.Client(url=vault_addr, token=vault_token)
        if client.is_authenticated():
            response = client.secrets.kv.v2.read_secret_version(
                path="medical-assistant",
                mount_point="secret"
            )
            secrets = response["data"]["data"]
            host = secrets.get("DATABRICKS_HOST")
            token = secrets.get("DATABRICKS_TOKEN")
            print("✅ Loaded credentials from Vault")
        else:
            print("⚠️  Vault not authenticated, using env vars")
    except Exception as e:
        print(f"⚠️  Vault not available: {e}")
    
    # Fall back to env vars
    if not host:
        host = os.getenv("DATABRICKS_HOST")
        token = os.getenv("DATABRICKS_TOKEN")
    
    if not host or not token:
        print("❌ No Databricks credentials found!")
        print("   Set DATABRICKS_HOST and DATABRICKS_TOKEN environment variables")
        return False
    
    print(f"\n1. Testing connection to: {host}")
    
    try:
        from databricks.sdk import WorkspaceClient
        
        client = WorkspaceClient(host=host, token=token)
        user = client.current_user.me()
        
        print(f"   ✅ Connected as: {user.user_name}")
        print(f"   ✅ Display name: {user.display_name}")
        
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return False
    
    # Check clusters
    print("\n2. Checking clusters...")
    try:
        clusters = list(client.clusters.list())
        if clusters:
            for c in clusters[:5]:
                state = str(c.state) if c.state else "UNKNOWN"
                print(f"   • {c.cluster_name}: {state}")
        else:
            print("   ⚠️  No clusters found (normal for Community Edition)")
    except Exception as e:
        print(f"   ⚠️  Could not list clusters: {e}")
    
    # Check SQL warehouses
    print("\n3. Checking SQL warehouses...")
    try:
        warehouses = list(client.warehouses.list())
        if warehouses:
            for w in warehouses[:5]:
                state = str(w.state) if w.state else "UNKNOWN"
                print(f"   • {w.name}: {state}")
        else:
            print("   ⚠️  No SQL warehouses (Community Edition limitation)")
            print("   📝 Note: Tables will be managed via notebooks in Community Edition")
    except Exception as e:
        print(f"   ⚠️  Could not list warehouses: {e}")
    
    # Summary
    print()
    print("=" * 50)
    print("  Connection Test Complete")
    print("=" * 50)
    print()
    print("Next steps for Phase 3:")
    print("1. Create a cluster in Databricks UI")
    print("2. Upload notebooks for data processing")
    print("3. Set up Delta tables for Bronze/Silver/Gold layers")
    print()
    
    return True


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
