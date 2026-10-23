import React from 'react';
import { createRoot } from 'react-dom/client';
import { AudioReview } from './AudioReview';
import { Practice } from './Practice';
import { Backups } from './Backups';
import './style.css';

type Paper = {id:string; year:number; session_month:number; set_number:number};
type Asset = {id:string; role:string; original_filename:string; verification_status:string};
type Question = {id:string; number:number; kind:string; prompt:string; passage_text:string; options:string[]; answer:string|null; rationale:string; version:number};
type Segment = {id:string;asset_id:string;start_ms:number;end_ms:number;ordinal:number};
const kinds:Record<string,string> = {listening_news:'听力新闻',listening_dialogue:'长对话',listening_passage:'听力篇章',cloze:'选词填空',matching:'段落匹配',careful:'仔细阅读',writing:'作文',translation:'翻译'};
async function api<T>(url:string, init?:RequestInit):Promise<T> {const response=await fetch(url,init);if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(body.detail||`HTTP ${response.status}`);}return response.json();}

function App(){
  const [papers,setPapers]=React.useState<Paper[]>([]),[selected,setSelected]=React.useState(''),[assets,setAssets]=React.useState<Asset[]>([]),[questions,setQuestions]=React.useState<Question[]>([]),[message,setMessage]=React.useState('');
  const [segments,setSegments]=React.useState<Segment[]>([]);
  const [year,setYear]=React.useState(new Date().getFullYear()),[month,setMonth]=React.useState(12),[paperSetNumber,setPaperSetNumber]=React.useState(1);
  const [number,setNumber]=React.useState(1),[kind,setKind]=React.useState('careful'),[prompt,setPrompt]=React.useState(''),[passage,setPassage]=React.useState(''),[options,setOptions]=React.useState(''),[answer,setAnswer]=React.useState(''),[rationale,setRationale]=React.useState(''),[existingId,setExistingId]=React.useState('');
  const refresh=React.useCallback(async()=>{setPapers(await api<Paper[]>('/api/papers'));if(selected){setAssets(await api<Asset[]>(`/api/papers/${selected}/assets`));setQuestions(await api<Question[]>(`/api/papers/${selected}/questions`));setSegments(await api<Segment[]>(`/api/papers/${selected}/segments`));}},[selected]);
  React.useEffect(()=>{refresh().catch(e=>setMessage(String(e)));},[refresh]);
  async function act(fn:()=>Promise<void>){setMessage('正在保存…');try{await fn();setMessage('已保存到本地');}catch(e){setMessage(`保存失败：${String(e)}`);}}
  async function create(event:React.FormEvent){event.preventDefault();await act(async()=>{const p=await api<Paper>('/api/papers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({year,session_month:month,set_number:paperSetNumber})});setSelected(p.id);setPapers(await api<Paper[]>('/api/papers'));});}
  async function upload(event:React.FormEvent<HTMLFormElement>,role:string){event.preventDefault();const input=event.currentTarget.querySelector('input[type=file]') as HTMLInputElement;const file=input.files?.[0];if(!file)return;await act(async()=>{const body=new FormData();body.append('role',role);body.append('file',file);await api(`/api/papers/${selected}/assets`,{method:'POST',body});input.value='';setAssets(await api<Asset[]>(`/api/papers/${selected}/assets`));});}
  async function saveQuestion(event:React.FormEvent){event.preventDefault();await act(async()=>{await api(`/api/papers/${selected}/questions`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({number,kind,prompt,passage_text:passage,options:options.split('\n').map(x=>x.trim()).filter(Boolean),answer:answer||null,rationale,existing_question_id:existingId||null,confirmed:true})});setQuestions(await api<Question[]>(`/api/papers/${selected}/questions`));});}
  return <main><header><strong>CET-4 Study OS</strong><span>本地学习空间</span></header><section className="hero"><p className="eyebrow">自由练习</p><h1>按自己的节奏准备四级。</h1><p>资料和学习记录保存在本机。日常训练不计分。</p></section>
  <section><h2>创建试卷</h2><form className="row" onSubmit={create}><label>年份<input type="number" min="2000" max="2100" value={year} onChange={e=>setYear(Number(e.target.value))}/></label><label>月份<select value={month} onChange={e=>setMonth(Number(e.target.value))}><option value="6">6 月</option><option value="12">12 月</option></select></label><label>套数<input type="number" min="1" value={paperSetNumber} onChange={e=>setPaperSetNumber(Number(e.target.value))}/></label><button>创建</button></form></section>
  <section><h2>选择试卷</h2><select aria-label="选择试卷" value={selected} onChange={e=>setSelected(e.target.value)}><option value="">请选择</option>{papers.map(p=><option key={p.id} value={p.id}>{p.year} 年 {p.session_month} 月 · 第 {p.set_number} 套</option>)}</select></section>
  {selected&&<><section><h2>上传原始资料</h2><p>分别上传试卷、MP3 与答案解析。上传后仍须人工核对题目、答案及音频对应关系。</p><div className="row">{([['paper','试卷'],['audio','听力音频'],['answer','答案解析']] as const).map(([role,label])=><form key={role} onSubmit={e=>upload(e,role)}><label>{label}<input type="file" required accept={role==='audio'?'.mp3':'.pdf,.docx,.png,.jpg,.jpeg'}/></label><button>上传</button></form>)}</div><ul>{assets.map(a=><li key={a.id}><a href={`/api/assets/${a.id}`}>{a.original_filename}</a> · {a.role} · {a.verification_status}</li>)}</ul></section>
  <section><h2>人工核对题目</h2><p>请对照原件填写。修订时填入旧题 ID，系统保留历史版本。</p><form className="grid" onSubmit={saveQuestion}><label>题号<input type="number" min="1" value={number} onChange={e=>setNumber(Number(e.target.value))}/></label><label>题型<select value={kind} onChange={e=>setKind(e.target.value)}>{Object.entries(kinds).map(([key,name])=><option key={key} value={key}>{name}</option>)}</select></label><label>文章或听力原文<textarea value={passage} onChange={e=>setPassage(e.target.value)}/></label><label>题干<textarea value={prompt} onChange={e=>setPrompt(e.target.value)}/></label><label>选项（每行一项）<textarea value={options} onChange={e=>setOptions(e.target.value)}/></label><label>答案<input value={answer} onChange={e=>setAnswer(e.target.value)}/></label><label>解析<textarea value={rationale} onChange={e=>setRationale(e.target.value)}/></label><label>旧题 ID（修订时填）<input value={existingId} onChange={e=>setExistingId(e.target.value)}/></label><button>已核对，保存题目</button></form><ul>{questions.map(q=><li key={q.id}>第 {q.number} 题 · {kinds[q.kind]} · 版本 {q.version} · ID {q.id}</li>)}</ul></section>
  <AudioReview paperId={selected} assets={assets} onConfirmed={()=>api<Segment[]>(`/api/papers/${selected}/segments`).then(setSegments).catch(e=>setMessage(String(e)))}/><Practice paperId={selected} questions={questions} segments={segments}/></>}
  <Backups/><p role="status">{message}</p></main>;
}
createRoot(document.getElementById('root')!).render(<App/>);
