"use client";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Mic, MicOff, PhoneOff, Send, Volume2, VolumeX } from "lucide-react";
import { agentsApi, type Agent, type TestResult } from "@/lib/agents";
import { Alert, Button, Input } from "@/components/ui";
import { SimulatedBadge, StatusBadge } from "../../_ui";
import { OutcomeCard } from "@/components/pipeline-ui";
import { pipelineApi, type Outcome } from "@/lib/pipeline";

type Msg = { role: "user" | "assistant"; content: string; result?: TestResult };

// Minimal typing for the (non-standard) Web Speech API recognition object.
type Recognition = {
  lang: string; interimResults: boolean; continuous: boolean; start(): void; stop(): void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null; onerror: ((e: { error: string }) => void) | null;
};
type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export default function TestLabPage() {
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [provider, setProvider] = useState<"" | "simulated" | "ollama">("");
  const [useKnowledge, setUseKnowledge] = useState(true);
  const [toolName, setToolName] = useState("");
  const [toolArgs, setToolArgs] = useState('{"lead_id": ""}');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const [sttSupported, setSttSupported] = useState(false);
  const rec = useRef<Recognition | null>(null);
  // Two-way browser voice preview: Web Speech API in, speechSynthesis out. Not a phone call.
  const search = useSearchParams();
  const leadId = search.get("lead") ?? undefined;
  const [speak, setSpeak] = useState(search.get("voice") === "1");
  const [ttsSupported, setTtsSupported] = useState(false);
  const [usedVoice, setUsedVoice] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [ending, setEnding] = useState(false);
  useEffect(() => { setTtsSupported(typeof window !== "undefined" && "speechSynthesis" in window); }, []);
  useEffect(() => () => { if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel(); }, []);

  function say(t: string) {
    if (!speak || !ttsSupported || !t) return;
    const u = new SpeechSynthesisUtterance(t);
    u.lang = agent?.language === "hi" ? "hi-IN" : agent?.language === "te" ? "te-IN" : "en-IN";
    u.rate = agent?.speaking_rate ?? 1;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  }

  async function endConversation() {
    if (!msgs.some((m) => m.role === "user")) { setError("Say or type something as the prospect first."); return; }
    setEnding(true); setError(null);
    if (ttsSupported) window.speechSynthesis.cancel();
    try {
      setOutcome(await pipelineApi.extract({
        transcript: msgs.filter((m) => m.content).map((m) => ({ role: m.role, text: m.content })),
        agent_id: id, lead_id: leadId, source: usedVoice ? "browser_voice" : "test_lab",
      }));
    } catch (e) { setError((e as Error).message); } finally { setEnding(false); }
  }

  useEffect(() => { agentsApi.get(id).then(setAgent).catch((e) => setError(e.message)); }, [id]);
  useEffect(() => { setSttSupported(!!recognitionCtor()); }, []);

  function toggleMic() {
    if (listening) { rec.current?.stop(); return; }
    const Ctor = recognitionCtor();
    if (!Ctor) return;
    const r = new Ctor();
    r.lang = agent?.language === "hi" ? "hi-IN" : agent?.language === "te" ? "te-IN" : "en-IN";
    r.interimResults = false; r.continuous = false;
    r.onresult = (e) => { setUsedVoice(true); setText((t) => `${t} ${Array.from(e.results).map((x) => x[0].transcript).join(" ")}`.trim()); };
    r.onend = () => setListening(false);
    r.onerror = (e) => { setError(`Browser speech recognition error: ${e.error}`); setListening(false); };
    rec.current = r; r.start(); setListening(true);
  }

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    let invoke: { name: string; arguments: Record<string, unknown> }[] = [];
    if (toolName) {
      try { invoke = [{ name: toolName, arguments: JSON.parse(toolArgs || "{}") }]; }
      catch { setError("Tool arguments must be valid JSON"); return; }
    }
    const history: Msg[] = [...msgs, { role: "user", content: text.trim() }];
    setMsgs(history); setText(""); setBusy(true); setError(null);
    try {
      const res = await agentsApi.test(id, {
        messages: history.filter((m) => m.content).map(({ role, content }) => ({ role, content })),
        provider: provider || undefined, use_knowledge: useKnowledge, invoke_tools: invoke, dry_run: true,
      });
      setMsgs([...history, { role: "assistant", content: res.reply, result: res }]);
      say(res.reply);
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="max-w-4xl space-y-5">
      <div>
        <Link href={`/agents/${id}`} className="text-sm text-accent">← Agent builder</Link>
        <h1 className="mt-1 flex items-center gap-3 text-xl font-semibold">Test lab {agent && <><span className="text-muted">· {agent.name}</span><StatusBadge status={agent.status} /></>}</h1>
        <p className="mt-1 text-sm text-muted">Text simulation of a conversation turn. Every run is logged. Side-effect tools run in dry-run mode here.</p>
        <p className="mt-2 inline-flex items-center gap-2 rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800">Browser voice preview — not a phone call. Nobody is contacted.</p>
        {leadId && <p className="mt-1 text-xs text-muted">Outcome will be written to lead {leadId.slice(0, 8)}… when you end the conversation.</p>}
      </div>
      {error && <Alert>{error}</Alert>}

      <div className="card flex flex-wrap items-end gap-4 p-4 text-sm">
        <div><label className="label" htmlFor="t-prov">Provider</label>
          <select id="t-prov" value={provider} onChange={(e) => setProvider(e.target.value as typeof provider)} className="h-10 rounded-lg border border-line bg-bg px-3">
            <option value="">Agent default</option><option value="simulated">Simulated (template, no AI)</option><option value="ollama">Ollama</option>
          </select></div>
        <label className="flex items-center gap-2 pb-2"><input type="checkbox" checked={useKnowledge} onChange={(e) => setUseKnowledge(e.target.checked)} />Use knowledge</label>
        <div><label className="label" htmlFor="t-tool">Invoke tool (optional)</label>
          <select id="t-tool" value={toolName} onChange={(e) => setToolName(e.target.value)} className="h-10 rounded-lg border border-line bg-bg px-3">
            <option value="">None</option>
            {["crm_lookup", "create_note", "book_callback", "schedule_outbound_call"].map((t) => <option key={t} value={t}>{t}{agent?.tools?.includes(t) ? "" : " (not allowed)"}</option>)}
          </select></div>
        {toolName && <div className="min-w-60 flex-1"><label className="label" htmlFor="t-args">Arguments (JSON)</label><Input id="t-args" className="h-10 font-mono text-xs" value={toolArgs} onChange={(e) => setToolArgs(e.target.value)} /></div>}
      </div>

      <div className="card space-y-4 p-5">
        {msgs.length === 0 && <p className="text-sm text-muted">Send a message to start.</p>}
        {msgs.map((m, i) => (
          <div key={i} className={m.role === "user" ? "ml-auto max-w-[80%] rounded-2xl bg-accent px-4 py-2 text-sm text-white" : "max-w-[90%] space-y-2"}>
            {m.role === "user" ? m.content : (
              <>
                <div className="whitespace-pre-wrap rounded-2xl bg-raised px-4 py-2 text-sm">{m.content || <span className="text-muted">(no reply)</span>}</div>
                {m.result && <RunMeta r={m.result} />}
              </>
            )}
          </div>
        ))}
        {busy && <p className="text-sm text-muted">Running…</p>}
      </div>

      <form onSubmit={send} className="flex items-center gap-2">
        <Input aria-label="Message" value={text} onChange={(e) => setText(e.target.value)} placeholder="Type as the customer…" />
        <Button type="button" variant="outline" disabled={!sttSupported} onClick={toggleMic} aria-label="Browser speech-to-text"
          title={sttSupported ? "Browser STT preview (Web Speech API; audio is processed by your browser vendor, not Leadex)" : "Speech recognition not supported in this browser"}>
          {listening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
        </Button>
        <Button type="button" variant="outline" disabled={!ttsSupported} onClick={() => { if (speak) window.speechSynthesis.cancel(); setSpeak(!speak); }}
          aria-label="Speak agent replies" title={ttsSupported ? "Speak the agent's replies with your browser's speech synthesis" : "Speech synthesis not supported"}>
          {speak ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
        </Button>
        <Button type="submit" loading={busy}><Send className="h-4 w-4" />Send</Button>
      </form>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" loading={ending} onClick={endConversation}><PhoneOff className="h-4 w-4" />End conversation &amp; extract outcome</Button>
        <span className="text-xs text-muted">Extracts interest, budget (only if the prospect stated it), timeline, decision maker and next step.</span>
      </div>
      {outcome && <OutcomeCard o={outcome} />}
      <p className="text-xs text-muted">Mic button: <b>browser STT preview</b> only — uses your browser&apos;s Web Speech API to fill the text box; the speaker button reads replies aloud with your browser&apos;s speech synthesis. This is a browser voice preview, not a phone call and not the production voice pipeline.</p>
    </div>
  );
}

function RunMeta({ r }: { r: TestResult }) {
  return (
    <div className="space-y-2 rounded-xl border border-line p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2 text-muted">
        <SimulatedBadge on={r.simulated} />
        <span className={r.status === "ok" ? "text-green-700" : "text-danger"}>{r.status.replace(/_/g, " ")}</span>
        <span>{r.provider}{r.model ? `/${r.model}` : ""}</span><span>{r.latency_ms} ms</span><span>retrieval: {r.retrieval_mode}</span>
      </div>
      {r.error && <p className="text-danger">{r.error}</p>}
      {r.tool_calls.length > 0 && (
        <div><p className="font-medium">Tool calls</p>
          <ul className="mt-1 space-y-1 font-mono">
            {r.tool_calls.map((t, i) => <li key={i} className={t.ok ? "text-green-800" : "text-danger"}>{t.name} → {t.ok ? JSON.stringify(t.result) : t.error}</li>)}
          </ul></div>
      )}
      {r.citations.length > 0 && (
        <div><p className="font-medium">Citations</p>
          <ol className="mt-1 list-decimal space-y-1 pl-4">
            {r.citations.map((c) => <li key={c.chunk_id}><b>{c.title}</b> <span className="text-muted">(score {c.score})</span> — {c.text.slice(0, 160)}</li>)}
          </ol></div>
      )}
    </div>
  );
}
