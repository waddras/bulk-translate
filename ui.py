#!/usr/bin/env python3
"""Server-rendered HTML/JS single-page UI for the bulk translator."""

HTML_UI = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Bulk Subtitle Translator</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0f1117;--surface:#1a1d27;--border:#2a2d3d;--text:#e2e4f0;--muted:#6b7280;--accent:#6366f1;--green:#22c55e;--red:#ef4444;--yellow:#f59e0b;--font:system-ui,-apple-system,sans-serif;--mono:'SF Mono','Fira Code','Consolas',monospace}
body{background:var(--bg);color:var(--text);font-family:var(--font);font-size:14px;min-height:100vh}
.layout{display:grid;grid-template-columns:1fr 300px;height:100vh;overflow:hidden}
.main{display:flex;flex-direction:column;overflow:hidden;border-right:1px solid var(--border)}
.sidebar{display:flex;flex-direction:column;overflow:hidden;background:var(--surface)}
.header{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px;background:var(--surface)}
.header h1{font-size:15px;font-weight:700}
.badge{font-size:10px;padding:3px 8px;border-radius:99px;background:var(--accent);color:#fff;font-weight:600}
.tabs{display:flex;border-bottom:1px solid var(--border);background:var(--surface);padding:0 8px;flex-wrap:wrap}
.tab{padding:10px 14px;cursor:pointer;font-size:13px;color:var(--muted);border-bottom:2px solid transparent;transition:all .2s;font-weight:500}
.tab:hover{color:var(--text)}.tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.panel{flex:1;overflow-y:auto;padding:20px;display:none}.panel.active{display:block}
.path-bar{display:flex;gap:8px;margin-bottom:16px}
.path-bar input{flex:1;background:var(--surface);border:1px solid var(--border);color:var(--text);padding:9px 12px;border-radius:6px;font-family:var(--mono);font-size:13px}
.path-bar button{background:var(--accent);color:#fff;border:none;padding:9px 18px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:500}
.dir-list{display:flex;flex-direction:column;gap:4px;margin-bottom:16px}
.dir-item{display:flex;align-items:center;gap:10px;padding:9px 12px;background:var(--surface);border:1px solid var(--border);border-radius:6px;cursor:pointer;color:var(--muted);transition:all .15s;font-size:13px}
.dir-item:hover{border-color:var(--accent);color:var(--text);background:#1e2035}
.file-list{display:flex;flex-direction:column;gap:4px}
.file-item{display:flex;align-items:center;gap:12px;padding:9px 12px;background:var(--surface);border:1px solid var(--border);border-radius:6px;cursor:pointer;transition:all .15s}
.file-item:hover{border-color:#4b5563}.file-item.sel{border-color:var(--accent);background:#1e2035}
.file-item input[type=checkbox]{accent-color:var(--accent);width:16px;height:16px;cursor:pointer}
.file-name{flex:1;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.file-size{color:var(--muted);font-size:12px;white-space:nowrap;font-family:var(--mono)}
.file-actions{display:flex;gap:4px}
.file-actions button{background:none;border:1px solid var(--border);color:var(--muted);padding:2px 6px;border-radius:4px;cursor:pointer;font-size:11px}
.file-actions button:hover{border-color:var(--accent);color:var(--text)}
.toolbar{display:flex;gap:8px;margin-bottom:12px;align-items:center;flex-wrap:wrap}
.toolbar button{font-size:12px;padding:5px 10px;border-radius:5px;cursor:pointer;border:1px solid var(--border);background:var(--surface);color:var(--text)}
.toolbar button:hover{border-color:var(--accent)}
.toolbar .del-btn{border-color:var(--red);color:var(--red)}
.toolbar .del-btn:hover{background:#3a1010}
.sec-label{font-size:11px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase;margin-bottom:8px;font-weight:600}
.empty{color:var(--muted);font-size:13px;text-align:center;padding:24px}
.quota-table{width:100%;border-collapse:collapse}
.quota-table th{text-align:left;padding:8px 10px;color:var(--muted);font-size:11px;border-bottom:1px solid var(--border);text-transform:uppercase;letter-spacing:.05em}
.quota-table td{padding:9px 10px;border-bottom:1px solid var(--border);font-size:13px;vertical-align:middle}
.bar{height:5px;background:var(--border);border-radius:3px;margin-top:5px}.bar-fill{height:100%;border-radius:3px;transition:width .3s}
.badge-oos{font-size:10px;padding:3px 7px;border-radius:4px;background:var(--red);color:#fff;font-weight:600}
.badge-ok{font-size:10px;padding:3px 7px;border-radius:4px;background:#1a3a1a;color:var(--green);font-weight:600}
.btn-sm{font-size:11px;padding:4px 8px;border-radius:4px;border:1px solid var(--border);background:var(--surface);color:var(--text);cursor:pointer;transition:all .15s}
.btn-sm:hover{border-color:var(--accent);color:var(--accent)}
.reset-info{font-size:11px;color:var(--muted);margin-top:12px;padding:8px 10px;background:var(--surface);border-radius:6px;border:1px solid var(--border)}
.key-form{display:flex;flex-direction:column;gap:8px;margin-bottom:16px;padding:14px;background:var(--surface);border:1px solid var(--border);border-radius:8px}
.key-form input{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:9px 12px;border-radius:6px;font-size:13px}
.key-form button{background:var(--accent);color:#fff;border:none;padding:9px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:500}
.key-row{display:flex;align-items:center;gap:8px;padding:9px 12px;background:var(--surface);border:1px solid var(--border);border-radius:6px;margin-bottom:4px}
.key-email{flex:1;font-size:13px}.key-inactive{opacity:.4}
.settings-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}
.field{display:flex;flex-direction:column;gap:5px}
.field label{font-size:12px;color:var(--muted);font-weight:500}
.field input,.field select{background:var(--surface);border:1px solid var(--border);color:var(--text);padding:9px 11px;border-radius:6px;font-family:var(--mono);font-size:13px}
.field input:focus,.field select:focus{outline:none;border-color:var(--accent)}
.model-row{display:flex;align-items:center;gap:6px;padding:8px 10px;background:var(--surface);border:1px solid var(--border);border-radius:6px;margin-bottom:4px}
.model-row input{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:6px 8px;border-radius:5px;font-family:var(--mono);font-size:12px}
.model-row input:focus{outline:none;border-color:var(--accent)}
.model-id{flex:2;min-width:120px}.model-num{width:55px;text-align:center}.model-pri{width:40px;text-align:center}
.btn-save{background:var(--accent);color:#fff;border:none;padding:10px 22px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600}
.btn-save:hover{background:#4f52d6}
.btn-danger{background:none;border:1px solid var(--red);color:var(--red);padding:4px 8px;border-radius:5px;cursor:pointer;font-size:11px}
.btn-danger:hover{background:#3a1010}
.btn-muted{background:none;border:1px solid var(--border);color:var(--muted);padding:5px 10px;border-radius:5px;cursor:pointer;font-size:12px}
.btn-muted:hover{border-color:var(--accent);color:var(--text)}
.model-header{display:flex;align-items:center;gap:6px;padding:4px 10px;font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px}
.pri-err{color:var(--red);font-size:12px;margin-top:6px;display:none}
.log-box{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;font-family:var(--mono);font-size:12px;line-height:1.9;white-space:pre-wrap;word-break:break-word;overflow-y:auto;max-height:calc(100vh - 180px)}
.log-line{display:block;padding:1px 0}
.log-ok{color:var(--green)}.log-err{color:var(--red)}.log-sep{color:var(--accent);font-weight:700;padding:4px 0}.log-warn{color:var(--yellow)}.log-info{color:#8b95a8}
.hist-item{display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--surface);border:1px solid var(--border);border-radius:6px;margin-bottom:4px;cursor:pointer;transition:all .15s}
.hist-item:hover{border-color:var(--accent)}.hist-ts{font-family:var(--mono);font-size:12px;color:var(--muted)}.hist-status{font-size:11px;font-weight:600;padding:2px 6px;border-radius:4px}
.hist-ok{background:#1a3a1a;color:var(--green)}.hist-err{background:#3a1a1a;color:var(--red)}.hist-cancel{background:#3a3a1a;color:var(--yellow)}
.sb-header{padding:16px;border-bottom:1px solid var(--border)}.sb-header h2{font-size:14px;font-weight:700}
.q-count{font-size:12px;color:var(--muted);margin-top:4px}
.queue-list{flex:1;overflow-y:auto;padding:12px}
.q-item{display:flex;align-items:center;justify-content:space-between;padding:7px 10px;background:var(--bg);border:1px solid var(--border);border-radius:6px;margin-bottom:4px;font-size:12px}
.q-name{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:var(--mono)}
.rm{color:var(--muted);background:none;border:none;cursor:pointer;font-size:16px;padding:0 4px}.rm:hover{color:var(--red)}
.sb-footer{padding:12px;border-top:1px solid var(--border);display:flex;flex-direction:column;gap:8px}
.analyze-btn{width:100%;padding:12px;background:#1a3a1a;color:var(--green);border:1px solid var(--green);border-radius:8px;cursor:pointer;font-size:14px;font-weight:700}
.analyze-btn:disabled{opacity:.35;cursor:not-allowed}.analyze-btn:hover:not(:disabled){background:#1f4a1f}
.exec-btn{width:100%;padding:12px;background:var(--accent);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;font-weight:700}
.exec-btn:disabled{opacity:.35;cursor:not-allowed}.exec-btn:hover:not(:disabled){background:#4f52d6}
.cancel-btn{width:100%;padding:9px;background:none;border:1px solid var(--red);color:var(--red);border-radius:8px;cursor:pointer;font-size:13px;display:none;font-weight:500}
.cancel-btn:hover{background:#3a1010}
.dot{width:9px;height:9px;border-radius:50%}.dot-green{background:var(--green);box-shadow:0 0 6px var(--green)}.dot-yellow{background:var(--yellow);animation:pulse 1s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.toast{position:fixed;bottom:20px;right:20px;background:var(--surface);border:1px solid var(--border);color:var(--text);padding:12px 18px;border-radius:8px;font-size:13px;z-index:999;opacity:0;transition:opacity .3s;box-shadow:0 4px 12px rgba(0,0,0,.4)}.toast.show{opacity:1}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.7);z-index:1000;align-items:center;justify-content:center}
.modal-box{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:24px;max-width:400px;width:90%;box-shadow:0 8px 24px rgba(0,0,0,.6)}
.modal-box h3{font-size:15px;margin-bottom:10px}
.modal-box p{font-size:13px;color:var(--muted);line-height:1.6;margin-bottom:16px}
.modal-box .spinner{display:inline-block;width:14px;height:14px;border:2px solid var(--muted);border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;margin-right:8px;vertical-align:middle}
@keyframes spin{to{transform:rotate(360deg)}}
.modal-actions{display:flex;gap:10px;justify-content:flex-end}
.modal-actions button{padding:8px 16px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:500}
.kill-btn{background:var(--red);color:#fff;border:none}
.kill-btn:hover{background:#dc2626}
.wait-btn{background:var(--surface);color:var(--text);border:1px solid var(--border)}
.wait-btn:hover{border-color:var(--accent)}
</style></head>
<body>
<div class="layout">
<div class="main">
  <div class="header"><div class="dot dot-green" id="status-dot"></div><h1>Bulk Subtitle Translator</h1><span class="badge">v2.2</span></div>
  <div class="tabs">
    <div class="tab active" onclick="showTab('browser')">Browser</div>
    <div class="tab" onclick="showTab('quota')">Quotas</div>
    <div class="tab" onclick="showTab('keys')">Keys</div>
    <div class="tab" onclick="showTab('settings')">Settings</div>
    <div class="tab" onclick="showTab('log')">Log</div>
    <div class="tab" onclick="showTab('history')">History</div>
  </div>
  <div id="tab-browser" class="panel active">
    <div class="path-bar"><input id="path-input" value="/mnt/secure/srv/hddmedia/anime" onkeydown="if(event.key==='Enter')navigate()"><button onclick="navigate()">Go</button></div>
    <div id="dir-list" class="dir-list"></div>
    <div class="toolbar"><button onclick="selectAll()">Select All</button><button onclick="unselectAll()">Unselect All</button><button class="del-btn" onclick="deleteSelected()">Delete Selected</button></div>
    <div class="sec-label">Subtitle Files (.srt / .ass)</div>
    <div id="file-list" class="file-list"></div>
  </div>
  <div id="tab-quota" class="panel">
    <div class="sec-label" style="margin-bottom:12px">Model Quotas - Period: <span id="quota-date"></span></div>
    <table class="quota-table"><thead><tr><th>Pri</th><th>Model</th><th>Used/Limit</th><th>Fails</th><th>Status</th><th>Actions</th></tr></thead><tbody id="quota-tbody"></tbody></table>
    <div class="reset-info" id="reset-info"></div>
  </div>
  <div id="tab-keys" class="panel">
    <div class="sec-label" style="margin-bottom:10px">Add API Key</div>
    <div class="key-form"><input id="key-email" placeholder="Email / label"><input id="key-value" type="password" placeholder="Gemini API Key"><button onclick="addKey()">Add Key</button></div>
    <div class="sec-label" style="margin-bottom:10px">Saved Keys</div>
    <div id="keys-list"></div>
  </div>
  <div id="tab-settings" class="panel">
    <div class="sec-label" style="margin-bottom:12px">Translation Parameters</div>
    <div class="settings-grid">
      <div class="field"><label>NUM_CHUNKS (split blob into N)</label><input id="s-numchunks" type="number" min="1"></div>
      <div class="field"><label>GEMINI_MAX_OUTPUT (0=default)</label><input id="s-gmaxout" type="number"></div>
      <div class="field"><label>OOS_THRESHOLD</label><input id="s-oos" type="number"></div>
      <div class="field"><label>RETRY_ATTEMPTS</label><input id="s-retry" type="number"></div>
      <div class="field"><label>RETRY_COOLDOWN (sec)</label><input id="s-cool" type="number"></div>
      <div class="field"><label>MAX_BLOB_LINES</label><input id="s-maxblob" type="number"></div>
      <div class="field"><label>File Conflict</label><select id="s-conflict"><option value="overwrite">Overwrite</option><option value="rename">Rename (_1, _2...)</option></select></div>
    </div>
    <div class="sec-label" style="margin-bottom:8px">Model Pool</div>
    <div class="model-header"><span style="width:40px">Pri</span><span style="flex:2">Model ID</span><span style="width:55px">RPD</span><span style="width:55px">RPM</span><span style="width:30px"></span></div>
    <div id="model-pool-list"></div>
    <div class="pri-err" id="pri-err">Duplicate priority numbers. Each must be unique.</div>
    <div style="display:flex;gap:10px;margin-top:10px"><button class="btn-muted" onclick="addModelRow()">+ Add Model</button><button class="btn-save" id="save-btn" onclick="saveSettings()">Save Settings</button></div>
  </div>
  <div id="tab-log" class="panel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><div class="sec-label">Live Job Log</div><button class="btn-sm" onclick="loadLog()">Refresh</button></div>
    <div id="log-box" class="log-box">No job logs yet.</div>
  </div>
  <div id="tab-history" class="panel">
    <div class="sec-label" style="margin-bottom:12px">Past Jobs</div>
    <div id="history-list"></div>
    <div id="history-detail" style="display:none;margin-top:16px"><button class="btn-sm" onclick="document.getElementById('history-detail').style.display='none'">Back to list</button><div id="history-log" class="log-box" style="margin-top:10px"></div></div>
  </div>
</div>
<div class="sidebar">
  <div class="sb-header"><h2>Queue</h2><div class="q-count"><span id="q-count">0</span> files selected</div></div>
  <div class="queue-list" id="queue-list"><div class="empty">No files queued</div></div>
  <div class="sb-footer">
    <button class="analyze-btn" id="analyze-btn" onclick="runAnalyze()" disabled>Analyze</button>
    <button class="exec-btn" id="translate-btn" onclick="runTranslate()" disabled>Translate</button>
    <button class="cancel-btn" id="cancel-btn" onclick="cancelJob()">Cancel</button>
  </div>
</div>
</div>
<div class="toast" id="toast"></div>
<div class="modal" id="cancel-modal">
  <div class="modal-box">
    <h3>Cancelling Job</h3>
    <p><span class="spinner"></span>Saving translated subtitles from completed chunks... This may take a moment while the current chunk finishes.</p>
    <div class="modal-actions">
      <button class="wait-btn" onclick="document.getElementById('cancel-modal').style.display='none'">Wait</button>
      <button class="kill-btn" onclick="forceKill()">Kill Process Now</button>
    </div>
  </div>
</div>
<script>
let selected=[],currentPath='/mnt/secure/srv/hddmedia/anime',pollTimer=null,jobRunning=false,translatePhase=false;
function toast(msg,ok=true){const el=document.getElementById('toast');el.textContent=msg;el.style.borderColor=ok?'var(--green)':'var(--red)';el.classList.add('show');setTimeout(()=>el.classList.remove('show'),3500);}
function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function showTab(name){document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));document.getElementById('tab-'+name).classList.add('active');const tabs=['browser','quota','keys','settings','log','history'];document.querySelectorAll('.tab')[tabs.indexOf(name)].classList.add('active');if(name==='quota')loadQuota();if(name==='keys')loadKeys();if(name==='settings')loadSettings();if(name==='log')loadLog();if(name==='history')loadHistory();}

async function navigate(path){
  if(path!==undefined)currentPath=path;else currentPath=document.getElementById('path-input').value.trim();
  document.getElementById('path-input').value=currentPath;
  const res=await fetch('/api/browse?path='+encodeURIComponent(currentPath));
  if(!res.ok){toast('Cannot open path',false);return;}
  const data=await res.json();
  const dirEl=document.getElementById('dir-list');dirEl.innerHTML='';
  if(data.current!==data.parent){const up=document.createElement('div');up.className='dir-item';up.textContent='.. (Go Up)';up.onclick=()=>navigate(data.parent);dirEl.appendChild(up);}
  data.dirs.forEach(d=>{const el=document.createElement('div');el.className='dir-item';el.textContent=d.name;el.onclick=()=>navigate(d.path);dirEl.appendChild(el);});
  const fileEl=document.getElementById('file-list');fileEl.innerHTML='';
  if(!data.files.length){fileEl.innerHTML='<div class="empty">No subtitle files here</div>';return;}
  data.files.forEach(f=>{
    const isSel=selected.includes(f.path);const el=document.createElement('div');el.className='file-item'+(isSel?' sel':'');
    el.innerHTML=`<input type="checkbox" ${isSel?'checked':''} data-path="${escHtml(f.path)}"><span class="file-name">${escHtml(f.name)}</span><span class="file-size">${f.size_kb} KB</span><div class="file-actions"><button onclick="renameFile('${escHtml(f.path)}','${escHtml(f.name)}')">ren</button></div>`;
    const cb=el.querySelector('input');
    cb.onchange=()=>{if(cb.checked){if(!selected.includes(f.path))selected.push(f.path);}else{selected=selected.filter(p=>p!==f.path);}el.classList.toggle('sel',cb.checked);updateQueue();};
    fileEl.appendChild(el);
  });
}
function selectAll(){document.querySelectorAll('#file-list input[type=checkbox]').forEach(cb=>{if(!cb.checked){cb.checked=true;cb.onchange();}});}
function unselectAll(){document.querySelectorAll('#file-list input[type=checkbox]').forEach(cb=>{if(cb.checked){cb.checked=false;cb.onchange();}});}
async function deleteSelected(){
  const sel=Array.from(document.querySelectorAll('#file-list input[type=checkbox]:checked')).map(cb=>cb.dataset.path);
  if(!sel.length){toast('Nothing selected',false);return;}
  if(!confirm(`Delete ${sel.length} file(s)?`))return;
  const res=await fetch('/api/file/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paths:sel})});
  if(res.ok){const r=await res.json();toast(`Deleted ${r.deleted} files`);selected=selected.filter(p=>!sel.includes(p));updateQueue();navigate();}
  else toast('Delete failed',false);
}
async function renameFile(path,oldName){
  const newName=prompt('New filename:',oldName);if(!newName||newName===oldName)return;
  const res=await fetch('/api/file/rename',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path,new_name:newName})});
  if(res.ok){toast('Renamed');navigate();}else{const e=await res.json();toast(e.detail||'Rename failed',false);}
}
function updateQueue(){
  const el=document.getElementById('queue-list');document.getElementById('q-count').textContent=selected.length;
  document.getElementById('analyze-btn').disabled=selected.length===0||jobRunning;
  if(!jobRunning)document.getElementById('translate-btn').disabled=true;
  if(!selected.length){el.innerHTML='<div class="empty">No files queued</div>';return;}
  el.innerHTML=selected.map(p=>{const name=p.split('/').pop();return`<div class="q-item"><span class="q-name" title="${escHtml(p)}">${escHtml(name)}</span><button class="rm" onclick="removeFile(this)" data-path="${escHtml(p)}">x</button></div>`;}).join('');
  if(!jobRunning)checkAnalyzeStatus();
}
function removeFile(btn){const path=btn.dataset.path;selected=selected.filter(p=>p!==path);updateQueue();navigate();}
async function checkAnalyzeStatus(){const res=await fetch('/api/analyze-status').then(r=>r.json());document.getElementById('translate-btn').disabled=!res.ready||jobRunning||translatePhase;}

async function runAnalyze(){
  if(!selected.length)return;
  const res=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files:selected})});
  if(res.ok){setJobRunning(true);showTab('log');startSSE();}
  else{const err=await res.json();toast('Error: '+(err.detail||'Unknown'),false);}
}
async function runTranslate(){
  translatePhase=true;
  document.getElementById('translate-btn').disabled=true;
  const res=await fetch('/api/translate',{method:'POST'});
  if(res.ok){setJobRunning(true);showTab('log');startSSE();}
  else{const err=await res.json();toast('Error: '+(err.detail||'Unknown'),false);translatePhase=false;document.getElementById('translate-btn').disabled=false;}
}
async function cancelJob(){
  document.getElementById('cancel-btn').disabled=true;
  document.getElementById('cancel-modal').style.display='flex';
  const res=await fetch('/api/job/cancel',{method:'POST'});
  if(!res.ok){toast('No job running',false);document.getElementById('cancel-modal').style.display='none';document.getElementById('cancel-btn').disabled=false;}
}
async function forceKill(){
  document.getElementById('cancel-modal').style.display='none';
  const res=await fetch('/api/job/force-kill',{method:'POST'});
  if(res.ok){toast('Service restarting...');setTimeout(()=>location.reload(),3000);}
  else toast('Force kill failed',false);
}
function setJobRunning(running){
  jobRunning=running;
  document.getElementById('cancel-btn').style.display=running?'block':'none';
  document.getElementById('status-dot').className='dot '+(running?'dot-yellow':'dot-green');
  document.getElementById('analyze-btn').disabled=jobRunning||selected.length===0;
  if(running){document.getElementById('translate-btn').disabled=true;}
}
let evtSource=null;
function startSSE(){
  if(evtSource)evtSource.close();
  const box=document.getElementById('log-box');box.innerHTML='';
  evtSource=new EventSource('/api/job-stream');
  evtSource.onmessage=function(e){
    const msg=JSON.parse(e.data);
    if(msg.type==='log'){
      let cls='log-info';const line=msg.line;
      if(line.includes('===')||line.startsWith('PHASE')||line.startsWith('ANALYZE')||line.startsWith('TRANSLATE'))cls='log-sep';
      else if(line.includes('FAIL')||line.includes('ERROR')||line.includes('OOS')||line.startsWith('  skipped'))cls='log-err';
      else if(line.includes('SUCCESS')||line.includes('COMPLETE')||line.includes('Written')||line.startsWith('  done')||line.includes('Ready to translate'))cls='log-ok';
      else if(line.includes('WARN')||line.includes('cancel')||line.includes('Retry')||line.startsWith('DEDUP'))cls='log-warn';
      box.innerHTML+=`<span class="log-line ${cls}">${escHtml(line)}</span>`;
      box.scrollTop=box.scrollHeight;
    } else if(msg.type==='status'){
      setJobRunning(msg.running);
      if(!msg.running&&msg.done){
        evtSource.close();evtSource=null;translatePhase=false;
        document.getElementById('cancel-modal').style.display='none';
        document.getElementById('cancel-btn').disabled=false;
        if(msg.error)toast('Job failed: '+msg.error,false);
        else if(msg.cancelled)toast('Job cancelled successfully');
        else toast('Done - '+(msg.completed_files||[]).length+' files written');
        checkAnalyzeStatus();
      }
    } else if(msg.type==='end'){
      if(evtSource){evtSource.close();evtSource=null;}
    }
  };
  evtSource.onerror=function(){if(evtSource){evtSource.close();evtSource=null;}setJobRunning(false);checkAnalyzeStatus();};
}
async function pollStatus(){
  const status=await fetch('/api/job-status').then(r=>r.json());
  setJobRunning(status.running);await loadLog();
  if(status.running){pollTimer=setTimeout(pollStatus,2000);}
  else{
    translatePhase=false;
    document.getElementById('cancel-modal').style.display='none';
    document.getElementById('cancel-btn').disabled=false;
    if(status.error)toast('Job failed: '+status.error,false);
    else if(status.cancelled)toast('Job cancelled successfully');
    else if(status.done)toast('Done - '+(status.completed_files||[]).length+' files written');
    checkAnalyzeStatus();
  }
}
async function loadLog(){
  const status=await fetch('/api/job-status').then(r=>r.json());const box=document.getElementById('log-box');
  if(!status.log||!status.log.length){box.textContent='No logs yet.';return;}
  box.innerHTML=status.log.map(line=>{let cls='log-info';
    if(line.includes('===')||line.startsWith('PHASE')||line.startsWith('ANALYZE')||line.startsWith('TRANSLATE'))cls='log-sep';
    else if(line.includes('FAIL')||line.includes('ERROR')||line.includes('OOS')||line.startsWith('  skipped'))cls='log-err';
    else if(line.includes('SUCCESS')||line.includes('COMPLETE')||line.includes('Written')||line.startsWith('  done')||line.includes('Ready to translate'))cls='log-ok';
    else if(line.includes('WARN')||line.includes('cancel')||line.includes('Retry')||line.startsWith('DEDUP'))cls='log-warn';
    return`<span class="log-line ${cls}">${escHtml(line)}</span>`;}).join('');
  if(status.error)box.innerHTML+=`<span class="log-line log-err">FATAL: ${escHtml(status.error)}</span>`;
  box.scrollTop=box.scrollHeight;
}
async function loadQuota(){
  const res=await fetch('/api/usage').then(r=>r.json());
  document.getElementById('quota-date').textContent=res.date;
  document.getElementById('reset-info').textContent='Next reset: '+(res.next_reset||'10:30 AM AST');
  document.getElementById('quota-tbody').innerHTML=res.models.map(m=>{
    const pct=Math.min(100,Math.round(m.used_today/m.rpd_limit*100));const col=pct>80?'#ef4444':pct>50?'#f59e0b':'#22c55e';
    return`<tr><td style="font-family:var(--mono);text-align:center">${m.priority||'-'}</td><td style="font-size:12px;font-family:var(--mono)">${m.model}</td><td>${m.used_today}/${m.rpd_limit}<div class="bar"><div class="bar-fill" style="width:${pct}%;background:${col}"></div></div></td><td>${m.failures}</td><td>${m.out_of_service?'<span class="badge-oos">OOS</span>':'<span class="badge-ok">OK</span>'}</td><td><button class="btn-sm" onclick="resetOOS('${m.model}')">Reset OOS</button> <button class="btn-sm" onclick="resetAll('${m.model}')">Reset All</button></td></tr>`;}).join('');
}
async function resetOOS(m){await fetch('/api/usage/'+encodeURIComponent(m)+'/reset-oos',{method:'POST'});loadQuota();toast('OOS reset');}
async function resetAll(m){if(!confirm('Reset ALL for '+m+'?'))return;await fetch('/api/usage/'+encodeURIComponent(m)+'/reset-usage',{method:'POST'});loadQuota();toast('Reset');}
async function loadKeys(){
  const keys=await fetch('/api/keys').then(r=>r.json());const el=document.getElementById('keys-list');
  if(!keys.length){el.innerHTML='<div class="empty">No keys saved</div>';return;}
  el.innerHTML=keys.map(k=>`<div class="key-row ${k.active?'':'key-inactive'}"><span class="key-email">${escHtml(k.email)}</span><span style="font-size:11px;color:var(--muted)">${k.added}</span><button class="btn-sm" onclick="toggleKey(${k.id})">${k.active?'Disable':'Enable'}</button><button class="btn-sm btn-danger" onclick="deleteKey(${k.id})">Del</button></div>`).join('');
}
async function addKey(){const email=document.getElementById('key-email').value.trim(),key=document.getElementById('key-value').value.trim();if(!email||!key){toast('Enter email and key',false);return;}const res=await fetch('/api/keys',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,api_key:key})});if(res.ok){document.getElementById('key-email').value='';document.getElementById('key-value').value='';loadKeys();toast('Key added');}else{const e=await res.json();toast(e.detail,false);}}
async function toggleKey(id){await fetch('/api/keys/'+id+'/toggle',{method:'POST'});loadKeys();}
async function deleteKey(id){if(!confirm('Delete key?'))return;await fetch('/api/keys/'+id,{method:'DELETE'});loadKeys();toast('Deleted');}
async function loadSettings(){
  const s=await fetch('/api/settings').then(r=>r.json());
  document.getElementById('s-numchunks').value=s.NUM_CHUNKS;document.getElementById('s-gmaxout').value=s.GEMINI_MAX_OUTPUT_TOKENS;
  document.getElementById('s-oos').value=s.OOS_THRESHOLD;document.getElementById('s-retry').value=s.RETRY_ATTEMPTS;
  document.getElementById('s-cool').value=s.RETRY_COOLDOWN;document.getElementById('s-maxblob').value=s.MAX_BLOB_LINES;
  document.getElementById('s-conflict').value=s.FILE_CONFLICT||'overwrite';
  renderModelPool(s.MODEL_POOL);
}
function renderModelPool(pool){
  const sorted=[...pool].sort((a,b)=>(a.priority||99)-(b.priority||99));
  document.getElementById('model-pool-list').innerHTML=sorted.map((m,i)=>`<div class="model-row"><input class="model-pri" type="number" value="${m.priority||i+1}" min="1"><input class="model-id" value="${m.id}" placeholder="model-id"><input class="model-num" type="number" value="${m.rpd}" title="RPD"><input class="model-num" type="number" value="${m.rpm}" title="RPM"><button class="btn-danger" onclick="this.closest('.model-row').remove()">x</button></div>`).join('');
  document.getElementById('pri-err').style.display='none';
}
function getModelPool(){return Array.from(document.querySelectorAll('#model-pool-list .model-row')).map(row=>{const inp=row.querySelectorAll('input');return{priority:parseInt(inp[0].value)||1,id:inp[1].value.trim(),rpd:parseInt(inp[2].value)||20,rpm:parseInt(inp[3].value)||5};}).filter(m=>m.id);}
function addModelRow(){const pool=getModelPool();const maxP=pool.reduce((mx,m)=>Math.max(mx,m.priority),0);pool.push({priority:maxP+1,id:'gemini-new-model',rpd:20,rpm:5});renderModelPool(pool);}
function validatePriorities(){const pool=getModelPool();const pris=pool.map(m=>m.priority);const hasDup=new Set(pris).size!==pris.length;document.getElementById('pri-err').style.display=hasDup?'block':'none';document.getElementById('save-btn').disabled=hasDup;return!hasDup;}
async function saveSettings(){
  if(!validatePriorities()){toast('Fix duplicate priorities',false);return;}
  const body={NUM_CHUNKS:parseInt(document.getElementById('s-numchunks').value),GEMINI_MAX_OUTPUT_TOKENS:parseInt(document.getElementById('s-gmaxout').value),OOS_THRESHOLD:parseInt(document.getElementById('s-oos').value),RETRY_ATTEMPTS:parseInt(document.getElementById('s-retry').value),RETRY_COOLDOWN:parseInt(document.getElementById('s-cool').value),MAX_BLOB_LINES:parseInt(document.getElementById('s-maxblob').value),FILE_CONFLICT:document.getElementById('s-conflict').value,MODEL_POOL:getModelPool()};
  const res=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(res.ok)toast('Settings saved');else{const e=await res.json();toast(e.detail||'Save failed',false);}
}
document.addEventListener('input',e=>{if(e.target.classList.contains('model-pri'))validatePriorities();});
async function loadHistory(){
  document.getElementById('history-detail').style.display='none';
  const jobs=await fetch('/api/history').then(r=>r.json());const el=document.getElementById('history-list');
  if(!jobs.length){el.innerHTML='<div class="empty">No past jobs</div>';return;}
  el.innerHTML=jobs.map(j=>{
    const cls=j.status==='ok'?'hist-ok':j.status==='error'?'hist-err':'hist-cancel';
    return`<div class="hist-item" onclick="viewHistory('${j.id}')"><span class="hist-ts">${j.timestamp.replace('_',' ')}</span><span class="hist-status ${cls}">${j.status}</span><span style="color:var(--muted);font-size:12px">${j.completed} done, ${j.skipped} skipped</span></div>`;
  }).join('');
}
async function viewHistory(id){
  const data=await fetch('/api/history/'+id).then(r=>r.json());
  document.getElementById('history-list').style.display='none';
  const det=document.getElementById('history-detail');det.style.display='block';
  const box=document.getElementById('history-log');
  box.innerHTML=data.log.map(line=>{let cls='log-info';
    if(line.includes('===')||line.startsWith('PHASE')||line.startsWith('ANALYZE')||line.startsWith('TRANSLATE'))cls='log-sep';
    else if(line.includes('FAIL')||line.includes('ERROR')||line.includes('OOS')||line.startsWith('  skipped'))cls='log-err';
    else if(line.includes('SUCCESS')||line.includes('COMPLETE')||line.includes('Written')||line.startsWith('  done')||line.includes('Ready to translate'))cls='log-ok';
    else if(line.includes('WARN')||line.includes('cancel')||line.includes('Retry')||line.startsWith('DEDUP'))cls='log-warn';
    return`<span class="log-line ${cls}">${escHtml(line)}</span>`;}).join('');
}
// On back button, show list again
document.addEventListener('click',e=>{if(e.target.textContent==='Back to list'){document.getElementById('history-list').style.display='block';}});

navigate(currentPath);
fetch('/api/job-status').then(r=>r.json()).then(s=>{setJobRunning(s.running);if(s.running)startSSE();else checkAnalyzeStatus();});
</script></body></html>"""
