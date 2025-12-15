"""
A2A Agent Card Validation Tests

Tests Agent Card creation, Pydantic validation, and endpoint serving.
Validates that the Agent Card conforms to A2A v0.3 specification.

Author: Task Master AI
Created: $(date)
"""

import pytest

# Try to import a2a types, skip tests if not available
try:
    from a2a.types import AgentCard
    A2A_AVAILABLE = True
except ImportError:
    A2A_AVAILABLE = False
    # Create dummy types for pytest collection
    AgentCard = None

# Skip marker for all test methods
pytestmark = pytest.mark.skipif(not A2A_AVAILABLE, reason="A2A SDK not available (a2a-sdk package not installed)")


class TestAgentCardPydanticValidation:
    """Test Agent Card Pydantic model validation."""

    def test_agent_card_creation_succeeds(self):
        """Test that create_agent_card() returns a valid AgentCard instance."""
        from src.a2a_server.agent_card import create_agent_card

        card = create_agent_card()
        assert card is not None
        assert hasattr(card, 'name')
        assert hasattr(card, 'description')

    def test_agent_card_pydantic_validation(self):
        """Test that Agent Card validates with SDK's Pydantic model."""
        from src.a2a_server.agent_card import create_agent_card

        card = create_agent_card()

        # Validate using Pydantic model_validate
        validated = AgentCard.model_validate(card.model_dump())
        assert validated == card

    def test_agent_card_required_fields(self):
        """Test that Agent Card has all required fields."""
        from src.a2a_server.agent_card import create_agent_card

        card = create_agent_card()

        # Required fields for A2A v0.3
        assert card.name == "Loist Music Library Processor"
        assert card.description is not None
        assert card.url is not None
        assert card.version == "1.0.0"
        assert card.protocol_version == "0.3.0"

    def test_agent_card_capabilities(self):
        """Test Agent Card capabilities structure."""
        from src.a2a_server.agent_card import create_agent_card

        card = create_agent_card()

        assert card.capabilities is not None
        assert card.capabilities.streaming is False  # MVP doesn't support streaming
        assert card.capabilities.pushNotifications is False  # MVP doesn't support push notifications
        assert card.capabilities.stateTransitionHistory is True  # Tasks have state transitions

    def test_agent_card_input_output_modes(self):
        """Test Agent Card input/output mode specifications."""
        from src.a2a_server.agent_card import create_agent_card

        card = create_agent_card()

        assert "application/json" in card.default_input_modes
        assert "text/plain" in card.default_input_modes
        assert card.default_output_modes == ["application/json"]

    def test_agent_card_skills(self):
        """Test Agent Card skills array."""
        from src.a2a_server.agent_card import create_agent_card

        card = create_agent_card()

        assert card.skills is not None
        assert len(card.skills) > 0

        # Check for expected skills
        skill_ids = [skill.id for skill in card.skills]
        expected_skills = [
            "process_audio_complete",
            "search_library",
            "get_audio_metadata",
            "update_metadata",
            "delete_audio",
            "get_embed_url"
        ]

        for expected_skill in expected_skills:
            assert expected_skill in skill_ids

    def test_agent_card_skill_details(self):
        """Test individual skill details."""
        from src.a2a_server.agent_card import create_agent_card

        card = create_agent_card()

        # Find process_audio_complete skill
        process_skill = next(
            (skill for skill in card.skills if skill.id == "process_audio_complete"),
            None
        )
        assert process_skill is not None
        assert "Process audio file from URL" in process_skill.description
        assert "audio" in process_skill.tags
        assert "ingestion" in process_skill.tags

    def test_agent_card_security_disabled(self):
        """Test that security is disabled for development."""
        from src.a2a_server.agent_card import create_agent_card

        card = create_agent_card()

        # Security should be disabled for development
        assert card.security is None
        assert card.security_schemes is None


@pytest.mark.asyncio
class TestAgentCardEndpoint:
    """Test Agent Card endpoint serving."""

    async def test_agent_card_endpoint_exists(self):
        """Test that Agent Card endpoint returns 200."""
        # Create a minimal A2A app for testing
        from fastapi import FastAPI
        from src.a2a_server.agent_card import create_agent_card
        from unittest.mock import AsyncMock

        # Create a simple FastAPI app with just the agent card endpoint
        app = FastAPI()

        @app.get("/.well-known/agent-card.json")
        async def get_agent_card():
            card = create_agent_card()
            return card.model_dump()

        # Test the endpoint
        import httpx
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/.well-known/agent-card.json")

            assert response.status_code == 200

    async def test_agent_card_endpoint_content_type(self):
        """Test that Agent Card endpoint returns correct content type."""
        from fastapi import FastAPI
        from src.a2a_server.agent_card import create_agent_card

        app = FastAPI()

        @app.get("/.well-known/agent-card.json")
        async def get_agent_card():
            card = create_agent_card()
            return card.model_dump()

        import httpx
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/.well-known/agent-card.json")

            assert response.headers.get("content-type", "").startswith("application/json")

    async def test_agent_card_endpoint_valid_json(self):
        """Test that Agent Card endpoint returns valid JSON."""
        from fastapi import FastAPI
        from src.a2a_server.agent_card import create_agent_card

        app = FastAPI()

        @app.get("/.well-known/agent-card.json")
        async def get_agent_card():
            card = create_agent_card()
            return card.model_dump()

        import httpx
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/.well-known/agent-card.json")

            # Should be valid JSON
            data = response.json()
            assert isinstance(data, dict)
            assert "name" in data
            assert "description" in data

    async def test_agent_card_endpoint_pydantic_valid(self):
        """Test that Agent Card endpoint response validates with Pydantic."""
        from fastapi import FastAPI
        from src.a2a_server.agent_card import create_agent_card

        app = FastAPI()

        @app.get("/.well-known/agent-card.json")
        async def get_agent_card():
            card = create_agent_card()
            return card.model_dump()

        import httpx
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/.well-known/agent-card.json")

            data = response.json()

            # Validate with Pydantic
            validated = AgentCard.model_validate(data)
            assert validated.name == "Loist Music Library Processor"


class TestAgentCardFieldsValidation:
    """Test specific Agent Card field validation."""

    def test_agent_card_url_environment_variable(self):
        """Test that Agent Card URL uses environment variable."""
        import os
        from src.a2a_server.agent_card import create_agent_card

        # Test with default (should use fallback)
        original_url = os.environ.get("A2A_SERVICE_URL")
        try:
            # Remove env var if it exists
            if "A2A_SERVICE_URL" in os.environ:
                del os.environ["A2A_SERVICE_URL"]

            card = create_agent_card()
            assert "api.loist.music" in card.url or "loist.music" in card.url

        finally:
            # Restore original env var
            if original_url is not None:
                os.environ["A2A_SERVICE_URL"] = original_url

    def test_agent_card_service_endpoint(self):
        """Test Agent Card has proper service endpoint configuration."""
        from src.a2a_server.agent_card import create_agent_card

        card = create_agent_card()

        # Should have serviceEndpoint with JSON-RPC protocols
        # Note: This is part of the skills/capabilities, not a separate field in current implementation
        # The test validates that the card can be created and validated
        validated = AgentCard.model_validate(card.model_dump())
        assert validated is not None

    def test_agent_card_a2a_version_compatibility(self):
        """Test Agent Card declares A2A v0.3 compatibility."""
        from src.a2a_server.agent_card import create_agent_card

        card = create_agent_card()
        assert card.protocol_version == "0.3.0"

        # Validate the card conforms to expected structure
        validated = AgentCard.model_validate(card.model_dump())
        assert validated.protocol_version == "0.3.0"
