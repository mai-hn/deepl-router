import { useState, type FormEvent } from "react";
import { translate } from "../../api/endpoints";
import type { TranslateResponse } from "../../api/types";

const LANGUAGES = [["", "自动检测"], ["EN", "英语"], ["ZH", "中文"], ["JA", "日语"], ["KO", "韩语"], ["DE", "德语"], ["FR", "法语"], ["ES", "西班牙语"]] as const;

export default function PlaygroundPage() {
  const [text, setText] = useState("Hello, translate this sentence for me.");
  const [sourceLang, setSourceLang] = useState("");
  const [targetLang, setTargetLang] = useState("ZH");
  const [result, setResult] = useState<TranslateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!text.trim()) return;
    setLoading(true); setError(null);
    try { setResult(await translate({ text: text.trim(), source_lang: sourceLang || undefined, target_lang: targetLang })); }
    catch (reason) { setResult(null); setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setLoading(false); }
  };
  return (
    <section className="panel">
      <div className="panel-heading"><div className="heading-icon purple">文</div><div><h2>翻译测试</h2><p>使用当前路由策略发起真实的下游翻译请求。结果会记录到请求日志。</p></div></div>
      <form onSubmit={(event) => void submit(event)} className="playground-grid">
        <label>原文<textarea value={text} onChange={(event) => setText(event.target.value)} placeholder="输入要翻译的文本" required /></label>
        <div className="form-grid"><label>源语言<select value={sourceLang} onChange={(event) => setSourceLang(event.target.value)}>{LANGUAGES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>目标语言<select value={targetLang} onChange={(event) => setTargetLang(event.target.value)}>{LANGUAGES.filter(([value]) => value).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></div>
        <button className="button yellow" type="submit" disabled={loading || !text.trim()}>{loading ? "翻译中…" : "发送翻译请求"}</button>
      </form>
      <div className="translation-result" aria-live="polite"><span className="eyebrow">RESULT</span>{loading && <p className="muted">正在等待上游路由响应…</p>}{error && <p className="error-message">请求失败：{error}</p>}{result && <><p>{Array.isArray(result.data) ? result.data.join("\n") : result.data}</p><div className="muted mono">由 {result.providers.join("、")} 返回</div></>}{!loading && !error && !result && <p className="muted">翻译结果会显示在这里。</p>}</div>
    </section>
  );
}
