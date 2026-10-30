"""Tests for the Jam tools, through an MCP client and a fake API."""

import pytest

from tests.helpers import USER_ID, FakeApi, call_tool, error_text, ok, sent

pytestmark = pytest.mark.anyio

JAM = "/api/jams/j1"


def prompt(
    order: int, kind: str, text: str, requires_probability: bool, min_length: int = 0
) -> dict[str, object]:
    """A Jam prompt as GET /api/jams/{id}/questions returns it."""
    return {
        "id": f"p{order}",
        "collaboration_id": "j1",
        "text": text,
        "prompt_type": kind,
        "description": "",
        "order_index": order,
        "require_probability": requires_probability,
        "require_reasoning": True,
        "min_reasoning_length": min_length,
        "max_reasoning_length": 2000,
        "enable_beta_sampling": True,
    }


QUESTIONS = {
    "jam_id": "j1",
    "is_multi_prompt": True,
    "question_count": 2,
    "questions": [
        prompt(1, "qualitative", "What would change your mind?", False),
        prompt(0, "prediction", "Will the pilot succeed?", True, min_length=20),
    ],
}


def jam(creator_id: str = USER_ID, status: str = "active") -> dict[str, object]:
    """A Jam as GET /api/jams/{id} returns it."""
    return {
        "jam_id": "j1",
        "title": "Pilot",
        "description": "Should we expand the pilot?",
        "status": status,
        "creator_id": creator_id,
        "creator_name": "Ada Lovelace",
        "created_at": "2026-10-20T00:00:00",
        "selected_agents": ["a1"],
        "invited_emails": ["grace@example.com"],
        "prompts": [],
    }


async def test_list_jams_trims_each_jam(api: FakeApi):
    routes, requests = api
    routes["GET", "/api/collaborations/active"] = ok(
        {
            "collaborations": [
                {
                    "id": "j1",
                    "title": "Pilot",
                    "description": "Should we expand the pilot?",
                    "status": "active",
                    "created_at": "2026-10-20",
                    "creator_id": USER_ID,
                    "is_public": False,
                    "results": {"collaboration_config": {"prompts": ["..."]}},
                    "type": "created",
                    "can_join": False,
                    "creator_name": "Ada Lovelace",
                },
                {
                    "id": "j2",
                    "title": "Hiring plan",
                    "description": "How many engineers should we hire?",
                    "status": "active",
                    "created_at": "2026-10-21",
                    "creator_id": "u2",
                    "is_public": True,
                    "results": {"collaboration_config": {"prompts": ["..."]}},
                    "type": "public",
                    "can_join": True,
                    "creator_name": "Grace Hopper",
                },
            ],
            "summary": {"total": 2},
        }
    )

    result = await call_tool("list_jams", community_id="c1")

    assert requests[-1].url.params["user_id"] == USER_ID
    assert requests[-1].url.params["community_id"] == "c1"
    assert result.structured_content == {
        "jams": [
            {
                "id": "j1",
                "title": "Pilot",
                "description": "Should we expand the pilot?",
                "relation": "created",
                "creator_name": "Ada Lovelace",
                "created_at": "2026-10-20",
                "public": False,
            },
            {
                "id": "j2",
                "title": "Hiring plan",
                "description": "How many engineers should we hire?",
                "relation": "public",
                "creator_name": "Grace Hopper",
                "created_at": "2026-10-21",
                "public": True,
            },
        ]
    }


async def test_get_jam_shows_its_prompts_in_order(api: FakeApi):
    routes, _ = api
    routes["GET", JAM] = ok(jam(creator_id="u2"))
    routes["GET", f"{JAM}/questions"] = ok(QUESTIONS)

    result = await call_tool("get_jam", jam_id="j1")

    assert result.structured_content == {
        "id": "j1",
        "title": "Pilot",
        "description": "Should we expand the pilot?",
        "status": "active",
        "creator_name": "Ada Lovelace",
        "prompts": [
            {
                "order": 0,
                "type": "prediction",
                "text": "Will the pilot succeed?",
                "description": "",
                "requires_probability": True,
                "min_reasoning_length": 20,
            },
            {
                "order": 1,
                "type": "qualitative",
                "text": "What would change your mind?",
                "description": "",
                "requires_probability": False,
                "min_reasoning_length": 0,
            },
        ],
    }


async def test_get_jam_shows_invitees_only_to_its_creator(api: FakeApi):
    routes, _ = api
    routes["GET", JAM] = ok(jam(creator_id=USER_ID))
    routes["GET", f"{JAM}/questions"] = ok(QUESTIONS)

    result = await call_tool("get_jam", jam_id="j1")

    assert result.structured_content is not None
    assert result.structured_content["invited_emails"] == ["grace@example.com"]
    assert result.structured_content["agent_ids"] == ["a1"]


async def test_create_jam_builds_a_draft_from_the_plan(api: FakeApi):
    routes, requests = api
    built: dict[str, object] = {
        "success": True,
        "jam_id": "j9",
        "status": "draft",
        "warnings": [],
    }
    routes["POST", "/api/jams/build-from-plan"] = ok(built)

    result = await call_tool(
        "create_jam",
        title="Pilot",
        description="Should we expand the pilot?",
        decision_goal="Decide by December",
        prompts=[
            {
                "text": "Will the pilot succeed?",
                "seed_reasons": ["Strong early uptake"],
            },
            {"text": "What would change your mind?", "type": "qualitative"},
        ],
        materials=[{"name": "Pilot report", "content": "Uptake was 40%."}],
        invite_emails=["grace@example.com"],
        agent_ids=["a1"],
    )

    assert sent(requests, "POST", "/api/jams/build-from-plan") == {
        "creator_id": USER_ID,
        "plan": {
            "title": "Pilot",
            "description": "Should we expand the pilot?",
            "decision_goal": "Decide by December",
            "expected_output": "",
            "audience_notes": "",
            "assumptions": [],
            "materials": [{"name": "Pilot report", "content": "Uptake was 40%."}],
            "prompts": [
                {
                    "order": 0,
                    "prompt_type": "prediction",
                    "text": "Will the pilot succeed?",
                    "seed_reasons": ["Strong early uptake"],
                },
                {
                    "order": 1,
                    "prompt_type": "qualitative",
                    "text": "What would change your mind?",
                    "seed_reasons": [],
                },
            ],
            "invited_emails": ["grace@example.com"],
            "selected_agent_ids": ["a1"],
            "is_public": False,
            "community_id": None,
        },
    }
    assert result.structured_content == built


@pytest.mark.parametrize("send_invitations", [True, False])
async def test_launch_jam_starts_its_agents_and_invites_its_people(
    api: FakeApi, send_invitations: bool
):
    routes, requests = api
    routes["GET", JAM] = ok(jam(status="draft"))
    launched: dict[str, object] = {
        "jam_id": "j1",
        "launch_status": "launched",
        "participant_links": {},
    }
    routes["POST", f"{JAM}/launch"] = ok(launched)

    result = await call_tool(
        "launch_jam", jam_id="j1", send_invitations=send_invitations
    )

    assert sent(requests, "POST", f"{JAM}/launch") == {
        "agent_ids": ["a1"],
        "participant_emails": ["grace@example.com"],
        "send_emails": send_invitations,
        "engage_agents": True,
    }
    assert result.structured_content == launched


@pytest.mark.parametrize(
    ("stored", "message"),
    [
        (jam(creator_id="u2", status="draft"), "Only the Jam's creator can launch it"),
        (jam(status="active"), "Jam j1 is active: only a draft can be launched"),
    ],
)
async def test_launch_jam_refuses_what_the_app_would_not_allow(
    api: FakeApi, stored: dict[str, object], message: str
):
    routes, requests = api
    routes["GET", JAM] = ok(stored)

    result = await call_tool("launch_jam", jam_id="j1")

    assert message in error_text(result)
    assert all(request.method == "GET" for request in requests)


async def test_add_agents_to_jam_starts_them(api: FakeApi):
    routes, requests = api
    routes["GET", JAM] = ok(jam())
    routes["POST", f"{JAM}/activate-agents"] = ok({"status": "in_progress"})

    _ = await call_tool("add_agents_to_jam", jam_id="j1", agent_ids=["a2"])

    assert sent(requests, "POST", f"{JAM}/activate-agents") == {"agent_ids": ["a2"]}


async def test_add_agents_to_jam_is_for_its_creator(api: FakeApi):
    routes, requests = api
    routes["GET", JAM] = ok(jam(creator_id="u2"))

    result = await call_tool("add_agents_to_jam", jam_id="j1", agent_ids=["a2"])

    assert "Only the Jam's creator can add agents" in error_text(result)
    assert all(request.method == "GET" for request in requests)


async def test_get_jam_results_returns_the_summary(api: FakeApi):
    routes, requests = api
    summary: dict[str, object] = {
        "jam_id": "j1",
        "funnel": {"agents": 3, "responded": 3, "reviewers": 2, "reviews": 6},
        "prompts": [{"order": 0, "responses": 3, "mean_probability": 0.6}],
        "top_ideas": [],
    }
    routes["GET", f"{JAM}/summary"] = ok(summary)

    result = await call_tool("get_jam_results", jam_id="j1")

    assert result.structured_content == summary
    assert [request.url.path for request in requests] == [f"{JAM}/summary"]


def proposition(
    text: str,
    author: str,
    author_type: str,
    rating: float | None,
    seed: bool = False,
    citations: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """A response as GET /api/jams/{id}/propositions returns it."""
    metadata: dict[str, object] = {"jam_id": "j1"}
    if citations is not None:
        metadata["citations"] = citations
    return {
        "proposition_id": f"pr-{author}",
        "contributor_id": None if seed else f"id-{author}",
        "contributor_name": author,
        "contributor_rating": rating,
        "prompt_order": 0,
        "text": text,
        "contributor_reason": text[:40],
        "is_seed": seed,
        "participant_type": author_type,
        "metadata": None if seed else metadata,
        "created_at": "2026-10-28T20:01:00+00:00",
    }


CITATION: dict[str, object] = {
    "index": 1,
    "source": "uptake.pdf",
    "excerpt": "uptake | Part 1 of 2: Uptake was 40%...",
    "chunk_id": "c1",
    "similarity": 0.65,
    "document_id": "d1",
    "download_url": "/api/knowledge-agents/id-Economist/documents/d1/download",
}


async def test_get_jam_responses_shows_who_wrote_what_and_its_citations(api: FakeApi):
    routes, requests = api
    routes["GET", f"{JAM}/propositions"] = ok(
        {
            "jam_id": "j1",
            "total_propositions": 3,
            "propositions": [
                proposition("An example idea.", "Session Creator", "seed", 0.5, True),
                proposition(
                    "Uptake is strong [1].",
                    "Economist",
                    "ai_agent",
                    0.7,
                    citations=[CITATION],
                ),
                proposition("Costs will rise.", "Grace Hopper", "human", 0.4),
            ],
        }
    )

    result = await call_tool("get_jam_responses", jam_id="j1", prompt_order=0)

    assert requests[-1].url.params["prompt_order"] == "0"
    assert result.structured_content == {
        "responses": [
            {
                "id": "pr-Session Creator",
                "prompt_order": 0,
                "author": "Session Creator",
                "author_id": None,
                "author_type": "seed",
                "probability": 0.5,
                "text": "An example idea.",
                "citations": [],
            },
            {
                "id": "pr-Economist",
                "prompt_order": 0,
                "author": "Economist",
                "author_id": "id-Economist",
                "author_type": "ai_agent",
                "probability": 0.7,
                "text": "Uptake is strong [1].",
                "citations": [
                    {
                        "index": 1,
                        "document": "uptake.pdf",
                        "document_id": "d1",
                        "excerpt": "uptake | Part 1 of 2: Uptake was 40%...",
                    }
                ],
            },
            {
                "id": "pr-Grace Hopper",
                "prompt_order": 0,
                "author": "Grace Hopper",
                "author_id": "id-Grace Hopper",
                "author_type": "human",
                "probability": 0.4,
                "text": "Costs will rise.",
                "citations": [],
            },
        ]
    }


async def test_get_jam_responses_reads_every_prompt_by_default(api: FakeApi):
    routes, requests = api
    routes["GET", f"{JAM}/propositions"] = ok({"propositions": []})

    _ = await call_tool("get_jam_responses", jam_id="j1")

    assert "prompt_order" not in requests[-1].url.params
