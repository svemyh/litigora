# Weaviate Integration Guide: HTTP Queries with Tool Calling

This guide explains how to query your Weaviate cluster via HTTP and integrate it with LLM tool calling through Make.com webhooks.

## Architecture Overview

```
LLM with Tool Calls → Make.com Webhook → Weaviate HTTP API → Response Chain
```

## 1. Weaviate HTTP Query Structure

Your Weaviate cluster accepts GraphQL queries via HTTP POST:

**Endpoint**: `https://your_project_id.c0.europe-west3.gcp.weaviate.cloud/v1/graphql`

**Headers**:
```json
{
  "Authorization": "Bearer YOUR_WEAVIATE_API_KEY",
  "Content-Type": "application/json"
}
```

**Sample Query Body**:
```json
{
  "query": "{ Get { Documents(nearText: { concepts: [\"GDPR compliance\"] } limit: 4) { filename chunk_index content chunk_id _additional { score } } } }"
}
```

## 2. Make.com Webhook Setup

**Webhook Flow**:
1. **HTTP Webhook Trigger** - Receives tool call from LLM
2. **HTTP Request Module** - Queries Weaviate
3. **Data Processing** - Formats response
4. **HTTP Response** - Returns to LLM

**Sample Make.com HTTP Request Configuration**:
- **URL**: `https://your_project_id.c0.europe-west3.gcp.weaviate.cloud/v1/graphql`
- **Method**: POST
- **Headers**:
  - `Authorization: Bearer your_api_key`
  - `Content-Type: application/json`
- **Body**: Dynamic GraphQL query based on webhook input

## 3. Tool Call Function Schema

```json
{
  "name": "search_legal_documents",
  "description": "Search through the most critical GDPR and EU legal documents (namely the following three documents: EU AI Act (Regulation 2024/1689), GDPR (Regulation 2016/679), EU Data Act (Regulation 2023/2854) - APPLIES SEPTEMBER 12, 2025) for specific information. Returns top 4 most relevant results.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "The search query or legal concept to find"
      }
    },
    "required": ["query"]
  }
}
```

## 4. Implementation Steps

### Step 1: Create Make.com Scenario
1. Add HTTP Webhook trigger
2. Add HTTP Request module with Weaviate configuration
3. Add data transformation modules
4. Test with sample queries

### Step 2: GraphQL Query Templates
Create dynamic queries in Make.com:

**Basic Search** (hardcoded to 4 results):
```graphql
{
  Get {
    Documents(
      nearText: { concepts: ["{{query}}"] }
      limit: 4
    ) {
      filename
      chunk_index
      content
      chunk_id
      _additional { score }
    }
  }
}
```

**Filtered Search** (by document, 4 results):
```graphql
{
  Get {
    Documents(
      nearText: { concepts: ["{{query}}"] }
      where: { path: ["filename"], operator: Equal, valueText: "{{filename}}" }
      limit: 4
    ) {
      filename
      content
      _additional { score }
    }
  }
}
```

### Step 3: Response Processing
Format Weaviate response in Make.com:
```json
{
  "results": [
    {
      "document": "{{filename}}",
      "relevance_score": "{{score}}",
      "content": "{{content}}",
      "source": "chunk_{{chunk_index}}"
    }
  ],
  "query": "{{original_query}}",
  "total_found": "{{results_count}}"
}
```

### Step 4: LLM Integration
Configure your LLM to call the webhook:

**Tool Call Example**:
```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_legal_documents",
            "description": "Search GDPR and EU legal documents",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 4}
                },
                "required": ["query"]
            }
        }
    }
]
```

## 5. Advanced Features

### Hybrid Search (Vector + Keyword)
```graphql
{
  Get {
    Documents(
      hybrid: {
        query: "{{query}}"
        alpha: 0.7
      }
      limit: {{limit}}
    ) {
      filename
      content
      _additional { score }
    }
  }
}
```

### Generative Search (RAG)
```graphql
{
  Get {
    Documents(
      nearText: { concepts: ["{{query}}"] }
      limit: 4
    ) {
      filename
      content
      _additional {
        generate(
          singleResult: {
            prompt: "Based on this legal text: {content}, answer: {{query}}"
          }
        ) {
          singleResult
        }
      }
    }
  }
}
```

## 6. Testing Commands

**Direct HTTP Test**:
```bash
curl -X POST \
  https://your_project_id.c0.europe-west3.gcp.weaviate.cloud/v1/graphql \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ Get { Documents(nearText: { concepts: [\"data protection\"] } limit: 4) { filename content _additional { score } } } }"}'
```

## 7. Make.com Scenario Configuration

### Webhook Trigger Setup
1. Create new scenario in Make.com
2. Add "Webhooks" > "Custom webhook" as trigger
3. Copy webhook URL for LLM integration

### HTTP Module Configuration
1. Add "HTTP" > "Make a request" module
2. Configure as follows:
   - **URL**: `https://your_project_id.c0.europe-west3.gcp.weaviate.cloud/v1/graphql`
   - **Method**: POST
   - **Headers**:
     ```
     Authorization: Bearer YOUR_WEAVIATE_API_KEY
     Content-Type: application/json
     ```
   - **Body Type**: Raw
   - **Content Type**: JSON (application/json)
   - **Request Content**:
     ```json
     {
       "query": "{ Get { Documents(nearText: { concepts: [\"{{1.query}}\"] } limit: {{1.limit}}) { filename chunk_index content chunk_id _additional { score } } } }"
     }
     ```

### Response Processing
1. Add "Tools" > "Set variable" to format response
2. Parse JSON response from Weaviate
3. Transform to desired output format

## 8. Error Handling

### Common Issues
- **401 Unauthorized**: Check API key format
- **400 Bad Request**: Validate GraphQL syntax
- **Rate Limiting**: Implement retry logic in Make.com

### Debug Steps
1. Test GraphQL query directly with curl
2. Validate Make.com HTTP module configuration
3. Check webhook payload format
4. Monitor Make.com execution logs

## 9. Security Considerations

- Store API keys securely in Make.com
- Use HTTPS for all communications
- Implement request validation
- Consider rate limiting on webhook endpoints

This architecture provides a robust pipeline from LLM tool calls through Make.com to your vectorized legal documents, enabling intelligent document search and retrieval.