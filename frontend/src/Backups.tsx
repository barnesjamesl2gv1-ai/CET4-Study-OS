import React from 'react';

type Backup={id:string;created_at:string;backup_kind:string;verified:number};

export function Backups(){
  const [items,setItems]=React.useState<Backup[]>([]),[status,setStatus]=React.useState(''),[busy,setBusy]=React.useState(false);
  const [file,setFile]=React.useState<File|null>(null);
  const refresh=React.useCallback(async()=>{const response=await fetch('/api/backups');if(response.ok)setItems(await response.json());},[]);
  React.useEffect(()=>{refresh().catch(e=>setStatus(String(e)));},[refresh]);
  async function create(){setBusy(true);setStatus('正在备份…');try{const response=await fetch('/api/backups',{method:'POST'});if(!response.ok)throw new Error((await response.json()).detail);await refresh();setStatus('备份已创建并校验');}catch(e){setStatus(`备份失败：${String(e)}`);}finally{setBusy(false);}}
  async function restore(){if(!file)return;if(!window.confirm('将使用选中的备份恢复学习数据。系统会先保存当前状态的恢复前备份。确认继续？'))return;setBusy(true);setStatus('正在验证并恢复…');try{const body=new FormData();body.append('file',file);body.append('confirmed','true');const response=await fetch('/api/backups/restore',{method:'POST',body});if(!response.ok)throw new Error((await response.json()).detail);await refresh();setStatus('恢复成功。请刷新页面查看恢复后的数据。');}catch(e){setStatus(`恢复失败：${String(e)}`);}finally{setBusy(false);}}
  return <section><h2>备份与恢复</h2><p>每天首次启动自动备份。立即备份包含数据库及已上传原始资料；导出的 ZIP 可复制到其他磁盘保存。</p><button disabled={busy} onClick={create}>立即备份</button><ul>{items.map(item=><li key={item.id}>{item.created_at} · {item.backup_kind} · {item.verified?'已验证':'未验证'} · <a href={`/api/backups/${item.id}/export`}>导出 ZIP</a></li>)}</ul><label>选择本地备份 ZIP<input type="file" accept=".zip" onChange={e=>setFile(e.target.files?.[0]||null)}/></label><button disabled={!file||busy} onClick={restore}>验证并恢复</button><p role="status">{status}</p></section>;
}
