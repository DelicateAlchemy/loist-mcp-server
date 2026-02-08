# tests/test_mcp_protocol.py

import pytest
from fastmcp import Client

@pytest.mark.asyncio
async def test_mcp_handshake():
    """Test the MCP handshake (initialize -> initialized)"""
    async with Client("http://localhost:8080/mcp") as client:
        assert client.is_connected()
        init_result = client.initialize_result
        assert init_result is not None
        assert init_result.serverInfo is not None
        assert init_result.serverInfo.name == "Music Library MCP"

@pytest.mark.asyncio
async def test_mcp_tools_list():
    """Test the tools/list method"""
    async with Client("http://localhost:8080/mcp") as client:
        tools = await client.list_tools()
        assert len(tools) == 12

@pytest.mark.asyncio
async def test_mcp_tools_call_health_check():
    """Test the tools/call method for health_check tool (happy path)"""
    async with Client("http://localhost:8080/mcp") as client:
        result = await client.call_tool("health_check", {})
        # Extract the actual data from CallToolResult
        data = result.data
        assert isinstance(data, dict)
        # Status can be "healthy" or "degraded" - both are valid happy path responses
        assert data["status"] in ["healthy", "degraded"]
        assert "service" in data
        assert "version" in data
        assert "database" in data
        assert "gcs" in data
        assert "cloud_tasks" in data
        # Verify database and GCS are available (core services)
        assert data["database"]["available"] is True
        assert data["gcs"]["available"] is True

@pytest.mark.asyncio
async def test_mcp_tools_call_invalid_tool():
    """Test the tools/call method error handling for invalid tool"""
    async with Client("http://localhost:8080/mcp") as client:
        # Attempt to call a non-existent tool
        with pytest.raises(Exception) as exc_info:
            await client.call_tool("non_existent_tool", {})

        # FastMCP should raise an exception for invalid tool calls
        # The exact exception type depends on how FastMCP handles MCP errors
        assert exc_info.value is not None
        # Error message should indicate the tool is not found
        error_msg = str(exc_info.value).lower()
        assert any(keyword in error_msg for keyword in ["not found", "invalid", "unknown", "does not exist"])

@pytest.mark.asyncio
async def test_mcp_tools_call_process_audio_complete():
    """Test the tools/call method for process_audio_complete tool"""
    async with Client("http://localhost:8080/mcp") as client:
        # Call process_audio_complete with test audio URL
        result = await client.call_tool("process_audio_complete", {
            "source": {
                "type": "http_url",
                "url": "https://tmpfiles.org/dl/13699668/bam_bam-al186_005_big_air_main_echoic_bam_music_limited.mp3"
            }
        })

        # Extract the actual data from CallToolResult
        data = result.data
        assert isinstance(data, dict)

        # Check for required fields in response
        assert "audio_id" in data
        assert "metadata" in data
        assert "resources" in data

        # Validate audio_id format (should be UUID)
        import uuid
        assert uuid.UUID(data["audio_id"])

        # Validate metadata structure
        metadata = data["metadata"]
        assert "product" in metadata

        # Check product metadata has expected fields
        product = metadata["product"]
        assert "title" in product
        assert "artist" in product

        # Validate resources contains URLs
        resources = data["resources"]
        assert "audio_url" in resources
        assert "thumbnail_url" in resources

        # URLs should be valid music-library:// scheme URLs
        assert resources["audio_url"].startswith("music-library://")
        assert resources["thumbnail_url"].startswith("music-library://")

        # Check for embed URL in metadata
        assert "url_embed_link" in metadata
        assert metadata["url_embed_link"].startswith("https://")

@pytest.mark.asyncio
async def test_mcp_tools_call_search_library():
    """Test the tools/call method for search_library tool"""
    async with Client("http://localhost:8080/mcp") as client:
        # Search for tracks (should find at least the one we just processed)
        result = await client.call_tool("search_library", {
            "query": "Bam",
            "limit": 10
        })

        # Extract the actual data from CallToolResult
        data = result.data
        assert isinstance(data, dict)

        # Check for required fields in response
        assert "results" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

        # Results should be a list
        assert isinstance(data["results"], list)

        # Total should be a non-negative integer
        assert isinstance(data["total"], int)
        assert data["total"] >= 0

        # Limit and offset should match request
        assert data["limit"] == 10
        assert data["offset"] == 0

        # If we have results, validate their structure
        if len(data["results"]) > 0:
            first_result = data["results"][0]
            assert isinstance(first_result, dict)

            # Each result should have expected fields
            assert "audio_id" in first_result
            assert "metadata" in first_result
            assert "score" in first_result

            # Validate audio_id format (should be UUID)
            import uuid
            assert uuid.UUID(first_result["audio_id"])

            # Validate metadata structure
            metadata = first_result["metadata"]
            assert "product" in metadata

            # Check product metadata has expected fields
            product = metadata["product"]
            assert "title" in product
            assert "artist" in product

            # Check for embed URL in metadata
            assert "url_embed_link" in metadata
            assert metadata["url_embed_link"].startswith("https://")

            # Score should be a number between 0 and 1
            assert isinstance(first_result["score"], (int, float))
            assert 0 <= first_result["score"] <= 1

@pytest.mark.asyncio
async def test_mcp_tools_call_update_metadata():
    """Test the tools/call method for update_metadata tool"""
    async with Client("http://localhost:8080/mcp") as client:
        # First search to get an audio_id to update
        search_result = await client.call_tool("search_library", {
            "query": "Bam",
            "limit": 1
        })
        search_data = search_result.data
        assert len(search_data["results"]) > 0
        audio_id = search_data["results"][0]["audio_id"]

        # Update metadata for the track
        result = await client.call_tool("update_metadata", {
            "audio_id": audio_id,
            "metadata": {
                "artist": "Updated Artist Name",
                "genre": "Updated Genre"
            }
        })

        # Extract the actual data from CallToolResult
        data = result.data
        assert isinstance(data, dict)

        # Check for required fields in response
        assert "success" in data
        assert "audio_id" in data
        assert "updated_fields" in data

        # Should be successful
        assert data["success"] is True

        # Audio ID should match what we updated
        assert data["audio_id"] == audio_id

        # Updated fields should include what we changed
        assert "artist" in data["updated_fields"]
        assert "genre" in data["updated_fields"]

        # Verify the update by searching again
        verify_result = await client.call_tool("search_library", {
            "query": "Updated Artist Name",
            "limit": 1
        })
        verify_data = verify_result.data
        assert len(verify_data["results"]) > 0
        updated_track = verify_data["results"][0]
        assert updated_track["metadata"]["product"]["artist"] == "Updated Artist Name"

@pytest.mark.asyncio
async def test_mcp_tools_call_delete_audio():
    """Test the tools/call method for delete_audio tool"""
    async with Client("http://localhost:8080/mcp") as client:
        # First search to get an audio_id to delete
        search_result = await client.call_tool("search_library", {
            "query": "Updated Artist Name",
            "limit": 1
        })
        search_data = search_result.data
        assert len(search_data["results"]) > 0
        audio_id = search_data["results"][0]["audio_id"]

        # Delete the audio track
        result = await client.call_tool("delete_audio", {
            "audio_id": audio_id
        })

        # Extract the actual data from CallToolResult
        data = result.data
        assert isinstance(data, dict)

        # Check for required fields in response
        assert "deleted" in data
        assert "audio_id" in data

        # Should be successful
        assert data["deleted"] is True
        assert data["audio_id"] == audio_id

        # Verify the deletion by searching - should not find the track
        verify_result = await client.call_tool("search_library", {
            "query": audio_id,
            "limit": 1
        })
        verify_data = verify_result.data
        # Should not find the deleted track
        assert len(verify_data["results"]) == 0

@pytest.mark.asyncio
async def test_mcp_prompts_list():
    """Test the prompts/list method returns the 3 implemented prompts"""
    async with Client("http://localhost:8080/mcp") as client:
        prompts = await client.list_prompts()
        assert isinstance(prompts, list)
        assert len(prompts) == 3

        # Check that expected prompts are present
        prompt_names = [prompt.name for prompt in prompts]
        expected_prompts = ["ingest_from_url", "search_and_refine", "batch_edit_metadata"]

        for expected_prompt in expected_prompts:
            assert expected_prompt in prompt_names

        # Validate prompt structure
        for prompt in prompts:
            assert hasattr(prompt, 'name')
            assert hasattr(prompt, 'description')
            assert prompt.name in expected_prompts
            assert isinstance(prompt.description, str)
            assert len(prompt.description) > 0

@pytest.mark.asyncio
async def test_mcp_prompt_execution():
    """Test executing prompts to ensure they return valid message structures"""
    async with Client("http://localhost:8080/mcp") as client:
        # Test ingest_from_url prompt
        result = await client.get_prompt("ingest_from_url", {"audio_url": "https://example.com/test.mp3"})
        messages = result.messages
        assert isinstance(messages, list)
        assert len(messages) > 0

        # Validate message structure
        message = messages[0]
        assert hasattr(message, 'role')
        assert hasattr(message, 'content')
        assert message.role == "user"
        assert hasattr(message.content, 'type')
        assert message.content.type == "text"
        assert "https://example.com/test.mp3" in message.content.text  # Should contain our parameter

        # Test search_and_refine prompt
        result = await client.get_prompt("search_and_refine", {"query": "test artist"})
        messages = result.messages
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert "test artist" in messages[0].content.text

        # Test batch_edit_metadata prompt
        result = await client.get_prompt("batch_edit_metadata", {"search_query": "test query"})
        messages = result.messages
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert "test query" in messages[0].content.text

@pytest.mark.asyncio
async def test_mcp_resources_list():
    """Test the resources/list method returns empty (by design)"""
    async with Client("http://localhost:8080/mcp") as client:
        resources = await client.list_resources()
        assert isinstance(resources, list)
        assert len(resources) == 0
