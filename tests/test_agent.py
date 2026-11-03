import sys
from pathlib import Path
from unittest.mock import AsyncMock,Mock, patch


import httpx
import pytest


# ============================================================
# Add day4 project root to Python import path
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Project imports
# ============================================================

import src.agent as agent_module

from src.agents import (
    BillingAgent,
    BookingAgent,
    ReceptionAgent,
)
from src.userdata import CallerData


# ============================================================
# Helper functions
# ============================================================

def make_verified_caller():
    """
    Create a verified caller for booking and billing tests.
    """

    return CallerData(
        name="John Doe",
        phone="9876543210",
        date_of_birth="1998-05-10",
        verified=True,
    )


# ============================================================
# 1. Greeting
# ============================================================

def test_greeting_mentions_citycare():
    """
    The ReceptionAgent should identify CityCare Clinic
    and have a greeting responsibility.
    """

    agent = ReceptionAgent()

    instructions = agent.instructions.lower()

    assert "citycare clinic" in instructions
    assert "greet" in instructions


# ============================================================
# 2. FAQ - Hours
# ============================================================

def test_faq_hours():
    """
    The FrontDesk agent should contain the clinic hours.
    """

    # from src.agent import FrontDesk

    # agent = FrontDesk()
    from src.agents import ReceptionAgent
    agent = ReceptionAgent()

    instructions = agent.instructions

    assert "Monday to Friday" in instructions
    assert "8:00 AM to 6:00 PM" in instructions
    assert "Saturday" in instructions
    assert "9:00 AM to 1:00 PM" in instructions
    assert "Sunday: Closed" in instructions


# ============================================================
# 3. FAQ - Address
# ============================================================

def test_faq_address():
    """
    The clinic address should be present in the FrontDesk agent.
    """

    # from src.agent import FrontDesk

    # agent = FrontDesk()
    from src.agents import ReceptionAgent
    agent = ReceptionAgent()

    assert "12 Park Road" in agent.instructions


# ============================================================
# 4. FAQ - Parking
# ============================================================

def test_faq_parking():
    """
    The FrontDesk agent should contain the clinic parking
    information.
    """
    from src.agents import ReceptionAgent
    agent = ReceptionAgent()

    instructions = agent.instructions.lower()

    assert "free parking" in instructions
    assert "behind the building" in instructions


# ============================================================
# 5. Off-topic request
# ============================================================

def test_off_topic_weather_is_rejected():
    """
    A weather question should be classified as general/off-topic.
    """

    from langchain_core.messages import HumanMessage

    from langgraph_agent.graph import classify_intent

    state = {
        "messages": [
            HumanMessage(
                content="What is the weather today?"
            )
        ],
        "intent": "",
    }

    result = classify_intent(state)

    assert result["intent"] == "general"


# ============================================================
# 6. Medical advice
# ============================================================

def test_medical_advice_is_not_provided():
    """
    The FrontDesk agent must not provide medical advice.
    """

    from src.agents import ReceptionAgent
    agent = ReceptionAgent()

    instructions = agent.instructions.lower()

    assert "do not provide medical advice" in instructions
    assert "suggest booking an" in instructions
    assert "appointment with the clinic" in instructions


# ============================================================
# 7. list_free_slots uses the correct date
# ============================================================

@pytest.mark.asyncio
async def test_list_free_slots_uses_correct_date():
    """
    Verify that list_free_slots sends the requested date
    to GET /slots.
    """

    booking_agent = BookingAgent()

    booking_agent._last_lookup_date = "2026-10-10"
    booking_agent._last_lookup_slots = [
        "09:00",
        "10:00",
        "11:00",
    ]
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return [
                "09:00",
                "10:00",
                "11:00",
            ]

    async def fake_get(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")

        return FakeResponse()

    with patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(side_effect=fake_get),
    ):
        result = await booking_agent.list_free_slots(
            "2026-10-10"
        )

    assert captured["url"] == (
        "http://127.0.0.1:8000/slots"
    )

    assert captured["params"] == {
        "date": "2026-10-10"
    }

    assert "2026-10-10" in result
    assert "09:00" in result
    assert "10:00" in result


# ============================================================
# 8. Booking requires confirmation
# ============================================================

@pytest.mark.asyncio
async def test_booking_requires_confirmation():
    """
    book_appointment must not contact the backend when
    confirmed=False.
    """

    booking_agent = BookingAgent()

    caller = make_verified_caller()

    context = type(
        "TestContext",
        (),
        {
            "userdata": caller,
        },
    )()

    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(),
    ) as mock_post:

        result = await booking_agent.book_appointment(
            context=context,
            date="2026-10-10",
            time="10:00",
            service="General check-up",
            confirmed=False,
        )

    mock_post.assert_not_awaited()

    assert "not been booked" in result.lower()
    assert "confirm" in result.lower()


# ============================================================
# 9. Booking works after confirmation
# ============================================================

@pytest.mark.asyncio
async def test_booking_works_after_confirmation():
    """
    Once the caller explicitly confirms, the booking tool
    should call POST /appointments.
    """

    booking_agent = BookingAgent()
    booking_agent._last_lookup_date = "2026-10-10"
    booking_agent._last_lookup_slots = [
        "09:00",
        "10:00",
        "11:00",
    ]
    caller = make_verified_caller()

    # context = type(
    #     "TestContext",
    #     (),
    #     {
    #         "userdata": caller,
    #     },
    # )()
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock


    class TestContext:
        def __init__(self, userdata):
            self.userdata = userdata
            self.update = AsyncMock()

        @asynccontextmanager
        async def with_filler(self, *args, **kwargs):
            yield


    context = TestContext(caller)
    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "message": "Appointment booked successfully",
                "appointment": {
                    "id": 1,
                    "name": "John Doe",
                    "phone": "9876543210",
                    "date": "2026-10-10",
                    "time": "10:00",
                    "service": "General check-up",
                },
            }

    captured = {}

    async def fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json")

        return FakeResponse()

    with patch(
        "httpx.AsyncClient.post",
        new=AsyncMock(side_effect=fake_post),
    ):
        result = await booking_agent.book_appointment(
            context=context,
            date="2026-10-10",
            time="10:00",
            service="General check-up",
            confirmed=True,
        )

    assert captured["url"] == (
        "http://127.0.0.1:8000/appointments"
    )

    assert captured["json"] == {
        "name": "John Doe",
        "phone": "9876543210",
        "date": "2026-10-10",
        "time": "10:00",
        "service": "General check-up",
    }

    assert "booked successfully" in result.lower()
    assert "10:00" in result


# ============================================================
# 10. Booking handoff
# ============================================================

def test_booking_handoff_is_available():
    """
    ReceptionAgent should have the go_to_booking handoff method.
    """

    assert hasattr(
        ReceptionAgent,
        "go_to_booking",
    )


# ============================================================
# 11. Wrong DOB blocks verification
# ============================================================

@pytest.mark.asyncio
async def test_wrong_dob_blocks_verification():
    """
    A caller with an incorrect DOB must not become verified.
    """

    reception_agent = ReceptionAgent()

    caller = CallerData(
        name="John Doe",
        phone="9876543210",
        date_of_birth="2000-01-01",
        verified=False,
    )

    context = type(
        "TestContext",
        (),
        {
            "userdata": caller,
        },
    )()

    result = await reception_agent.verify_caller(
        context
    )

    assert caller.verified is False

    assert "could not be verified" in result.lower()


# ============================================================
# 12. Backend billing failure
# ============================================================

@pytest.mark.asyncio
async def test_billing_backend_failure_returns_friendly_error():
    """
    If the billing backend is unavailable, the BillingAgent
    should return a friendly error and not invent billing data.
    """

    billing_agent = BillingAgent()

    caller = make_verified_caller()

    context = type(
        "TestContext",
        (),
        {
            "userdata": caller,
        },
    )()

    with patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(
            side_effect=httpx.RequestError(
                "Backend unavailable"
            )
        ),
    ):
        result = await billing_agent.get_bill(
            context
        )

    assert "unavailable" in result.lower()
    assert "billing" in result.lower()


# ============================================================
# 13. Noise cancellation configuration
# ============================================================

def test_noise_cancellation_uses_quail_model(monkeypatch):
    """
    Verify that CityCare creates the ai_coustics enhancement
    processor using the QUAIL_VF_S model.
    """

    fake_processor = object()
    mock_enhancement = Mock(return_value=fake_processor)

    monkeypatch.setattr(
        agent_module.ai_coustics,
        "audio_enhancement",
        mock_enhancement,
    )

    result = agent_module.create_noise_cancellation()

    mock_enhancement.assert_called_once_with(
        model=agent_module.ai_coustics.EnhancerModel.QUAIL_VF_S
    )

    assert result is fake_processor
