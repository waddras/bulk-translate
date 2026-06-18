#!/usr/bin/env python3
"""Server-rendered HTML/JS single-page UI for the bulk translator."""

HTML_UI = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bulk Subtitle Translator</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0f1117;--surface:#1a1d27;--border:#2a2d3d;
  --text:#e2e4f0;--muted:#6b7280;--accent:#6366f1;
  --green:#22c55e;--red:#ef4444;--yellow:#f59e0b;
  --font:'SF Mono','Fira Code',monospace
}
body{background:var(--bg);color:var(--text);font-family:var(--font);font-size:13px;min-height:100vh}
.layout{display:grid;grid-template-columns:1fr 320px;height:100vh;overflow:hidden}
.main{display:flex;flex-direction:column;overflow:hidden;border-right:1px solid var(--border)}
.sidebar{display:flex;flex-direction:column;overflow:hidden}
.header{padding:12px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;background:var(--surface)}
.header h1{font-size:14px;font-weight:600;letter-spacing:.04em}
.badge{font-size:10px;padding:2px 7px;border-radius:99px;background:var(--accent);color:#fff}
.tabs{display:flex;border-bottom:1px solid var(--border);background:var(--surface)}
.tab{padding:9px 16px;cursor:pointer;font-size:12px;color:var(--muted);border-bottom:2px solid transparent;transition:all .15s}
.tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.panel{flex:1;overflow-y:auto;padding:16px;display:none}
.panel.active{display:block}
.path-bar{display:flex;gap:8px;margin-bottom:12px}
.path-bar input{flex:1;background:var(--surface);border:1px solid var(--border);color:var(--text);padding:7px 10px;border-radius:6px;font-family:var(--font);font-size:12px}
.path-bar button{background:var(--accent);color:#fff;border:none;padding:7px 14px;border-radius:6px;cursor:pointer;font-size:12px}
.dir-list{display:flex;flex-direction:column;gap:3px;margin-bottom:10px}
.dir-item{display:flex;align-items:center;gap:8px;padding:7px 10px;background:var(--surface);border:1px solid var(--border);border-radius:5px;cursor:pointer;color:var(--muted);transition:border-color .15s}
.dir-item:hover{border-color:var(--accent);color:var(--text)}
</style>
</head>

<body>
<div class="layout">
<div class="main">
  <div class="header">
    <div class="dot dot-green" id="status-dot"></div>
    <h1>Bulk Subtitle Translator</h1>
    <span class="badge">v2.1</span>
  </div>
  <div class="tabs">
    <div class="tab active" onclick="showTab('browser')">Browser</div>
    <div class="tab" onclick="showTab('quota')">Quotas</div>
    <div class="tab" onclick="showTab('keys')">Keys</div>
    <div class="tab" onclick="showTab('settings')">Settings</div>
    <div class="tab" onclick="showTab('log')">Log</div>
  </div>
  <div id="tab-browser" class="panel active">
    <div class="path-bar">
      <input id="path-input" value="/mnt/secure/srv/hddmedia/anime" onkeydown="if(event.key==='Enter')navigate()">
      <button onclick="navigate()">Go</button>
    </div>
    <div id="dir-list" class="dir-list"></div>
    <div style="display:flex;align-items:center;justify-content:space-between">
      <div class="sec-label">SRT Files</div>
      <button class="sel-all" onclick="selectAll()">Select All</button>
    </div>
    <div id="file-list" class="file-list"></div>
  </div>
  <div id="tab-quota" class="panel">
    <div class="sec-label" style="margin-bottom:10px">Daily Quotas - <span id="quota-date"></span></div>
    <table class="quota-table">
      <thead><tr><th>Model</th><th>Used / Limit</th><th>Failures</th><th>Status</th><th>Actions</th></tr></thead>
      <tbody id="quota-tbody"></tbody>
    </table>
  </div>
  <div id="tab-keys" class="panel">
    <div class="sec-label" style="margin-bottom:8px">Add API Key</div>
    <div class="key-form">
      <input id="key-email" placeholder="Email / label (shown in logs)">
      <input id="key-value" type="password" placeholder="Gemini API Key">
      <button onclick="addKey()">Add Key</button>
    </div>
    <div class="sec-label" style="margin-bottom:8px">Saved Keys</div>
    <div id="keys-list"></div>
  </div>
  <div id="tab-settings" class="panel">
    <div class="sec-label" style="margin-bottom:10px">Translation Parameters</div>
    <div class="settings-grid">
      <div class="field"><label>CHUNK_SIZE (blocks, 0=off)</label><input id="s-chunk" type="number"></div>
      <div class="field"><label>CHARS_PER_TOKEN</label><input id="s-cpt" type="number"></div>
      <div class="field"><label>CHUNK_OUTPUT_TOKENS (0=off)</label><input id="s-chunktok" type="number"></div>
      <div class="field"><label>GEMINI_MAX_OUTPUT_TOKENS (0=model default)</label><input id="s-gmaxout" type="number"></div>
      <div class="field"><label>OOS_THRESHOLD</label><input id="s-oos" type="number"></div>
      <div class="field"><label>RETRY_ATTEMPTS</label><input id="s-retry" type="number"></div>
      <div class="field"><label>RETRY_COOLDOWN (seconds)</label><input id="s-cool" type="number"></div>
      <div class="field"><label>MAX_BLOB_LINES</label><input id="s-maxblob" type="number"></div>
    </div>
    <div class="sec-label" style="margin-bottom:8px">Model Pool (order = priority)</div>
    <div id="model-pool-list"></div>
    <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
      <button class="btn-muted" onclick="addModelRow()">+ Add Model</button>
      <button class="btn-save" onclick="saveSettings()">Save Settings</button>
    </div>
  </div>
  <div id="tab-log" class="panel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <div class="sec-label">Live Job Log</div>
      <button class="btn-sm" onclick="loadLog()">Refresh</button>
    </div>
    <div id="log-box" class="log-box">No job logs yet.</div>
  </div>
</div>
<div class="sidebar">
  <div class="sb-header"><h2>Queue</h2><div class="q-count"><span id="q-count">0</span> files selected</div></div>
  <div class="queue-list" id="queue-list"><div class="empty">No files queued yet</div></div>
  <div class="sb-footer">
    <button class="exec-btn" id="exec-btn" onclick="executeBatch()" disabled>Execute Batch</button>
    <button class="cancel-btn" id="cancel-btn" onclick="cancelJob()">Cancel Job</button>
  </div>
</div>
</div>
<div class="toast" id="toast"></div>

<script>
let selected=[], currentPath='/mnt/secure/srv/hddmedia/anime', pollTimer=null, jobRunning=false;

function toast(msg,ok=true){const el=document.getElementById('toast');el.textContent=msg;el.style.borderColor=ok?'var(--green)':'var(--red)';el.classList.add('show');setTimeout(()=>el.classList.remove('show'),3000);}
function escHtml(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

function showTab(name){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  ['browser','quota','keys','settings','log'].indexOf(name);
  document.querySelectorAll('.tab')[['browser','quota','keys','settings','log'].indexOf(name)].classList.add('active');
  if(name==='quota')loadQuota();if(name==='keys')loadKeys();if(name==='settings')loadSettings();if(name==='log')loadLog();
}

async function navigate(path){
  if(path!==undefined)currentPath=path;
  else currentPath=document.getElementById('path-input').value.trim();
  document.getElementById('path-input').value=currentPath;
  const res=await fetch('/api/browse?path='+encodeURIComponent(currentPath));
  if(!res.ok){toast('Cannot open: '+currentPath,false);return;}
  const data=await res.json();
  const dirEl=document.getElementById('dir-list');dirEl.innerHTML='';
  if(data.current!==data.parent){const up=document.createElement('div');up.className='dir-item';up.innerHTML='<span>.. (Go Up)</span>';up.onclick=()=>navigate(data.parent);dirEl.appendChild(up);}
  data.dirs.forEach(d=>{const el=document.createElement('div');el.className='dir-item';el.innerHTML=`<span>${d.name}</span>`;el.onclick=()=>navigate(d.path);dirEl.appendChild(el);});
  const fileEl=document.getElementById('file-list');fileEl.innerHTML='';
  if(!data.files.length){fileEl.innerHTML='<div class="empty">No .srt files here</div>';return;}
  data.files.forEach(f=>{const isSel=selected.includes(f.path);const el=document.createElement('label');el.className='file-item'+(isSel?' sel':'');
    el.innerHTML=`<input type="checkbox" ${isSel?'checked':''} onchange="toggleFile('${f.path.replace(/'/g,"\\'")}',this)"><span class="file-name">${f.name}</span><span class="file-size">${f.size_kb} KB</span>`;fileEl.appendChild(el);});
}

function toggleFile(path,cb){if(cb.checked){if(!selected.includes(path))selected.push(path);}else selected=selected.filter(p=>p!==path);cb.closest('.file-item').classList.toggle('sel',cb.checked);updateQueue();}

function selectAll(){
  document.querySelectorAll('#file-list .file-item').forEach(item=>{
    const cb=item.querySelector('input[type=checkbox]');const match=cb.getAttribute('onchange').match(/'([^']+)'/);
    if(!match)return;const path=match[1];cb.checked=true;if(!selected.includes(path))selected.push(path);item.classList.add('sel');});updateQueue();}

function updateQueue(){
  const el=document.getElementById('queue-list');
  document.getElementById('q-count').textContent=selected.length;
  document.getElementById('exec-btn').disabled=selected.length===0||jobRunning;
  if(!selected.length){el.innerHTML='<div class="empty">No files queued yet</div>';return;}
  el.innerHTML=selected.map(p=>{const name=p.split('/').pop();
    return `<div class="q-item"><span class="q-name" title="${p}">${name}</span><button class="rm" onclick="removeFile('${p.replace(/'/g,"\\'")}')">x</button></div>`;}).join('');
}

function removeFile(path){selected=selected.filter(p=>p!==path);updateQueue();navigate();}

async function executeBatch(){
  if(!selected.length)return;
  const res=await fetch('/api/translate-bulk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files:selected})});
  if(res.ok){selected=[];updateQueue();setJobRunning(true);showTab('log');pollStatus();}
  else{const err=await res.json();toast('Error: '+(err.detail||'Unknown'),false);}
}

async function cancelJob(){const res=await fetch('/api/job/cancel',{method:'POST'});if(res.ok)toast('Cancel signal sent');else toast('No job running',false);}

function setJobRunning(running){
  jobRunning=running;
  document.getElementById('cancel-btn').style.display=running?'block':'none';
  document.getElementById('status-dot').className='dot '+(running?'dot-yellow':'dot-green');
  document.getElementById('exec-btn').disabled=jobRunning||selected.length===0;
}

async function pollStatus(){
  const status=await fetch('/api/job-status').then(r=>r.json());
  setJobRunning(status.running);await loadLog();
  if(status.running)pollTimer=setTimeout(pollStatus,2000);
  else{if(status.error)toast('Job failed: '+status.error,false);
    else if(status.cancelled)toast('Cancelled - '+(status.completed_files||[]).length+' files written');
    else toast('Complete - '+(status.completed_files||[]).length+' files written');}
}

async function loadLog(){
  const status=await fetch('/api/job-status').then(r=>r.json());
  const box=document.getElementById('log-box');
  if(!status.log||!status.log.length){box.textContent='No logs yet.';return;}
  box.innerHTML=status.log.map(line=>{
    if(line.includes('===')||line.startsWith('PHASE'))return`<span class="log-sep">${escHtml(line)}</span>`;
    if(line.includes('FAIL')||line.includes('ERROR')||line.includes('OOS')||line.startsWith('  skipped'))return`<span class="log-err">${escHtml(line)}</span>`;
    if(line.includes('SUCCESS')||line.includes('COMPLETE')||line.includes('Written')||line.startsWith('  done'))return`<span class="log-ok">${escHtml(line)}</span>`;
    if(line.includes('WARN')||line.includes('cancel')||line.includes('Retry')||line.startsWith('DEDUP'))return`<span class="log-warn">${escHtml(line)}</span>`;
    return escHtml(line);}).join('\n');
  if(status.error)box.innerHTML+=`\n<span class="log-err">FATAL: ${escHtml(status.error)}</span>`;
  box.scrollTop=box.scrollHeight;
}

async function loadQuota(){
  const res=await fetch('/api/usage').then(r=>r.json());
  document.getElementById('quota-date').textContent=res.date;
  document.getElementById('quota-tbody').innerHTML=res.models.map(m=>{
    const pct=Math.min(100,Math.round(m.used_today/m.rpd_limit*100));
    const col=pct>80?'#ef4444':pct>50?'#f59e0b':'#22c55e';
    return`<tr><td style="font-size:11px">${m.model}</td><td>${m.used_today}/${m.rpd_limit}<div class="bar"><div class="bar-fill" style="width:${pct}%;background:${col}"></div></div></td><td>${m.failures}</td>
      <td>${m.out_of_service?'<span class="badge-oos">OOS</span>':'<span class="badge-ok">OK</span>'}</td>
      <td><button class="btn-sm" onclick="resetOOS('${m.model}')">Reset OOS</button><br><button class="btn-sm" onclick="resetAll('${m.model}')">Reset All</button></td></tr>`;}).join('');
}
async function resetOOS(m){await fetch('/api/usage/'+encodeURIComponent(m)+'/reset-oos',{method:'POST'});loadQuota();toast('OOS reset for '+m);}
async function resetAll(m){if(!confirm('Reset ALL usage for '+m+' today?'))return;await fetch('/api/usage/'+encodeURIComponent(m)+'/reset-usage',{method:'POST'});loadQuota();toast('Usage reset for '+m);}

async function loadKeys(){
  const keys=await fetch('/api/keys').then(r=>r.json());
  const el=document.getElementById('keys-list');
  if(!keys.length){el.innerHTML='<div class="empty">No keys saved yet</div>';return;}
  el.innerHTML=keys.map(k=>`<div class="key-row ${k.active?'':'key-inactive'}"><span class="key-email">${k.email}</span><span style="font-size:10px;color:var(--muted)">${k.added}</span>
    <button class="btn-sm" onclick="toggleKey(${k.id})">${k.active?'Disable':'Enable'}</button><button class="btn-sm btn-danger" onclick="deleteKey(${k.id})">Del</button></div>`).join('');
}
async function addKey(){
  const email=document.getElementById('key-email').value.trim(),key=document.getElementById('key-value').value.trim();
  if(!email||!key){toast('Enter email and API key',false);return;}
  const res=await fetch('/api/keys',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,api_key:key})});
  if(res.ok){document.getElementById('key-email').value='';document.getElementById('key-value').value='';loadKeys();toast('Key added');}
  else{const e=await res.json();toast(e.detail,false);}
}
async function toggleKey(id){await fetch('/api/keys/'+id+'/toggle',{method:'POST'});loadKeys();}
async function deleteKey(id){if(!confirm('Delete key?'))return;await fetch('/api/keys/'+id,{method:'DELETE'});loadKeys();toast('Key deleted');}

async function loadSettings(){
  const s=await fetch('/api/settings').then(r=>r.json());
  document.getElementById('s-chunk').value=s.CHUNK_SIZE;document.getElementById('s-cpt').value=s.CHARS_PER_TOKEN;
  document.getElementById('s-chunktok').value=s.CHUNK_OUTPUT_TOKENS;document.getElementById('s-gmaxout').value=s.GEMINI_MAX_OUTPUT_TOKENS;
  document.getElementById('s-oos').value=s.OOS_THRESHOLD;document.getElementById('s-retry').value=s.RETRY_ATTEMPTS;
  document.getElementById('s-cool').value=s.RETRY_COOLDOWN;document.getElementById('s-maxblob').value=s.MAX_BLOB_LINES;
  renderModelPool(s.MODEL_POOL);
}
function renderModelPool(pool){
  document.getElementById('model-pool-list').innerHTML=pool.map((m,i)=>`<div class="model-row" data-idx="${i}">
    <button class="move-btn" onclick="moveModel(${i},-1)">^</button><button class="move-btn" onclick="moveModel(${i},1)">v</button>
    <input class="model-id" value="${m.id}" placeholder="model-id">
    <input class="model-num" type="number" value="${m.rpd}" title="RPD"><input class="model-num" type="number" value="${m.rpm}" title="RPM">
    <button class="btn-danger" onclick="removeModelRow(${i})">x</button></div>`).join('');
}
function getModelPool(){return Array.from(document.querySelectorAll('#model-pool-list .model-row')).map(row=>{const inputs=row.querySelectorAll('input');return{id:inputs[0].value.trim(),rpd:parseInt(inputs[1].value)||20,rpm:parseInt(inputs[2].value)||5};}).filter(m=>m.id);}
function moveModel(idx,dir){const pool=getModelPool(),n=idx+dir;if(n<0||n>=pool.length)return;[pool[idx],pool[n]]=[pool[n],pool[idx]];renderModelPool(pool);}
function removeModelRow(idx){const pool=getModelPool();pool.splice(idx,1);renderModelPool(pool);}
function addModelRow(){const pool=getModelPool();pool.push({id:'gemini-new-model',rpd:20,rpm:5});renderModelPool(pool);}
async function saveSettings(){
  const body={CHUNK_SIZE:parseInt(document.getElementById('s-chunk').value),CHARS_PER_TOKEN:parseInt(document.getElementById('s-cpt').value),
    CHUNK_OUTPUT_TOKENS:parseInt(document.getElementById('s-chunktok').value),GEMINI_MAX_OUTPUT_TOKENS:parseInt(document.getElementById('s-gmaxout').value),
    OOS_THRESHOLD:parseInt(document.getElementById('s-oos').value),RETRY_ATTEMPTS:parseInt(document.getElementById('s-retry').value),
    RETRY_COOLDOWN:parseInt(document.getElementById('s-cool').value),MAX_BLOB_LINES:parseInt(document.getElementById('s-maxblob').value),MODEL_POOL:getModelPool()};
  const res=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(res.ok)toast('Settings saved');else toast('Save failed',false);
}

navigate(currentPath);
fetch('/api/job-status').then(r=>r.json()).then(s=>{setJobRunning(s.running);if(s.running)pollStatus();});
</script>
</body>
</html>"""
