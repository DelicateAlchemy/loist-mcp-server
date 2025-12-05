# MCP Prompts Documentation

**Date:** December 4, 2025
**Purpose:** Guide users through common workflows using structured templates and examples

---

## Overview

MCP prompts provide guided workflows for common audio library operations. Unlike tools that execute actions, prompts return structured guidance and examples to help users understand and use the available tools effectively.

**Architecture:** Prompts are implemented as `@mcp.prompt()` decorators in `server.py`, alongside the tool definitions.

---

## Available Prompts

### 1. `ingest_from_url` - Audio Ingestion Workflow
**Purpose:** Guide users through the complete audio ingestion process from URL to embeddable player.

**Parameters:**
- `audio_url` (string, optional): Example audio URL to include in guidance

**Returns:** Step-by-step workflow guide including:
- URL preparation requirements
- `process_audio_complete` tool usage with examples
- Expected processing steps and outcomes
- Troubleshooting guidance

**Example Usage:**
```json
{
  "audio_url": "https://example.com/audio.mp3"
}
```

### 2. `search_and_refine` - Library Search Guidance
**Purpose:** Help users construct effective searches with filters, sorting, and pagination.

**Parameters:**
- `query` (string, optional): Example search query
- `genre` (string, optional): Example genre filter
- `year_min` (integer, optional): Minimum year filter
- `year_max` (integer, optional): Maximum year filter

**Returns:** Comprehensive search guide including:
- Basic and advanced search syntax
- Filter combinations and strategies
- Sorting options and pagination
- Search tips and best practices

**Example Usage:**
```json
{
  "query": "classic rock",
  "genre": "Rock",
  "year_min": 1960,
  "year_max": 1980
}
```

### 3. `batch_edit_metadata` - Bulk Metadata Updates
**Purpose:** Guide users through multi-track metadata editing workflows.

**Parameters:**
- `search_query` (string, optional): Example search to find tracks
- `update_field` (string, optional): Example field to update
- `update_value` (string, optional): Example new value

**Returns:** Batch editing workflow guide including:
- Search strategies for targeting tracks
- Individual and batch update patterns
- JSON Merge Patch semantics explanation
- Validation rules and error handling
- Safety best practices

**Example Usage:**
```json
{
  "search_query": "unknown artist",
  "update_field": "artist",
  "update_value": "Corrected Artist Name"
}
```

---

## Prompt Design Principles

### 1. **Workflow-Oriented**
- Prompts focus on complete user journeys
- Guide through multi-step processes
- Provide context and reasoning

### 2. **Tool Orchestration**
- Explain how tools work together
- Show parameter relationships
- Demonstrate common patterns

### 3. **Educational Content**
- Include examples with sample data
- Explain validation rules and constraints
- Provide troubleshooting guidance

### 4. **Template-Based**
- Use placeholders for user-specific values
- Provide copy-paste ready examples
- Include multiple scenario variations

---

## Technical Implementation

### Prompt Structure
```python
@mcp.prompt(name="prompt_name", description="Brief description")
def prompt_function(param1: str = "default") -> list[dict]:
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"""Structured guidance with {{param1}} placeholders..."""
            }
        }
    ]
```

### Message Format
- **Role:** Always `"user"` (prompts provide user guidance)
- **Content Type:** `"text"` (structured markdown/text)
- **Format:** Comprehensive markdown with examples, code blocks, and lists

### Parameter Handling
- **Optional Parameters:** Sensible defaults provided
- **Type Hints:** Full type annotations for clarity
- **Validation:** FastMCP handles parameter validation automatically

---

## Testing and Validation

### Automated Tests
- **Prompt Registration:** `test_mcp_prompts_list()` verifies all 3 prompts are available
- **Prompt Execution:** `test_mcp_prompt_execution()` validates message structure and parameter substitution
- **Content Validation:** Ensures prompts return properly formatted guidance

### Manual Testing (MCP Inspector)
- **Prompts/List:** Verify 3 prompts appear with correct descriptions
- **Prompt Execution:** Test each prompt with different parameters
- **Content Review:** Validate guidance is helpful and accurate

---

## Usage Patterns

### For AI Agents
1. **Discover Prompts:** Call `prompts/list` to see available guidance
2. **Get Specific Help:** Call `prompts/get` with relevant parameters
3. **Follow Guidance:** Use the structured instructions to call appropriate tools
4. **Iterate:** Use prompts to refine complex workflows

### For Human Users
1. **Browse Available Help:** See what guidance topics are available
2. **Get Contextual Help:** Request specific workflow guidance
3. **Copy Examples:** Use provided code examples directly
4. **Learn Patterns:** Understand tool orchestration and best practices

---

## Future Enhancements

### Potential Additions
- **Advanced Filtering:** More sophisticated search and filter guidance
- **Bulk Operations:** Complex multi-track workflows
- **Integration Patterns:** Third-party service integration guides
- **Error Recovery:** Troubleshooting and error handling workflows

### Interactive Prompts
- **Dynamic Content:** Context-aware guidance based on library state
- **Progressive Disclosure:** Step-by-step interactive workflows
- **Feedback Loops:** Learning from successful/failed operations

---

## Integration Notes

### With Tools
- Prompts complement tools by providing usage guidance
- Tools remain the primary execution mechanism
- Prompts never execute actions - only provide guidance

### With MCP Inspector
- Prompts appear in Inspector's prompts section
- Can be executed with parameter customization
- Results display as formatted guidance text

### With Documentation
- Prompts serve as interactive documentation
- Complement static docs with dynamic examples
- Provide up-to-date guidance as tools evolve

---

**Last Updated:** December 4, 2025
**Implementation:** `@mcp.prompt()` decorators in `server.py`
**Testing:** Automated tests + MCP Inspector validation
**Total Prompts:** 3 ✅ All Functional
