import { useState } from "react";
import { sendChatMessage } from "../services/chatService";
export default function Chatbot() {
  const [open, setOpen] = useState(false),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false),
    [msgs, setMsgs] = useState([
      {
        role: "bot",
        text: "안녕하세요! 캠퍼스에서 어디로 가시나요?",
        local: true,
      },
    ]);
  async function send(text = input) {
    text = text.trim();
    if (!text || busy) return;
    setMsgs((x) => [...x, { role: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const answer = await sendChatMessage(text, msgs);
      setMsgs((x) => [...x, { role: "bot", text: answer.message, local: answer.status === "error" }]);
    } catch (error) {
      setMsgs((x) => [...x, { role: "bot", text: error.message, local: true }]);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button className="fab" onClick={() => setOpen(!open)}>
        {open ? "×" : "✦"}
        {!open && <span>AI 도우미</span>}
      </button>
      {open && (
        <section className="chat">
          <header>
            <span>✦</span>
            <div>
              <b>SafePath 도우미</b>
            </div>
            <button onClick={() => setOpen(false)}>—</button>
          </header>
          <main>
            {msgs.map((m, i) => (
              <div className={"msg " + m.role} key={i}>
                {m.role === "bot" && <i>✦</i>}
                <p>{m.text}</p>
              </div>
            ))}
            {msgs.length === 1 && (
              <div className="chips">
                {[
                  "가장 가까운 편의점이 어디야?",
                  "공학관까지 어떻게 가?",
                  "계단을 피할 수 있어?",
                ].map((x) => (
                  <button onClick={() => send(x)} key={x}>
                    {x}
                  </button>
                ))}
              </div>
            )}
            {busy && <small className="typing">● ● ●</small>}
          </main>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <input
              value={input}
              maxLength={4000}
              onChange={(e) => setInput(e.target.value)}
              placeholder="캠퍼스에 대해 물어보세요"
            />
            <button>➤</button>
          </form>
        </section>
      )}
    </>
  );
}
