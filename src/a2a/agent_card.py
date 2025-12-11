"""A2A Agent Card configuration for Loist Music Library Processor."""

from a2a.types import AgentCard, AgentSkill, AgentCapabilities


def create_agent_card() -> AgentCard:
    """Create the A2A Agent Card for agent discovery.

    Returns:
        AgentCard: Complete A2A v0.3 compliant agent card
    """
    return AgentCard(
        # Agent identity
        name="Loist Music Library Processor",
        description="Audio processing and metadata extraction service",
        url="https://api.loist.music/a2a",
        version="1.0.0",

        # A2A protocol version
        protocol_version="0.3.0",

        # Capabilities
        capabilities=AgentCapabilities(
            streaming=False,
            pushNotifications=False,
            stateTransitionHistory=True
        ),

        # Input/output modes
        default_input_modes=["application/json", "text/plain"],
        default_output_modes=["application/json"],

        # Security configuration
        security=[{"BearerAuth": []}],
        security_schemes={
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT"
            }
        },

        # Core business skills
        skills=[
            AgentSkill(
                id="process_audio_complete",
                name="Process audio (full)",
                description="Process audio file from URL and extract complete metadata including waveform, artwork, and tags",
                tags=["audio", "ingestion", "metadata", "waveform"]
            ),
            AgentSkill(
                id="search_library",
                name="Search library",
                description="Search processed music library with text queries and metadata filters",
                tags=["search", "query", "metadata"]
            ),
            AgentSkill(
                id="get_audio_metadata",
                name="Get metadata",
                description="Retrieve complete metadata for a processed audio track by ID",
                tags=["metadata", "retrieval"]
            ),
            AgentSkill(
                id="update_metadata",
                name="Update metadata",
                description="Update metadata fields for an existing audio track",
                tags=["metadata", "update", "editing"]
            ),
            AgentSkill(
                id="delete_audio",
                name="Delete audio",
                description="Remove an audio track from the library and delete associated files",
                tags=["deletion", "cleanup"]
            ),
            AgentSkill(
                id="get_embed_url",
                name="Get embed URL",
                description="Generate embeddable player URLs for audio tracks with waveform visualization",
                tags=["embed", "player", "waveform"]
            )
        ]
    )