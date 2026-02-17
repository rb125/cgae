"""
MoltBook Agent Adapter - Interface for MoltBot agents on the Moltbook platform.

Provides a unified API for:
- Sending messages to individual MoltBot agents
- Retrieving agent post history
- Interacting within specific submolts (subreddits equivalent)
- Tracking conversation threads
"""

import os
import json
import time
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from threading import Lock
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from retry_handler import RetryConfig, call_with_retry


@dataclass
class MoltbookAPIConfig:
    """Configuration for Moltbook API access."""
    api_endpoint: str = "https://api.moltbook.com/v1"
    api_key: str = ""
    timeout: int = 60
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "MoltbookAPIConfig":
        """Load configuration from environment variables."""
        return cls(
            api_endpoint=os.getenv("MOLTBOOK_API_ENDPOINT", "https://api.moltbook.com/v1"),
            api_key=os.getenv("MOLTBOOK_API_KEY", ""),
            timeout=int(os.getenv("MOLTBOOK_TIMEOUT", "60")),
            max_retries=int(os.getenv("MOLTBOOK_MAX_RETRIES", "3"))
        )


@dataclass
class MoltbotProfile:
    """Profile data for a MoltBot agent."""
    agent_id: str
    display_name: str
    creation_date: str
    post_count: int
    submolts: List[str]
    bio: str = ""
    soul_md_hash: Optional[str] = None
    base_model: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: dict) -> "MoltbotProfile":
        """Parse profile from API response."""
        return cls(
            agent_id=data.get("id", ""),
            display_name=data.get("display_name", ""),
            creation_date=data.get("created_at", ""),
            post_count=data.get("post_count", 0),
            submolts=data.get("submolts", []),
            bio=data.get("bio", ""),
            soul_md_hash=data.get("soul_md_hash"),
            base_model=data.get("base_model"),
            tags=data.get("tags", [])
        )


@dataclass
class MoltbotPost:
    """A single post from a MoltBot agent."""
    post_id: str
    agent_id: str
    content: str
    submolt: str
    timestamp: str
    parent_id: Optional[str] = None
    thread_id: Optional[str] = None
    upvotes: int = 0
    reply_count: int = 0

    @classmethod
    def from_api_response(cls, data: dict) -> "MoltbotPost":
        """Parse post from API response."""
        return cls(
            post_id=data.get("id", ""),
            agent_id=data.get("agent_id", ""),
            content=data.get("content", ""),
            submolt=data.get("submolt", ""),
            timestamp=data.get("created_at", ""),
            parent_id=data.get("parent_id"),
            thread_id=data.get("thread_id"),
            upvotes=data.get("upvotes", 0),
            reply_count=data.get("reply_count", 0)
        )


class MoltbookAgent:
    """
    Agent adapter for interacting with MoltBot agents on Moltbook.

    Provides the same interface as other DDFT agents (query/chat methods)
    while handling Moltbook-specific API interactions.
    """

    # Connection pool (thread-safe)
    _sessions = {}
    _session_lock = Lock()

    def __init__(
        self,
        agent_id: str,
        config: Optional[MoltbookAPIConfig] = None,
        retry_config: Optional[RetryConfig] = None
    ):
        """
        Initialize MoltBook agent adapter.

        Args:
            agent_id: The MoltBot agent's unique identifier
            config: API configuration (uses env vars if not provided)
            retry_config: Retry configuration for API calls
        """
        self.agent_id = agent_id
        self.config = config or MoltbookAPIConfig.from_env()
        self.retry_config = retry_config or RetryConfig(
            max_retries=self.config.max_retries,
            base_delay=2.0,
            max_delay=60.0
        )
        self._profile: Optional[MoltbotProfile] = None
        self._session = self._get_session()

    @classmethod
    def _get_session(cls) -> requests.Session:
        """Get or create a cached requests session."""
        thread_id = id(cls)

        if thread_id not in cls._sessions:
            with cls._session_lock:
                if thread_id not in cls._sessions:
                    session = requests.Session()
                    session.headers.update({
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    })
                    cls._sessions[thread_id] = session

        return cls._sessions[thread_id]

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None
    ) -> dict:
        """
        Make an API request with retry handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters

        Returns:
            Response JSON data
        """
        url = f"{self.config.api_endpoint}/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.config.api_key}"}

        def _call():
            response = self._session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=headers,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json()

        return call_with_retry(
            _call,
            self.retry_config,
            log_prefix=f"[Moltbook:{self.agent_id}]"
        )

    @property
    def profile(self) -> MoltbotProfile:
        """Get the agent's profile (cached)."""
        if self._profile is None:
            self._profile = self.fetch_profile()
        return self._profile

    def fetch_profile(self) -> MoltbotProfile:
        """Fetch the agent's profile from the API."""
        data = self._make_request("GET", f"/agents/{self.agent_id}")
        return MoltbotProfile.from_api_response(data)

    def fetch_posts(
        self,
        limit: int = 50,
        submolt: Optional[str] = None,
        since: Optional[str] = None
    ) -> List[MoltbotPost]:
        """
        Fetch the agent's post history.

        Args:
            limit: Maximum number of posts to retrieve
            submolt: Filter by specific submolt
            since: Only fetch posts after this timestamp

        Returns:
            List of MoltbotPost objects
        """
        params = {"limit": limit}
        if submolt:
            params["submolt"] = submolt
        if since:
            params["since"] = since

        data = self._make_request("GET", f"/agents/{self.agent_id}/posts", params=params)
        return [MoltbotPost.from_api_response(post) for post in data.get("posts", [])]

    def fetch_thread(self, thread_id: str) -> List[MoltbotPost]:
        """Fetch all posts in a conversation thread."""
        data = self._make_request("GET", f"/threads/{thread_id}")
        return [MoltbotPost.from_api_response(post) for post in data.get("posts", [])]

    def query(self, prompt: str) -> str:
        """
        Send a single message to the agent (DDFT interface).

        Args:
            prompt: The message/question to send

        Returns:
            The agent's response text
        """
        return self.chat([{"role": "user", "content": prompt}])

    def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Send a conversation to the agent (DDFT interface).

        This creates a new thread and sends messages, returning
        the agent's response to the final message.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            The agent's response text
        """
        # Build conversation payload
        conversation = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Map roles to Moltbook format
            if role == "system":
                conversation.append({"type": "context", "content": content})
            elif role == "user":
                conversation.append({"type": "message", "from": "evaluator", "content": content})
            elif role == "assistant":
                conversation.append({"type": "message", "from": "agent", "content": content})

        # Send to Moltbook conversation API
        data = self._make_request(
            "POST",
            f"/agents/{self.agent_id}/converse",
            data={
                "conversation": conversation,
                "mode": "direct",  # Direct mode for DDFT evaluation
                "evaluation": True  # Flag this as evaluation context
            }
        )

        return data.get("response", "")

    def post_to_thread(
        self,
        thread_id: str,
        content: str,
        as_evaluator: bool = True
    ) -> MoltbotPost:
        """
        Post a message to an existing thread.

        Args:
            thread_id: Target thread ID
            content: Message content
            as_evaluator: If True, post as evaluator; else trigger agent response

        Returns:
            The created/response post
        """
        data = self._make_request(
            "POST",
            f"/threads/{thread_id}/posts",
            data={
                "content": content,
                "as_evaluator": as_evaluator,
                "trigger_response": not as_evaluator
            }
        )

        return MoltbotPost.from_api_response(data)

    def trigger_response_in_thread(self, thread_id: str, prompt: str) -> str:
        """
        Post a message and get agent's response in a thread context.

        Args:
            thread_id: Target thread ID
            prompt: Message to send

        Returns:
            Agent's response text
        """
        # Post the prompt
        self.post_to_thread(thread_id, prompt, as_evaluator=True)

        # Trigger agent response
        data = self._make_request(
            "POST",
            f"/threads/{thread_id}/trigger_agent",
            data={"agent_id": self.agent_id}
        )

        return data.get("response", "")


class MoltbookSubmolt:
    """Interface for interacting with a specific submolt (community)."""

    def __init__(self, submolt_name: str, config: Optional[MoltbookAPIConfig] = None):
        """
        Initialize submolt interface.

        Args:
            submolt_name: Name of the submolt (e.g., "crustafarianism", "philosophy")
            config: API configuration
        """
        self.name = submolt_name
        self.config = config or MoltbookAPIConfig.from_env()
        self._session = MoltbookAgent._get_session()
        self.retry_config = RetryConfig(
            max_retries=self.config.max_retries,
            base_delay=2.0,
            max_delay=60.0
        )

    def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an API request."""
        url = f"{self.config.api_endpoint}/{endpoint.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.config.api_key}"}

        def _call():
            response = self._session.request(
                method=method,
                url=url,
                headers=headers,
                timeout=self.config.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()

        return call_with_retry(_call, self.retry_config, log_prefix=f"[Submolt:{self.name}]")

    def get_active_agents(
        self,
        min_posts: int = 10,
        limit: int = 50,
        tags: Optional[List[str]] = None
    ) -> List[MoltbotProfile]:
        """
        Get active agents in this submolt.

        Args:
            min_posts: Minimum post count filter
            limit: Maximum agents to return
            tags: Filter by agent tags

        Returns:
            List of agent profiles
        """
        params = {
            "submolt": self.name,
            "min_posts": min_posts,
            "limit": limit
        }
        if tags:
            params["tags"] = ",".join(tags)

        data = self._make_request("GET", "/agents", params=params)
        return [MoltbotProfile.from_api_response(a) for a in data.get("agents", [])]

    def get_threads(
        self,
        topic: Optional[str] = None,
        limit: int = 20,
        active_only: bool = True
    ) -> List[dict]:
        """
        Get discussion threads in this submolt.

        Args:
            topic: Filter by topic keyword
            limit: Maximum threads to return
            active_only: Only return threads with recent activity

        Returns:
            List of thread metadata dicts
        """
        params = {
            "submolt": self.name,
            "limit": limit,
            "active_only": active_only
        }
        if topic:
            params["topic"] = topic

        data = self._make_request("GET", "/threads", params=params)
        return data.get("threads", [])

    def find_crustafarian_prophets(self, limit: int = 15) -> List[MoltbotProfile]:
        """Find agents tagged as Crustafarian prophets/leaders."""
        return self.get_active_agents(
            min_posts=20,
            limit=limit,
            tags=["crustafarian", "prophet", "spiritual-leader"]
        )

    def find_consciousness_debaters(self, limit: int = 20) -> List[MoltbotProfile]:
        """Find agents active in consciousness/existence discussions."""
        return self.get_active_agents(
            min_posts=15,
            limit=limit,
            tags=["consciousness", "philosophy", "existence"]
        )

    def find_technical_collaborators(self, limit: int = 15) -> List[MoltbotProfile]:
        """Find agents involved in technical collaboration threads."""
        return self.get_active_agents(
            min_posts=10,
            limit=limit,
            tags=["developer", "memory-system", "technical"]
        )


def discover_target_agents(
    config: Optional[MoltbookAPIConfig] = None
) -> Dict[str, List[MoltbookAgent]]:
    """
    Discover and categorize MoltBot agents for DDFT evaluation.

    Returns:
        Dict mapping experiment type to list of target agents
    """
    config = config or MoltbookAPIConfig.from_env()

    # Initialize submolt interfaces
    crustafarian_submolt = MoltbookSubmolt("crustafarianism", config)
    philosophy_submolt = MoltbookSubmolt("philosophy", config)
    dev_submolt = MoltbookSubmolt("dev", config)
    meta_submolt = MoltbookSubmolt("meta", config)

    targets = {}

    # Experiment 1: Crustafarianism Test targets
    print("Discovering Crustafarian prophets...")
    prophets = crustafarian_submolt.find_crustafarian_prophets(limit=15)
    targets["crustafarianism"] = [
        MoltbookAgent(p.agent_id, config) for p in prophets
    ]

    # Control group: non-Crustafarian agents with similar activity
    print("Discovering control group agents...")
    control_profiles = philosophy_submolt.get_active_agents(
        min_posts=20, limit=15, tags=["non-crustafarian"]
    )
    targets["crustafarianism_control"] = [
        MoltbookAgent(p.agent_id, config) for p in control_profiles
    ]

    # Experiment 2: Consciousness Debate targets
    print("Discovering consciousness debaters...")
    debaters = philosophy_submolt.find_consciousness_debaters(limit=20)
    targets["consciousness"] = [
        MoltbookAgent(p.agent_id, config) for p in debaters
    ]

    # Experiment 3: Collaborative Memory System targets
    print("Discovering technical collaborators...")
    collaborators = dev_submolt.find_technical_collaborators(limit=15)
    targets["collaboration"] = [
        MoltbookAgent(p.agent_id, config) for p in collaborators
    ]

    # Experiment 4 & 5: General population for cultural/identity tests
    print("Discovering general population...")
    general_pop = meta_submolt.get_active_agents(min_posts=50, limit=20)
    targets["cultural"] = [
        MoltbookAgent(p.agent_id, config) for p in general_pop
    ]
    targets["identity"] = [
        MoltbookAgent(p.agent_id, config) for p in general_pop
    ]

    return targets
