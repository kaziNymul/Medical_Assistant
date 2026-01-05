#!/usr/bin/env python3
"""
Test script to verify AWS Bedrock access.
Run this after setting up Bedrock permissions.
"""

import json
import sys

def test_bedrock():
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        print("❌ boto3 not installed. Run: pip install boto3")
        return False
    
    # Use us-east-1 for best Bedrock model availability
    region = "us-east-1"
    
    print("=" * 50)
    print("  AWS Bedrock Connection Test")
    print("=" * 50)
    print()
    
    # Test 1: Can we connect to Bedrock?
    print("1. Testing Bedrock connection...")
    try:
        bedrock = boto3.client("bedrock", region_name=region)
        models = bedrock.list_foundation_models()
        print(f"   ✅ Connected to Bedrock in {region}")
        print(f"   ✅ Found {len(models['modelSummaries'])} foundation models")
    except ClientError as e:
        print(f"   ❌ Cannot connect to Bedrock: {e.response['Error']['Message']}")
        print()
        print("   To fix this, attach 'AmazonBedrockFullAccess' policy to your IAM user")
        return False
    print()
    
    # Test 2: Check specific models we need
    print("2. Checking required models...")
    required_models = {
        "anthropic.claude-3-5-sonnet-20241022-v2:0": "Claude 3.5 Sonnet",
        "anthropic.claude-3-haiku-20240307-v1:0": "Claude 3 Haiku (fallback)",
        "amazon.titan-embed-text-v2:0": "Titan Embeddings V2",
    }
    
    available_models = {m["modelId"] for m in models["modelSummaries"]}
    
    for model_id, name in required_models.items():
        if model_id in available_models or any(model_id.split(":")[0] in m for m in available_models):
            print(f"   ✅ {name} ({model_id.split(':')[0]})")
        else:
            print(f"   ⚠️  {name} - may need to request access")
    print()
    
    # Test 3: Try to invoke a model
    print("3. Testing model invocation...")
    bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)
    
    # Try Claude 3 Haiku first (cheaper and usually faster to get access)
    test_models = [
        "anthropic.claude-3-haiku-20240307-v1:0",
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
    ]
    
    for model_id in test_models:
        try:
            response = bedrock_runtime.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 100,
                    "messages": [
                        {"role": "user", "content": "Say 'Bedrock is working!' in exactly those words."}
                    ]
                })
            )
            result = json.loads(response["body"].read())
            text = result["content"][0]["text"]
            print(f"   ✅ {model_id.split('.')[1].split('-20')[0].title()} responded: {text[:50]}...")
            break
        except ClientError as e:
            error = e.response['Error']
            if "AccessDeniedException" in str(error):
                print(f"   ⚠️  {model_id}: Access denied - request model access in Bedrock console")
            else:
                print(f"   ❌ {model_id}: {error['Message']}")
    print()
    
    # Test 4: Try Titan Embeddings
    print("4. Testing Titan Embeddings...")
    try:
        response = bedrock_runtime.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "inputText": "Test medical embedding",
                "dimensions": 512,
                "normalize": True
            })
        )
        result = json.loads(response["body"].read())
        embedding_dim = len(result["embedding"])
        print(f"   ✅ Titan Embeddings working! Dimension: {embedding_dim}")
    except ClientError as e:
        error = e.response['Error']
        if "AccessDeniedException" in str(error):
            print("   ⚠️  Titan Embeddings: Access denied - request access in Bedrock console")
        else:
            print(f"   ❌ Titan Embeddings: {error['Message']}")
    print()
    
    print("=" * 50)
    print("  Test Complete")
    print("=" * 50)
    print()
    print("Next steps if you see ⚠️ warnings:")
    print("1. Go to: https://console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess")
    print("2. Click 'Manage model access'")
    print("3. Enable Claude and Titan models")
    print("4. Wait 1-2 minutes and re-run this test")
    print()
    
    return True

if __name__ == "__main__":
    success = test_bedrock()
    sys.exit(0 if success else 1)
