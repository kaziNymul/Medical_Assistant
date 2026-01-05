#!/usr/bin/env python3
"""
Phase 3 Integration Test

Tests the complete system with all components:
1. ✅ Vault (Secrets Management)
2. ✅ AWS Bedrock (LLM + Embeddings)
3. ✅ Databricks (Logging + Monitoring)
4. ✅ Full RAG Query Pipeline
"""

import os
import sys
import time
import json

# Set environment
os.environ.setdefault("VAULT_ADDR", "http://127.0.0.1:8200")
os.environ.setdefault("VAULT_TOKEN", "dev-token-medical")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(name: str, success: bool, details: str = ""):
    icon = "✅" if success else "❌"
    print(f"   {icon} {name}: {details}")


def test_vault():
    """Test Vault connection."""
    print_header("1. VAULT (Secrets Management)")
    
    try:
        import hvac
        client = hvac.Client(
            url=os.environ["VAULT_ADDR"],
            token=os.environ["VAULT_TOKEN"]
        )
        
        if not client.is_authenticated():
            print_result("Vault Auth", False, "Not authenticated")
            return False
        
        print_result("Vault Auth", True, "Authenticated")
        
        # Get secrets
        response = client.secrets.kv.v2.read_secret_version(
            path="medical-assistant",
            mount_point="secret",
            raise_on_deleted_version=False,
        )
        secrets = response.get("data", {}).get("data", {})
        
        print_result("Secrets Loaded", True, f"{len(secrets)} secrets found")
        
        # Check required secrets
        required = ["AWS_ACCESS_KEY_ID", "DATABRICKS_HOST", "DATABRICKS_TOKEN"]
        for key in required:
            has_key = key in secrets
            print_result(f"  {key}", has_key, "Present" if has_key else "Missing")
        
        return True
        
    except Exception as e:
        print_result("Vault", False, str(e))
        return False


def test_bedrock():
    """Test AWS Bedrock connection."""
    print_header("2. AWS BEDROCK (LLM + Embeddings)")
    
    try:
        import boto3
        
        # Create Bedrock client
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        
        # Test Claude Haiku
        print("\n   Testing Claude 3 Haiku...")
        start = time.time()
        
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 100,
                "messages": [
                    {"role": "user", "content": "What is hypertension? Reply in one sentence."}
                ]
            })
        )
        
        result = json.loads(response["body"].read())
        latency = (time.time() - start) * 1000
        answer = result["content"][0]["text"]
        
        print_result("Claude Haiku", True, f"{latency:.0f}ms")
        print(f"      Response: {answer[:80]}...")
        
        # Test Titan Embeddings
        print("\n   Testing Titan Embeddings...")
        start = time.time()
        
        response = bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "inputText": "Patient has diabetes and hypertension",
                "dimensions": 512,
            })
        )
        
        result = json.loads(response["body"].read())
        latency = (time.time() - start) * 1000
        embedding = result["embedding"]
        
        print_result("Titan Embeddings", True, f"{latency:.0f}ms, dim={len(embedding)}")
        
        return True
        
    except Exception as e:
        print_result("Bedrock", False, str(e))
        return False


def test_databricks():
    """Test Databricks connection."""
    print_header("3. DATABRICKS (Logging + Monitoring)")
    
    try:
        from databricks.sdk import WorkspaceClient
        import hvac
        
        # Get credentials from Vault
        client = hvac.Client(
            url=os.environ["VAULT_ADDR"],
            token=os.environ["VAULT_TOKEN"]
        )
        response = client.secrets.kv.v2.read_secret_version(
            path="medical-assistant",
            mount_point="secret",
            raise_on_deleted_version=False,
        )
        secrets = response.get("data", {}).get("data", {})
        
        # Connect to Databricks
        ws = WorkspaceClient(
            host=secrets["DATABRICKS_HOST"],
            token=secrets["DATABRICKS_TOKEN"]
        )
        
        user = ws.current_user.me()
        print_result("Databricks Auth", True, f"User: {user.user_name}")
        
        # Check warehouses
        warehouses = list(ws.warehouses.list())
        print_result("SQL Warehouses", True, f"{len(warehouses)} found")
        for w in warehouses[:3]:
            print(f"      • {w.name}: {w.state}")
        
        return True
        
    except Exception as e:
        print_result("Databricks", False, str(e))
        return False


def test_rag_pipeline():
    """Test the RAG pipeline with Bedrock."""
    print_header("4. RAG PIPELINE (Full Query)")
    
    try:
        import requests
        
        # First, check if we have documents
        print("\n   Checking vector store...")
        response = requests.get("http://localhost:8000/documents/stats", timeout=10)
        
        if response.status_code == 200:
            stats = response.json()
            doc_count = stats.get("total_chunks", 0)
            print_result("Vector Store", True, f"{doc_count} chunks indexed")
        else:
            print_result("Vector Store", False, "Could not get stats")
        
        # Test a clinical query
        print("\n   Testing clinical query...")
        
        query = {
            "query": "Patient presented with fever and cough. Temperature 101.5F. Diagnosis: Upper respiratory infection. Prescribed amoxicillin 500mg.",
        }
        
        start = time.time()
        response = requests.post(
            "http://localhost:8000/query/extract",
            json=query,
            timeout=60
        )
        latency = (time.time() - start) * 1000
        
        if response.status_code == 200:
            result = response.json()
            
            # Handle extraction response
            extraction = result.get("extraction", {})
            if extraction:
                diagnoses = extraction.get("diagnoses", [])
                medications = extraction.get("medications", [])
                print_result("Query Executed", True, f"{latency:.0f}ms")
                print(f"      Diagnoses: {diagnoses}")
                print(f"      Medications: {medications}")
            else:
                answer = str(result)[:150]
                print_result("Query Executed", True, f"{latency:.0f}ms")
                print(f"      Response: {answer}...")
            
            # Check if Bedrock was used
            model = result.get("model", result.get("llm_provider", "unknown"))
            print_result("Model Used", True, model)
            
            return True
        else:
            print_result("Query", False, f"Status {response.status_code}")
            return False
            
    except Exception as e:
        print_result("RAG Pipeline", False, str(e))
        return False


def test_ai_logging():
    """Test AI logging to Databricks."""
    print_header("5. AI LOGGING (Query Tracking)")
    
    try:
        import requests
        
        # Get AI logs
        response = requests.get("http://localhost:8000/databricks/logs?limit=10", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            logs = data.get("logs", [])
            stats = data.get("stats", {})
            
            print_result("Logs Retrieved", True, f"{len(logs)} entries")
            print(f"      Total queries: {stats.get('total_queries', 0)}")
            print(f"      Total cost: ${stats.get('total_cost_usd', 0):.4f}")
            print(f"      Avg latency: {stats.get('avg_latency_ms', 0):.0f}ms")
            
            return True
        else:
            print_result("Logging", False, f"Status {response.status_code}")
            return False
            
    except Exception as e:
        print_result("AI Logging", False, str(e))
        return False


def test_frontend():
    """Test frontend availability."""
    print_header("6. FRONTEND (React UI)")
    
    try:
        import requests
        
        # Check frontend
        for port in [3000, 3001, 3002]:
            try:
                response = requests.get(f"http://localhost:{port}/", timeout=2)
                if response.status_code == 200:
                    print_result("Frontend", True, f"Running on port {port}")
                    print(f"      URL: http://localhost:{port}")
                    return True
            except:
                continue
        
        print_result("Frontend", False, "Not running on ports 3000-3002")
        return False
        
    except Exception as e:
        print_result("Frontend", False, str(e))
        return False


def main():
    print("\n" + "=" * 60)
    print("  PHASE 3 INTEGRATION TEST")
    print("  AI Clinical Documentation Assistant")
    print("=" * 60)
    
    results = {}
    
    # Run all tests
    results["vault"] = test_vault()
    results["bedrock"] = test_bedrock()
    results["databricks"] = test_databricks()
    results["rag"] = test_rag_pipeline()
    results["logging"] = test_ai_logging()
    results["frontend"] = test_frontend()
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\n   Passed: {passed}/{total} tests")
    print()
    
    for name, success in results.items():
        icon = "✅" if success else "❌"
        status = "PASS" if success else "FAIL"
        print(f"   {icon} {name.upper()}: {status}")
    
    print()
    
    if passed == total:
        print("   🎉 ALL TESTS PASSED! Phase 3 is fully operational.")
    elif passed >= 4:
        print("   ⚠️  Most tests passed. Check failed components.")
    else:
        print("   ❌ Multiple failures. Review configuration.")
    
    print()
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
