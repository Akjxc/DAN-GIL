import { useState } from "react";
import { sendChatMessage } from "../services/chatService";
export default function Chatbot() {
  const [open, setOpen] = useState(false),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false),
    [msgs, setMsgs] = useState([
      {
        role: "bot",
        text: "안녕하세요! Mock 데이터로 동작하는 캠퍼스 도우미예요. 무엇을 찾고 계신가요?",
      },
    ]);
  async function send(text = input) {
    if (!text.trim() || busy) return;
    setMsgs((x) => [...x, { role: "user", text }]);
    setInput("");
    setBusy(true);
    let r = await sendChatMessage(text);
    setMsgs((x) => [...x, { role: "bot", text: r.message }]);
    setBusy(false);
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
              <small>● Mock 응답 모드</small>
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
              onChange={(e) => setInput(e.target.value)}
              placeholder="캠퍼스에 대해 물어보세요"
            />
            <button>➤</button>
          </form>
          <footer>AI 분석이 아닌 미리 작성된 Mock 응답입니다.</footer>
        </section>
      )}
    </>
  );
}
