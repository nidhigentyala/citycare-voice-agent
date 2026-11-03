import { useState } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  ControlBar,
  useTranscriptions,
} from "@livekit/components-react";
import "@livekit/components-styles";
import "./App.css";

function TranscriptPanel() {
  const transcriptions = useTranscriptions();

  return (
    <section className="transcript-card">
      <div className="section-heading">
        <div>
          <span className="eyebrow">CONVERSATION</span>
          <h2>Live transcript</h2>
        </div>
        <span className="live-indicator">LIVE</span>
      </div>

      <div className="transcript-content" aria-live="polite">
        {transcriptions.length === 0 ? (
          <div className="empty-transcript">
            <div className="transcript-icon">✦</div>
            <h3>Your conversation will appear here</h3>
            <p>
              Once the agent and transcription service are active,
              your conversation will show up in real time.
            </p>
          </div>
        ) : (
          transcriptions.map((item, index) => (
            <div className="transcript-message" key={index}>
              <span className="message-dot" />
              <p>{item.text}</p>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function App() {
  const [roomName, setRoomName] = useState("citycare-test");
  const [token, setToken] = useState<string | null>(null);
  const [serverUrl, setServerUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const backendUrl =
    import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

  async function joinRoom() {
    if (!roomName.trim()) {
      setError("Please enter a room name.");
      return;
    }

    try {
      setLoading(true);
      setError("");

      const response = await fetch(
        `${backendUrl}/token?room=${encodeURIComponent(roomName.trim())}`
      );
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not get a LiveKit token.");
      }

      setToken(data.token);
      setServerUrl(data.url);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to connect to the backend."
      );
    } finally {
      setLoading(false);
    }
  }

  function leaveRoom() {
    setToken(null);
    setServerUrl(null);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/">
          <span className="brand-mark">+</span>
          <span>CityCare <strong>Clinic</strong></span>
        </a>
        <span className="topbar-label">VOICE ASSISTANT</span>
      </header>

      <main className="main-content">
        <div className="welcome">
          <span className="eyebrow">YOUR HEALTH, OUR PRIORITY</span>
          <h1>How can we help <span>you today?</span></h1>
          <p>
            Talk to the CityCare virtual assistant for help with
            clinic services and appointments.
          </p>
        </div>

        {!token || !serverUrl ? (
          <section className="connect-card">
            <div className="assistant-avatar">✚</div>
            <h2>Start a conversation</h2>
            <p>Connect securely to begin your voice session.</p>

            <form
              onSubmit={(event) => {
                event.preventDefault();
                void joinRoom();
              }}
            >
              <label htmlFor="roomName">Room name</label>
              <input
                id="roomName"
                value={roomName}
                onChange={(event) => setRoomName(event.target.value)}
                placeholder="Enter room name"
              />

              <button
                className="primary-button"
                type="submit"
                disabled={loading || !roomName.trim()}
              >
                {loading ? "Connecting..." : "Connect to assistant"}
                {!loading && <span aria-hidden="true"> →</span>}
              </button>
            </form>

            {error && <p className="error-message">{error}</p>}

            <div className="privacy-note">
              <span>●</span> Your session connects through LiveKit
            </div>
          </section>
        ) : (
          // <LiveKitRoom
          //   serverUrl={serverUrl}
          //   token={token}
          //   connect={true}
          //   audio={true}
          //   video={false}
          //   onDisconnected={leaveRoom}
          //   onError={(err) => setError(err.message)}
          // >
          <LiveKitRoom
            serverUrl={serverUrl}
            token={token}
            connect={true}
            audio={{
              noiseSuppression: true,
              echoCancellation: true,
              autoGainControl: true,
            }}
            video={false}
            onDisconnected={leaveRoom}
            onError={(err) => setError(err.message)}
          >
            <div className="session-layout">
              <section className="call-card">
                <div className="section-heading">
                  <div>
                    <span className="eyebrow">VOICE SESSION</span>
                    <h2>CityCare Assistant</h2>
                  </div>
                  <span className="connected-badge">Connected</span>
                </div>

                <div className="assistant-visual">
                  <div className="avatar-halo">
                    <div className="assistant-avatar large">✚</div>
                  </div>
                  <h3>I'm here to help</h3>
                  <p>Use your microphone to speak with the assistant.</p>
                </div>

                <div className="controls">
                  <ControlBar
                    controls={{
                      microphone: true,
                      camera: false,
                      screenShare: false,
                      chat: false,
                    }}
                  />
                </div>

                <RoomAudioRenderer />

                <button
                  className="leave-button"
                  type="button"
                  onClick={leaveRoom}
                >
                  Leave conversation
                </button>
                {error && <p className="error-message">{error}</p>}
              </section>

              <TranscriptPanel />
            </div>
          </LiveKitRoom>
        )}

        <div className="feature-row">
          <div className="feature">
            <span className="feature-icon">♡</span>
            <div><strong>Patient-focused</strong><p>Designed around your needs</p></div>
          </div>
          <div className="feature">
            <span className="feature-icon">◷</span>
            <div><strong>Available by voice</strong><p>Speak naturally</p></div>
          </div>
          <div className="feature">
            <span className="feature-icon">⌑</span>
            <div><strong>Secure connection</strong><p>Server-issued access token</p></div>
          </div>
        </div>
      </main>

      <footer className="footer">
        CityCare Clinic · Virtual assistant demo
      </footer>
    </div>
  );
}

export default App;
