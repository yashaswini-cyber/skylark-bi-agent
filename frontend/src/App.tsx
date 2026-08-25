import { useState } from "react";
import type { FormEvent } from "react";
import "./App.css";

type Message = {
  role: "user" | "assistant";
  content: string;
};

const API_URL = "http://127.0.0.1:8000";

const suggestions = [
  "How is Mining pipeline doing?",
  "What is our receivables?",
  "What is the current work order status?",
];

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function sendMessage(message?: string) {
    const text = (message ?? input).trim();

    if (!text || loading) {
      return;
    }

    setMessages((current) => [
      ...current,
      {
        role: "user",
        content: text,
      },
    ]);

    setInput("");
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: text,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to get a response from the BI agent.",
        );
      }

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.answer,
        },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            error instanceof Error
              ? error.message
              : "Something went wrong. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage();
  }

  return (
    <div className="app">
      <header className="header">
        <div>
          <div className="brand">SKYLARK</div>
          <div className="product-name">BI Agent</div>
        </div>

        <div className="status">
          <span className="status-dot" />
          Connected
        </div>
      </header>

      <main className="main">
        <section className="hero">
          <p className="eyebrow">BUSINESS INTELLIGENCE</p>

          <h1>Your business data, in conversation.</h1>

          <p className="subtitle">
            Query live Deals and Work Order data through a conversational
            interface.
          </p>
        </section>

        {messages.length === 0 && (
          <section className="suggestions">
            <p className="section-label">Try asking</p>

            <div className="suggestion-grid">
              {suggestions.map((question) => (
                <button
                  key={question}
                  className="suggestion"
                  type="button"
                  onClick={() => void sendMessage(question)}
                >
                  {question}
                </button>
              ))}
            </div>
          </section>
        )}

        <section className="chat">
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`message ${message.role}`}
            >
              <div className="message-label">
                {message.role === "user" ? "You" : "SkylarK Business Intelligence Agent"}
              </div>

              <div className="message-content">{message.content}</div>
            </div>
          ))}

          {loading && (
            <div className="message assistant">
              <div className="message-label">Skylark BI Agent</div>

              <div className="message-content">
                Analyzing live data...
              </div>
            </div>
          )}
        </section>
      </main>

      <form className="composer" onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask about pipeline, billing, work orders..."
          disabled={loading}
        />

        <button
          type="submit"
          disabled={loading || !input.trim()}
        >
          {loading ? "..." : "Send"}
        </button>
      </form>
    </div>
  );
}

export default App;