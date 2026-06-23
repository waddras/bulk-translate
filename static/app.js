// === State ===
let selected=[], currentPath='/mnt/secure/srv/hddmedia/anime', jobRunning=false, translatePhase=false, currentMode='translate', evtSource=null, selectedTrack=null;

// === Utilities ===
function toast(msg,ok=true){const el=document.getElementById('toast');el.textContent=msg;el.style.borderColor=ok?'var(--green)':'var(--red)';el.classList.add('show');setTimeout(()=>el.classList.remove('show'),3500);}
function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function clearAll(){
  selected=[];selectedTrack=null;
  updateQueue();
  document.getElementById('track-list').innerHTML='<div class="empty" style="font-size:12px">Run Probe first</div>';
  document.getElementById('style-section').style.display='none';
  document.getElementById('style-list').innerHTML='';
  navigate();
  toast('Cleared');
}
function simplifyCodec(codec){
  if(codec==='subrip'||codec==='mov_text')return'srt';
  if(codec==='ass'||codec==='ssa')return'ass';
  if(codec==='webvtt')return'vtt';
  if(codec==='dvd_subtitle'||codec==='hdmv_pgs_subtitle'||codec==='dvb_subtitle')return'image';
  return codec;
}

// === Tabs ===
const TAB_NAMES=['files','quota','keys','settings','log','history'];
function showTab(name){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  document.querySelectorAll('.tab')[TAB_NAMES.indexOf(name)].classList.add('active');
  if(name==='quota')loadQuota();if(name==='keys')loadKeys();if(name==='settings')loadSettings();if(name==='log')loadLog();if(name==='history')loadHistory();
}

// === Mode switching ===
function switchMode(mode){
  currentMode=mode;selected=[];selectedTrack=null;updateQueue();
  document.getElementById('file-label').textContent=mode==='extract'?'Video Files (.mkv)':'Subtitle Files (.srt / .ass)';
  document.getElementById('analyze-btn').textContent=mode==='extract'?'Probe Tracks':'Analyze';
  document.getElementById('translate-btn').textContent=mode==='extract'?'Extract':'Translate';
  document.getElementById('delete-btn').style.display=mode==='extract'?'none':'inline-block';
  document.getElementById('queue-panel').style.display=mode==='extract'?'none':'block';
  document.getElementById('extract-panel').style.display=mode==='extract'?'block':'none';
  document.getElementById('sb-title').textContent=mode==='extract'?'Extract Setup':'Queue';
  document.getElementById('track-list').innerHTML='<div class="empty" style="font-size:12px">Run Probe first</div>';
  document.getElementById('style-section').style.display='none';
  navigate();
}

// === File browser ===
async function navigate(path){
  if(path!==undefined)currentPath=path;else currentPath=document.getElementById('path-input').value.trim();
  document.getElementById('path-input').value=currentPath;
  const res=await fetch('/api/browse?path='+encodeURIComponent(currentPath)+'&mode='+currentMode);
  if(!res.ok){toast('Cannot open path',false);return;}
  const data=await res.json();
  const dirEl=document.getElementById('dir-list');dirEl.innerHTML='';
  if(data.current!==data.parent){const up=document.createElement('div');up.className='dir-item';up.textContent='.. (Go Up)';up.onclick=()=>navigate(data.parent);dirEl.appendChild(up);}
  data.dirs.forEach(d=>{const el=document.createElement('div');el.className='dir-item';el.textContent=d.name;el.onclick=()=>navigate(d.path);dirEl.appendChild(el);});
  const fileEl=document.getElementById('file-list');fileEl.innerHTML='';
  if(!data.files.length){fileEl.innerHTML='<div class="empty">No files here</div>';return;}
  data.files.forEach(f=>{
    const isSel=selected.includes(f.path);const el=document.createElement('div');el.className='file-item'+(isSel?' sel':'');
    el.innerHTML=`<input type="checkbox" ${isSel?'checked':''} data-path="${escHtml(f.path)}"><span class="file-name">${escHtml(f.name)}</span><span class="file-size">${f.size_kb} KB</span>${currentMode==='translate'?'<div class="file-actions"><button onclick="renameFile(\''+escHtml(f.path)+'\',\''+escHtml(f.name)+'\')">ren</button></div>':''}`;
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
  if(!confirm('Delete '+sel.length+' file(s)?'))return;
  const res=await fetch('/api/file/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paths:sel})});
  if(res.ok){const r=await res.json();toast('Deleted '+r.deleted+' files');selected=selected.filter(p=>!sel.includes(p));updateQueue();navigate();}
  else toast('Delete failed',false);
}
async function renameFile(path,oldName){
  const newName=prompt('New filename:',oldName);if(!newName||newName===oldName)return;
  const res=await fetch('/api/file/rename',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path,new_name:newName})});
  if(res.ok){toast('Renamed');navigate();}else{const e=await res.json();toast(e.detail||'Rename failed',false);}
}

// === Queue ===
function updateQueue(){
  const el=document.getElementById('queue-panel');
  document.getElementById('q-count').textContent=selected.length;
  document.getElementById('analyze-btn').disabled=selected.length===0||jobRunning;
  if(!jobRunning)document.getElementById('translate-btn').disabled=true;
  if(currentMode==='translate'){
    if(!selected.length){el.innerHTML='<div class="empty">No files queued</div>';return;}
    el.innerHTML=selected.map(p=>{const name=p.split('/').pop();return'<div class="q-item"><span class="q-name" title="'+escHtml(p)+'">'+escHtml(name)+'</span><button class="rm" onclick="removeFile(this)" data-path="'+escHtml(p)+'">x</button></div>';}).join('');
    checkAnalyzeStatus();
  }
}
function removeFile(btn){const path=btn.dataset.path;selected=selected.filter(p=>p!==path);updateQueue();navigate();}
async function checkAnalyzeStatus(){
  if(currentMode==='extract'){document.getElementById('translate-btn').disabled=selectedTrack===null||selected.length===0||jobRunning||translatePhase;return;}
  const res=await fetch('/api/analyze-status').then(r=>r.json());
  document.getElementById('translate-btn').disabled=!res.ready||jobRunning||translatePhase;
}

// === Analyze / Probe / Translate / Extract ===
function setBtnLoading(id,text){document.getElementById(id).disabled=true;document.getElementById(id).textContent=text;}
function resetBtnLabels(){
  document.getElementById('analyze-btn').textContent=currentMode==='extract'?'Probe Tracks':'Analyze';
  document.getElementById('translate-btn').textContent=currentMode==='extract'?'Extract':'Translate';
  document.getElementById('analyze-btn').disabled=selected.length===0||jobRunning;
}

async function runAnalyze(){
  if(!selected.length)return;
  if(currentMode==='extract'){
    setBtnLoading('analyze-btn','Probing...');
    const res=await fetch('/api/probe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files:selected})});
    if(res.ok){setJobRunning(true);showTab('log');startSSE();}
    else{const err=await res.json();toast('Error: '+(err.detail||'Unknown'),false);resetBtnLabels();}
  } else {
    setBtnLoading('analyze-btn','Analyzing...');
    const res=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files:selected})});
    if(res.ok){setJobRunning(true);showTab('log');startSSE();}
    else{const err=await res.json();toast('Error: '+(err.detail||'Unknown'),false);resetBtnLabels();}
  }
}

async function runTranslate(){
  if(currentMode==='extract'){
    if(selectedTrack===null){toast('Select a track first',false);return;}
    const suffix=document.getElementById('ext-suffix').value.trim();
    if(!suffix){toast('Enter a suffix',false);return;}
    const keepStyles=Array.from(document.querySelectorAll('.style-cb:checked')).map(cb=>cb.value);
    setBtnLoading('translate-btn','Extracting...');
    translatePhase=true;
    const res=await fetch('/api/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files:selected,track_index:selectedTrack,suffix:suffix,keep_styles:keepStyles})});
    if(res.ok){setJobRunning(true);showTab('log');startSSE();}
    else{const err=await res.json();toast('Error: '+(err.detail||'Unknown'),false);translatePhase=false;resetBtnLabels();}
  } else {
    setBtnLoading('translate-btn','Translating...');
    translatePhase=true;
    const res=await fetch('/api/translate',{method:'POST'});
    if(res.ok){setJobRunning(true);showTab('log');startSSE();}
    else{const err=await res.json();toast('Error: '+(err.detail||'Unknown'),false);translatePhase=false;resetBtnLabels();}
  }
}

// === Cancel ===
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

// === Job state ===
function setJobRunning(running){
  jobRunning=running;
  document.getElementById('cancel-btn').style.display=running?'block':'none';
  document.getElementById('status-dot').className='dot '+(running?'dot-yellow':'dot-green');
  document.getElementById('analyze-btn').disabled=jobRunning||selected.length===0;
  if(running){document.getElementById('translate-btn').disabled=true;}
}

// === SSE ===
function startSSE(){
  if(evtSource)evtSource.close();
  const box=document.getElementById('log-box');box.innerHTML='';
  evtSource=new EventSource('/api/job-stream');
  evtSource.onmessage=function(e){
    const msg=JSON.parse(e.data);
    if(msg.type==='log'){
      let cls='log-info';const line=msg.line;
      if(line.includes('===')||line.startsWith('PHASE')||line.startsWith('ANALYZE')||line.startsWith('TRANSLATE')||line.startsWith('PROBE')||line.startsWith('EXTRACT'))cls='log-sep';
      else if(line.includes('FAIL')||line.includes('ERROR')||line.includes('OOS')||line.startsWith('  failed'))cls='log-err';
      else if(line.includes('SUCCESS')||line.includes('COMPLETE')||line.includes('Written')||line.startsWith('  done')||line.includes('Ready to translate'))cls='log-ok';
      else if(line.includes('WARN')||line.includes('cancel')||line.includes('Retry')||line.startsWith('DEDUP')||line.includes('missing'))cls='log-warn';
      box.innerHTML+='<span class="log-line '+cls+'">'+escHtml(line)+'</span>';
      box.scrollTop=box.scrollHeight;
    } else if(msg.type==='status'){
      setJobRunning(msg.running);
      if(!msg.running&&msg.done){
        evtSource.close();evtSource=null;translatePhase=false;
        document.getElementById('cancel-modal').style.display='none';
        document.getElementById('cancel-btn').disabled=false;
        resetBtnLabels();
        if(msg.error)toast('Job failed: '+msg.error,false);
        else if(msg.cancelled)toast('Job cancelled successfully');
        else toast('Done');
        checkAnalyzeStatus();
        if(currentMode==='extract')loadProbeResults();
      }
    } else if(msg.type==='end'){
      if(evtSource){evtSource.close();evtSource=null;}
    }
  };
  evtSource.onerror=function(){if(evtSource){evtSource.close();evtSource=null;}setJobRunning(false);resetBtnLabels();checkAnalyzeStatus();};
}

// === Extract: load probe results (tracks + styles) ===
async function loadProbeResults(){
  // Load tracks from job log (parsed from log lines)
  const status=await fetch('/api/job-status').then(r=>r.json());
  const trackLines=(status.log||[]).filter(l=>l.includes('Track '));
  const trackEl=document.getElementById('track-list');
  if(!trackLines.length){trackEl.innerHTML='<div class="empty" style="font-size:12px">No tracks found</div>';return;}
  // Parse track info from log
  const tracks=[];
  trackLines.forEach(l=>{
    const m=l.match(/Track (\d+): \[([^\]]*)\] \(([^)]*)\)(.*)/);
    if(m)tracks.push({index:parseInt(m[1]),lang:m[2],codec:m[3],title:m[4].replace(/^\s*"?|"?\s*$/g,'')});
  });
  // Deduplicate by index
  const unique=[];const seen=new Set();
  tracks.forEach(t=>{const k=t.index+'-'+t.lang+'-'+t.codec+'-'+t.title;if(!seen.has(k)){seen.add(k);unique.push(t);}});
  trackEl.innerHTML=unique.map(t=>{
    const sc=simplifyCodec(t.codec);
    const isImage=sc==='image';
    const cls='track-item'+(selectedTrack===t.index&&!isImage?' sel':'')+(isImage?' disabled':'');
    const onclick=isImage?'':'onclick="selectTrack('+t.index+',this,\''+t.codec+'\')"';
    const label=isImage?'<span style="color:var(--red)">image - cannot extract</span>':'<span>('+sc+')</span>';
    return'<div class="'+cls+'" '+onclick+'><strong>'+t.index+'</strong> <span style="color:var(--muted)">['+escHtml(t.lang)+']</span> '+label+' '+escHtml(t.title)+'</div>';
  }).join('');
}

function selectTrack(idx,el,codec){
  selectedTrack=idx;
  document.querySelectorAll('.track-item').forEach(t=>t.classList.remove('sel'));
  el.classList.add('sel');
  if(codec==='ass'||codec==='ssa'){
    document.getElementById('style-section').style.display='block';
    loadProbeStyles();
  } else {
    document.getElementById('style-section').style.display='none';
    document.getElementById('style-list').innerHTML='<div class="empty" style="font-size:12px">SRT tracks have no styles</div>';
  }
  checkAnalyzeStatus();
}

async function loadProbeStyles(){
  if(selectedTrack===null)return;
  const res=await fetch('/api/probe-styles?track='+selectedTrack).then(r=>r.json());
  const el=document.getElementById('style-list');
  const styles=res.styles||[];
  if(!styles.length){el.innerHTML='<div class="empty" style="font-size:12px">No styles detected</div>';return;}
  el.innerHTML=styles.map(s=>'<label class="style-cb-row"><input type="checkbox" checked class="style-cb" value="'+escHtml(s)+'"> '+escHtml(s)+'</label>').join('');
}

// === Log ===
async function loadLog(){
  const status=await fetch('/api/job-status').then(r=>r.json());
  const box=document.getElementById('log-box');
  if(!status.log||!status.log.length){box.textContent='No logs yet.';return;}
  box.innerHTML=status.log.map(line=>{
    let cls='log-info';
    if(line.includes('===')||line.startsWith('PHASE')||line.startsWith('ANALYZE')||line.startsWith('TRANSLATE')||line.startsWith('PROBE')||line.startsWith('EXTRACT'))cls='log-sep';
    else if(line.includes('FAIL')||line.includes('ERROR')||line.includes('OOS')||line.startsWith('  failed'))cls='log-err';
    else if(line.includes('SUCCESS')||line.includes('COMPLETE')||line.includes('Written')||line.startsWith('  done')||line.includes('Ready to translate'))cls='log-ok';
    else if(line.includes('WARN')||line.includes('cancel')||line.includes('Retry')||line.startsWith('DEDUP')||line.includes('missing'))cls='log-warn';
    return'<span class="log-line '+cls+'">'+escHtml(line)+'</span>';
  }).join('');
  box.scrollTop=box.scrollHeight;
}

// === Quota ===
async function loadQuota(){
  const res=await fetch('/api/usage').then(r=>r.json());
  document.getElementById('quota-date').textContent=res.date;
  document.getElementById('reset-info').textContent='Next reset: '+(res.next_reset||'10:30 AM AST');
  document.getElementById('quota-tbody').innerHTML=res.models.map(m=>{
    const pct=Math.min(100,Math.round(m.used_today/m.rpd_limit*100));const col=pct>80?'#ef4444':pct>50?'#f59e0b':'#22c55e';
    return'<tr><td style="font-family:var(--mono);text-align:center">'+(m.priority||'-')+'</td><td style="font-size:12px;font-family:var(--mono)">'+m.model+'</td><td>'+m.used_today+'/'+m.rpd_limit+'<div class="bar"><div class="bar-fill" style="width:'+pct+'%;background:'+col+'"></div></div></td><td>'+m.failures+'</td><td>'+(m.out_of_service?'<span class="badge-oos">OOS</span>':'<span class="badge-ok">OK</span>')+'</td><td><button class="btn-sm" onclick="resetOOS(\''+m.model+'\')">Reset OOS</button> <button class="btn-sm" onclick="resetAll(\''+m.model+'\')">Reset All</button></td></tr>';
  }).join('');
}
async function resetOOS(m){await fetch('/api/usage/'+encodeURIComponent(m)+'/reset-oos',{method:'POST'});loadQuota();toast('OOS reset');}
async function resetAll(m){if(!confirm('Reset ALL for '+m+'?'))return;await fetch('/api/usage/'+encodeURIComponent(m)+'/reset-usage',{method:'POST'});loadQuota();toast('Reset');}

// === Keys ===
async function loadKeys(){
  const keys=await fetch('/api/keys').then(r=>r.json());const el=document.getElementById('keys-list');
  if(!keys.length){el.innerHTML='<div class="empty">No keys saved</div>';return;}
  el.innerHTML=keys.map(k=>'<div class="key-row '+(k.active?'':'key-inactive')+'"><span class="key-email">'+escHtml(k.email)+'</span><span style="font-size:11px;color:var(--muted)">'+k.added+'</span><button class="btn-sm" onclick="toggleKey('+k.id+')">'+(k.active?'Disable':'Enable')+'</button><button class="btn-sm btn-danger" onclick="deleteKey('+k.id+')">Del</button></div>').join('');
}
async function addKey(){const email=document.getElementById('key-email').value.trim(),key=document.getElementById('key-value').value.trim();if(!email||!key){toast('Enter email and key',false);return;}const res=await fetch('/api/keys',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,api_key:key})});if(res.ok){document.getElementById('key-email').value='';document.getElementById('key-value').value='';loadKeys();toast('Key added');}else{const e=await res.json();toast(e.detail,false);}}
async function toggleKey(id){await fetch('/api/keys/'+id+'/toggle',{method:'POST'});loadKeys();}
async function deleteKey(id){if(!confirm('Delete key?'))return;await fetch('/api/keys/'+id,{method:'DELETE'});loadKeys();toast('Deleted');}

// === Settings ===
async function loadSettings(){
  const s=await fetch('/api/settings').then(r=>r.json());
  document.getElementById('s-numchunks').value=s.NUM_CHUNKS;
  document.getElementById('s-gmaxout').value=s.GEMINI_MAX_OUTPUT_TOKENS;
  document.getElementById('s-oos').value=s.OOS_THRESHOLD;
  document.getElementById('s-retry').value=s.RETRY_ATTEMPTS;
  document.getElementById('s-cool').value=s.RETRY_COOLDOWN;
  document.getElementById('s-maxblob').value=s.MAX_BLOB_LINES;
  document.getElementById('s-format').value=s.OUTPUT_FORMAT||'ass';
  document.getElementById('s-convert').value=String(s.CONVERT_TO_SRT_AFTER_EXTRACT===true);
  document.getElementById('s-conflict').value=s.FILE_CONFLICT||'overwrite';
  document.getElementById('s-embed').value=String(s.EMBED_FONT!==false);
  document.getElementById('s-preserve').value=String(s.PRESERVE_ASS_POSITIONS===true);
  document.getElementById('s-fontname').value=s.FONT_NAME||'Amiri';
  document.getElementById('s-fontsize').value=s.FONT_SIZE||40;
  document.getElementById('s-outline').value=s.FONT_OUTLINE!=null?s.FONT_OUTLINE:1;
  document.getElementById('s-shadow').value=s.FONT_SHADOW!=null?s.FONT_SHADOW:0;
  document.getElementById('s-align').value=s.FONT_ALIGNMENT||2;
  document.getElementById('s-ml').value=s.FONT_MARGIN_L||20;
  document.getElementById('s-mr').value=s.FONT_MARGIN_R||20;
  document.getElementById('s-mv').value=s.FONT_MARGIN_V||30;
  renderModelPool(s.MODEL_POOL);
}
function renderModelPool(pool){
  const sorted=[...pool].sort((a,b)=>(a.priority||99)-(b.priority||99));
  document.getElementById('model-pool-list').innerHTML=sorted.map(m=>'<div class="model-row"><input class="model-pri" type="number" value="'+(m.priority||1)+'" min="1"><input class="model-id" value="'+m.id+'" placeholder="model-id"><input class="model-num" type="number" value="'+m.rpd+'" title="RPD"><input class="model-num" type="number" value="'+m.rpm+'" title="RPM"><button class="btn-danger" onclick="this.closest(\'.model-row\').remove()">x</button></div>').join('');
  document.getElementById('pri-err').style.display='none';
}
function getModelPool(){return Array.from(document.querySelectorAll('#model-pool-list .model-row')).map(row=>{const inp=row.querySelectorAll('input');return{priority:parseInt(inp[0].value)||1,id:inp[1].value.trim(),rpd:parseInt(inp[2].value)||20,rpm:parseInt(inp[3].value)||5};}).filter(m=>m.id);}
function addModelRow(){const pool=getModelPool();const maxP=pool.reduce((mx,m)=>Math.max(mx,m.priority),0);pool.push({priority:maxP+1,id:'gemini-new-model',rpd:20,rpm:5});renderModelPool(pool);}
function validatePriorities(){const pool=getModelPool();const pris=pool.map(m=>m.priority);const hasDup=new Set(pris).size!==pris.length;document.getElementById('pri-err').style.display=hasDup?'block':'none';document.getElementById('save-btn').disabled=hasDup;return!hasDup;}
async function saveSettings(){
  if(!validatePriorities()){toast('Fix duplicate priorities',false);return;}
  const body={NUM_CHUNKS:parseInt(document.getElementById('s-numchunks').value),GEMINI_MAX_OUTPUT_TOKENS:parseInt(document.getElementById('s-gmaxout').value),OOS_THRESHOLD:parseInt(document.getElementById('s-oos').value),RETRY_ATTEMPTS:parseInt(document.getElementById('s-retry').value),RETRY_COOLDOWN:parseInt(document.getElementById('s-cool').value),MAX_BLOB_LINES:parseInt(document.getElementById('s-maxblob').value),OUTPUT_FORMAT:document.getElementById('s-format').value,CONVERT_TO_SRT_AFTER_EXTRACT:document.getElementById('s-convert').value==='true',FILE_CONFLICT:document.getElementById('s-conflict').value,EMBED_FONT:document.getElementById('s-embed').value==='true',PRESERVE_ASS_POSITIONS:document.getElementById('s-preserve').value==='true',FONT_NAME:document.getElementById('s-fontname').value,FONT_SIZE:parseInt(document.getElementById('s-fontsize').value),FONT_OUTLINE:parseInt(document.getElementById('s-outline').value),FONT_SHADOW:parseInt(document.getElementById('s-shadow').value),FONT_ALIGNMENT:parseInt(document.getElementById('s-align').value),FONT_MARGIN_L:parseInt(document.getElementById('s-ml').value),FONT_MARGIN_R:parseInt(document.getElementById('s-mr').value),FONT_MARGIN_V:parseInt(document.getElementById('s-mv').value),MODEL_POOL:getModelPool()};
  const res=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(res.ok)toast('Settings saved');else{const e=await res.json();toast(e.detail||'Save failed',false);}
}
document.addEventListener('input',e=>{if(e.target.classList.contains('model-pri'))validatePriorities();});

// === History ===
async function loadHistory(){
  document.getElementById('history-detail').style.display='none';
  document.getElementById('history-list').style.display='block';
  const jobs=await fetch('/api/history').then(r=>r.json());const el=document.getElementById('history-list');
  if(!jobs.length){el.innerHTML='<div class="empty">No past jobs</div>';return;}
  el.innerHTML=jobs.map(j=>{const cls=j.status==='ok'?'hist-ok':j.status==='error'?'hist-err':'hist-cancel';return'<div class="hist-item" onclick="viewHistory(\''+j.id+'\')"><span class="hist-ts">'+j.timestamp.replace('_',' ')+'</span><span class="hist-status '+cls+'">'+j.status+'</span><span style="color:var(--muted);font-size:12px">'+j.completed+' done, '+j.skipped+' skipped</span></div>';}).join('');
}
async function viewHistory(id){
  const data=await fetch('/api/history/'+id).then(r=>r.json());
  document.getElementById('history-list').style.display='none';
  document.getElementById('history-detail').style.display='block';
  const box=document.getElementById('history-log');
  box.innerHTML=data.log.map(line=>{let cls='log-info';if(line.includes('===')||line.startsWith('PHASE'))cls='log-sep';else if(line.includes('FAIL')||line.includes('ERROR'))cls='log-err';else if(line.includes('SUCCESS')||line.includes('COMPLETE')||line.startsWith('  done'))cls='log-ok';else if(line.includes('WARN')||line.startsWith('DEDUP'))cls='log-warn';return'<span class="log-line '+cls+'">'+escHtml(line)+'</span>';}).join('');
}
function hideHistoryDetail(){document.getElementById('history-detail').style.display='none';document.getElementById('history-list').style.display='block';}

// === Init ===
navigate(currentPath);
fetch('/api/job-status').then(r=>r.json()).then(s=>{setJobRunning(s.running);if(s.running)startSSE();else checkAnalyzeStatus();});
