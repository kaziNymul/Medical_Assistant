# Phase 2: AWS Bedrock Integration Guide

This guide covers integrating AWS Bedrock for LLM-powered clinical extraction.

## Prerequisites

1. AWS Account with Bedrock access
2. IAM credentials with Bedrock permissions
3. Bedrock model access granted (Claude 3.5 Sonnet, Titan Embeddings)

## Setup

### 1. Install AWS Dependencies

```bash
pip install boto3 langchain-aws
```

### 2. Configure AWS Credentials

Option A: Environment Variables
```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
```

Option B: Update `.env` file
```env
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
LLM_PROVIDER=bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
```

### 3. Request Model Access

In AWS Console:
1. Navigate to Amazon Bedrock
2. Go to Model Access
3. Request access to:
   - Anthropic Claude 3.5 Sonnet
   - Amazon Titan Embeddings V2

## Configuration

Update `config/settings.py` is already configured to support Bedrock.
Just change these settings:

```python
LLM_PROVIDER=bedrock  # Switch from 'local' to 'bedrock'
```

## Code Changes for Phase 2

### Using Bedrock Embeddings

The embeddings module already supports Bedrock:

```python
from src.rag.embeddings import BedrockEmbeddings

embeddings = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0",
    region="us-east-1"
)

# Generate embeddings
vector = embeddings.embed_text("Clinical note text")
```

### Using Claude for Extraction

Create a new LLM client in `src/agents/llm.py`:

```python
import json
import boto3
from config.settings import settings

class BedrockLLM:
    def __init__(self):
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
        )
        self.model_id = settings.bedrock_model_id
    
    def invoke(self, system_prompt: str, user_prompt: str) -> str:
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        })
        
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=body,
        )
        
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
```

### Update ExtractionAgent

Modify `src/agents/nodes.py` to use LLM:

```python
class ExtractionAgent(BaseAgent):
    def __init__(self):
        if settings.llm_provider == "bedrock":
            from src.agents.llm import BedrockLLM
            self.llm = BedrockLLM()
        else:
            self.llm = None
    
    def run(self, state: AgentState) -> AgentState:
        if self.llm:
            return self._llm_extraction(state)
        else:
            return self._rule_based_extraction(state)
    
    def _llm_extraction(self, state: AgentState) -> AgentState:
        from src.agents.prompts import (
            CLINICAL_EXTRACTION_SYSTEM_PROMPT,
            get_extraction_prompt,
        )
        
        prompt = get_extraction_prompt(state.context)
        
        response = self.llm.invoke(
            system_prompt=CLINICAL_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=prompt,
        )
        
        # Parse JSON response
        extraction = json.loads(response)
        state.raw_extraction = extraction
        
        return state
```

## Costs

Estimated costs per 1000 extractions:
- Claude 3.5 Sonnet: ~$5-15 (depends on context size)
- Titan Embeddings: ~$0.10

## Error Handling

Add retry logic for Bedrock API calls:

```python
import time
from botocore.exceptions import ClientError

def invoke_with_retry(self, prompt: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return self.invoke(prompt)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                time.sleep(2 ** attempt)
                continue
            raise
    raise Exception("Max retries exceeded")
```

## Monitoring

Log all Bedrock API calls:

```python
logger.info(
    f"Bedrock call | model={self.model_id} | "
    f"input_tokens={input_tokens} | output_tokens={output_tokens}"
)
```

## Security Notes

1. Never log raw prompts containing patient data
2. Use IAM roles in production (not access keys)
3. Enable CloudTrail for audit logging
4. Consider VPC endpoints for private connectivity

## Testing Phase 2

```bash
# Set environment
export LLM_PROVIDER=bedrock

# Run the server
python -m src.main

# Test extraction
curl -X POST http://localhost:8000/query/extract \
  -H "Content-Type: application/json" \
  -d '{"query": "Extract all clinical information"}'
```

## Rollback

To switch back to Phase 1:
```bash
export LLM_PROVIDER=local
```
