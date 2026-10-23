import React from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

function App() {
  const [papers, setPapers] = React.useState<Array<{id:string,year:number,session_month:number,set_number:number,status:string}>>([]);
  React.useEffect(() => { fetch('/api/papers').then(r => r.json()).then(setPapers).catch(() => {}); }, []);
  return <main><header><strong>CET-4 Study OS</strong><span>本地学习空间 · M1 开发中</span></header><section><p className="eyebrow">自由训练</p><h1>按照自己的节奏，准备下一次四级。</h1><p>选择真题、听力或阅读，自由练习。日常训练不计分。</p></section><section><h2>我的试卷</h2>{papers.length ? <ul>{papers.map(p => <li key={p.id}>{p.year} 年 {p.session_month} 月 · 第 {p.set_number} 套 · {p.status}</li>)}</ul> : <p>还没有导入试卷。导入与训练功能正在开发。</p>}</section></main>;
}

createRoot(document.getElementById('root')!).render(<App />);
