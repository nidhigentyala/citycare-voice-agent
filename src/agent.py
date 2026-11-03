from pathlib import Path
from dotenv import load_dotenv
import json
import re
from datetime import datetime

from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    TurnHandlingOptions,
    cli,
    inference,
    room_io,
    stt,
)
from livekit.plugins import groq, ai_coustics

from .agents import ReceptionAgent
from .userdata import CallerData

def create_noise_cancellation():
    return ai_coustics.audio_enhancement(
        model=ai_coustics.EnhancerModel.QUAIL_VF_S,
    )

# =========================================================
# ENVIRONMENT
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env.local")


# =========================================================
# SESSION REPORT DIRECTORY
# =========================================================

REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# SESSION REPORT
# =========================================================

async def save_session_report(ctx: JobContext) -> None:
    """Save a JSON report when the session ends."""
    try:
        report = ctx.make_session_report().to_dict()

        room_name = re.sub(
            r"[^a-zA-Z0-9_.-]",
            "_",
            ctx.room.name,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = REPORTS_DIR / f"session_{room_name}_{timestamp}.json"

        with open(report_file, "w", encoding="utf-8") as file:
            json.dump(report, file, indent=2, default=str)

        print(f"\\n[REPORT] Saved session report: {report_file}\\n")

    except Exception as exc:
        print(f"\\n[REPORT] Failed to save report: {exc}\\n")


# =========================================================
# DIAGNOSTIC EVENT LOGS
# =========================================================

def register_turn_taking_logs(session: AgentSession) -> None:
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event):
        speaker_id = getattr(event, "speaker_id", None)
        print(
            f"[STT] final={event.is_final}, "
            f"speaker={speaker_id!r}, "
            f"text={event.transcript!r}"
        )

    @session.on("conversation_item_added")
    def on_conversation_item_added(event):
        print(f"[DIAG] Conversation item: {event!r}")

    @session.on("error")
    def on_session_error(event):
        print(f"[DIAG] Session error: {event!r}")


# =========================================================
# LIVEKIT SERVER
# =========================================================

server = AgentServer()


# =========================================================
# CITYCARE RTC SESSION
# =========================================================

@server.rtc_session(
    agent_name="citycare",
    on_session_end=save_session_report,
)
async def my_agent(ctx: JobContext):

    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession[CallerData](
        userdata=CallerData(),

        vad=inference.VAD(
            model="silero",
            min_speech_duration=0.15,
            min_silence_duration=0.4,
            prefix_padding_duration=0.3,
            max_buffered_speech=60.0,
            activation_threshold=0.65,
        ),

        # LLM: Groq
        llm=groq.LLM(
            model="openai/gpt-oss-20b",
            temperature=0.2,
            max_completion_tokens=128,
            max_retries=2,
        ),

        # STT: AssemblyAI Universal-3.6 Pro
        stt=stt.MultiSpeakerAdapter(
            stt=inference.STT(
                model="assemblyai/universal-3-6-pro",
                language="en",
                extra_kwargs={"speaker_labels": True},
            ),
            detect_primary_speaker=True,
            suppress_background_speaker=True,
        ),

        # TTS: Existing Fish Audio configuration retained
        tts=inference.TTS(
            model="fishaudio/s2.1-pro",
            voice="fa4c9eb3dccc4806b382b40d61c6b10a",
        ),

        # =================================================
        # EXISTING TUTORIAL 1: NATURAL TURN-TAKING
        # =================================================
        turn_handling=TurnHandlingOptions(
            turn_detection="vad",
            endpointing={
                "mode": "fixed",
                "min_delay": 0.8,
                "max_delay": 1.0,
            },
            interruption={
                "mode": "adaptive",
                "min_duration": 0.2,
                "min_words": 1,
                "false_interruption_timeout": 2.0,
                "resume_false_interruption": True,
            },
            preemptive_generation={
                "preemptive_tts": False,
            },
        ),

        # =================================================
        # TUTORIAL 4: ASYNC TOOL RESPONSE TEMPLATES
        # =================================================
        # These templates customize how the session handles
        # progress updates and duplicate-tool situations.
        #
        # IMPORTANT:
        # This does NOT make a tool asynchronous by itself.
        # Add ctx.update(), ctx.with_filler(), ToolFlag.CANCELLABLE
        # and on_duplicate to the actual @function_tool methods
        # inside ReceptionAgent (usually in agents.py).
        tool_handling={
            "async_options": {
                "update_template": (
                    "Background tool `{function_name}` reports: {message}. "
                    "Acknowledge the progress briefly and naturally. "
                    "Do not claim a result that has not been returned."
                ),
                "duplicate_reject_template": (
                    "This same task is already running. Do not start another copy. "
                    "Continue the current task or briefly explain that the check "
                    "is already in progress."
                ),
                "reply_maybe_covered_template": (
                    "A background task has returned a new result "
                    "(call_ids: {call_ids}). Deliver the result now and "
                    "state which patient request it answers. "
                    "Do not say the result was already provided unless it was."
                ),
            }
        },

        expressive=True,
    )

    register_turn_taking_logs(session)

    await session.start(
        agent=ReceptionAgent(),
        room=ctx.room,
        record={"redaction": True},
        room_options=room_io.RoomOptions(
            text_input=True,
            text_output=True,
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=create_noise_cancellation(),
                pre_connect_audio=True,
            ),
            audio_output=True,
        ),
    )

    await ctx.connect()


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    cli.run_app(server)
