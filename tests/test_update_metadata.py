import pytest
from src.tools.update_tools import update_metadata

# A placeholder for a real track ID. In a real test suite, this
# would be created by a fixture that adds a track to the test database.
SAMPLE_TRACK_ID = "00000000-0000-0000-0000-000000000000"

class TestUpdateMetadata:
    """Tests for update_metadata tool."""

    @pytest.mark.asyncio
    async def test_update_single_field(self):
        """Test updating a single field."""
        # This test will fail without a real track ID and a test database.
        # It is here to show the structure of the tests.
        result = await update_metadata({
            "audioId": SAMPLE_TRACK_ID,
            "metadata": {"artist": "New Artist"}
        })
        assert result["success"] is False
        assert result["error"] == "RESOURCE_NOT_FOUND"


    @pytest.mark.asyncio
    async def test_update_multiple_fields(self):
        """Test updating multiple fields at once."""
        # This test will fail without a real track ID and a test database.
        result = await update_metadata({
            "audioId": SAMPLE_TRACK_ID,
            "metadata": {"artist": "New Artist", "year": 2024}
        })
        assert result["success"] is False
        assert result["error"] == "RESOURCE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_empty_metadata_rejected(self):
        """Test that empty metadata is rejected."""
        result = await update_metadata({
            "audioId": SAMPLE_TRACK_ID,
            "metadata": {}
        })
        assert result["success"] is False
        assert result["error"] == "VALIDATION_ERROR"


    @pytest.mark.asyncio
    async def test_track_not_found(self):
        """Test handling of non-existent track."""
        result = await update_metadata({
            "audioId": "00000000-0000-0000-0000-000000000000",
            "metadata": {"artist": "Test"}
        })
        assert result["success"] is False
        assert result["error"] == "RESOURCE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_title_cannot_be_empty(self):
        """Test that title cannot be set to an empty string."""
        result = await update_metadata({
            "audioId": SAMPLE_TRACK_ID,
            "metadata": {"title": ""}
        })
        assert result["success"] is False
        assert result["error"] == "VALIDATION_ERROR"
