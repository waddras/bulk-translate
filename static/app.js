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
  document.getElementById('translate-styles').style.display='none';
  document.getElementById('show-name-section').style.display='none';
  if(currentMode==='extract'){document.getElementById('analyze-btn').textContent='Probe Tracks';}
  document.getElementById('search-input').value='';
  navigate();
  toast('Cleared');
}
function goUp(){
  const parts=currentPath.replace(/\/$/,'').split('/');
  if(parts.length>1){parts.pop();navigate(parts.join('/')||'/');}
}
function filterFiles(){
  const q=document.getElementById('search-input').value.toLowerCase();
  document.querySelectorAll('#file-list .file-item').forEach(el=>{
    const name=el.querySelector('.file-name').textContent.toLowerCase();
    el.style.display=name.includes(q)?'':'none';
  });
}
function toggleAcc(header){header.parentElement.classList.toggle('open');}
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
  document.getElementById('delete-btn').style.display=mode==='extract'?'none':'inline-block';
  document.getElementById('fixrtl-btn').style.display=mode==='extract'?'none':'inline-block';
  document.getElementById('queue-panel').style.display=mode==='extract'?'none':'block';
  document.getElementById('extract-panel').style.display=mode==='extract'?'block':'none';
  document.getElementById('translate-styles').style.display='none';
  document.getElementById('show-name-section').style.display='none';
  document.getElementById('sb-title').textContent=mode==='extract'?'Extract Setup':'Queue';
  document.getElementById('track-list').innerHTML='<div class="empty" style="font-size:12px">Run Probe first</div>';
  document.getElementById('style-section').style.display='none';
  // Button labels
  if(mode==='extract'){
    document.getElementById('styles-btn').style.display='none';
    document.getElementById('analyze-btn').textContent='Probe Tracks';
    document.getElementById('translate-btn').textContent='Extract';
  } else {
    document.getElementById('styles-btn').style.display='none';
    document.getElementById('analyze-btn').textContent='Analyze';
    document.getElementById('translate-btn').textContent='Translate';
  }
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
  data.dirs.forEach(d=>{const el=document.createElement('div');el.className='dir-item';el.textContent=d.name;el.onclick=()=>navigate(d.path);dirEl.appendChild(el);});
  const fileEl=document.getElementById('file-list');fileEl.innerHTML='';
  if(!data.files.length){fileEl.innerHTML='<div class="empty">No files here</div>';return;}
  data.files.forEach(f=>{
    const isSel=selected.includes(f.path);const el=document.createElement('div');el.className='file-item'+(isSel?' sel':'');
    const renBtn=currentMode==='translate'?'<div class="file-actions"><button onclick="renameFile(this)" data-path="'+escHtml(f.path)+'" data-name="'+escHtml(f.name)+'">ren</button></div>':'';
    el.innerHTML='<input type="checkbox" '+(isSel?'checked':'')+' data-path="'+escHtml(f.path)+'"><span class="file-name">'+escHtml(f.name)+'</span><span class="file-size">'+f.size_kb+' KB</span>'+renBtn;
    const cb=el.querySelector('input');
    cb.onchange=()=>{if(cb.checked){if(!selected.includes(f.path))selected.push(f.path);}else{selected=selected.filter(p=>p!==f.path);}el.classList.toggle('sel',cb.checked);updateQueue();};
    fileEl.appendChild(el);
  });
}
function selectAll(){document.querySelectorAll('#file-list .file-item').forEach(el=>{if(el.style.display==='none')return;const cb=el.querySelector('input[type=checkbox]');if(cb&&!cb.checked){cb.checked=true;cb.onchange();}});}
function unselectAll(){document.querySelectorAll('#file-list .file-item').forEach(el=>{if(el.style.display==='none')return;const cb=el.querySelector('input[type=checkbox]');if(cb&&cb.checked){cb.checked=false;cb.onchange();}});}
async function deleteSelected(){
  const sel=Array.from(document.querySelectorAll('#file-list .file-item')).filter(el=>el.style.display!=='none').map(el=>el.querySelector('input[type=checkbox]')).filter(cb=>cb&&cb.checked).map(cb=>cb.dataset.path);
  if(!sel.length){toast('Nothing selected',false);return;}
  if(!confirm('Delete '+sel.length+' file(s)?'))return;
  const res=await fetch('/api/file/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paths:sel})});
  if(res.ok){const r=await res.json();toast('Deleted '+r.deleted+' files');selected=selected.filter(p=>!sel.includes(p));updateQueue();navigate();}
  else toast('Delete failed',false);
}
async function fixRtlSelected(){
  const sel=Array.from(document.querySelectorAll('#file-list .file-item')).filter(el=>el.style.display!=='none').map(el=>el.querySelector('input[type=checkbox]')).filter(cb=>cb&&cb.checked).map(cb=>cb.dataset.path);
  if(!sel.length){toast('Nothing selected',false);return;}
  const res=await fetch('/api/fix-rtl',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paths:sel})});
  if(res.ok){const r=await res.json();toast('Fixed RTL: '+r.fixed_lines+' lines in '+r.fixed_files+' files');}
  else{const e=await res.json();toast(e.detail||'Fix failed',false);}
}
async function renameFile(btn){
  const path=btn.dataset.path;const oldName=btn.dataset.name;
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
    if(!selected.length){el.innerHTML='<div class="empty">No files queued</div>';document.getElementById('translate-styles').style.display='none';document.getElementById('styles-btn').style.display='none';return;}
    el.innerHTML=selected.map(p=>{const name=p.split('/').pop();return'<div class="q-item"><span class="q-name" title="'+escHtml(p)+'">'+escHtml(name)+'</span><button class="rm" onclick="removeFile(this)" data-path="'+escHtml(p)+'">x</button></div>';}).join('');
    checkAnalyzeStatus();
    // Show Analyze Styles button if ASS files present
    const hasAss=selected.some(p=>p.toLowerCase().endsWith('.ass'));
    document.getElementById('styles-btn').style.display=hasAss?'block':'none';
    document.getElementById('styles-btn').disabled=jobRunning;
  }
}
function removeFile(btn){const path=btn.dataset.path;selected=selected.filter(p=>p!==path);updateQueue();navigate();}
async function checkAnalyzeStatus(){
  if(currentMode==='extract'){document.getElementById('translate-btn').disabled=selectedTrack===null||selected.length===0||jobRunning||translatePhase;return;}
  const res=await fetch('/api/analyze-status').then(r=>r.json());
  document.getElementById('translate-btn').disabled=!res.ready||jobRunning||translatePhase;
  if(res.ready&&res.show_name){
    document.getElementById('show-name-section').style.display='block';
    document.getElementById('show-name-input').value=res.show_name;
  }
}

async function detectTranslateStyles(){
  const assFiles=selected.filter(p=>p.toLowerCase().endsWith('.ass'));
  if(!assFiles.length){document.getElementById('translate-styles').style.display='none';return;}
  const res=await fetch('/api/detect-styles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files:assFiles})});
  const data=await res.json();
  const styles=data.styles||[];
  const el=document.getElementById('translate-style-list');
  if(!styles.length){document.getElementById('translate-styles').style.display='none';return;}
  document.getElementById('translate-styles').style.display='block';
  el.innerHTML=styles.map(s=>'<label class="style-cb-row"><input type="checkbox" checked class="translate-style-cb" value="'+escHtml(s)+'"> '+escHtml(s)+'</label>').join('');
}

async function runAnalyzeStyles(){
  setBtnLoading('styles-btn','Detecting...');
  await detectTranslateStyles();
  resetBtnLabels();
  document.getElementById('styles-btn').textContent='Analyze Styles';
  document.getElementById('styles-btn').disabled=false;
}

// === Analyze / Probe / Translate / Extract ===
function setBtnLoading(id,text){document.getElementById(id).disabled=true;document.getElementById(id).textContent=text;}
function resetBtnLabels(){
  if(currentMode==='extract'){
    document.getElementById('analyze-btn').textContent='Probe Tracks';
  } else {
    document.getElementById('analyze-btn').textContent='Analyze';
  }
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
    const keepStyles=Array.from(document.querySelectorAll('.translate-style-cb:checked')).map(cb=>cb.value);
    const res=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files:selected,keep_styles:keepStyles})});
    if(res.ok){setJobRunning(true);showTab('log');startSSE();}
    else{const err=await res.json();toast('Error: '+(err.detail||'Unknown'),false);resetBtnLabels();}
  }
}

async function runTranslate(){
  if(currentMode==='extract'){
    if(selectedTrack===null){toast('Select a track first',false);return;}
    const suffix=document.getElementById('ext-suffix').value.trim();
    if(!suffix){toast('Enter a suffix',false);return;}
    const convertToSrt=document.getElementById('convert-to-srt').checked;
    setBtnLoading('translate-btn','Extracting...');
    translatePhase=true;
    const res=await fetch('/api/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files:selected,track_index:selectedTrack,suffix:suffix,convert_to_srt:convertToSrt})});
    if(res.ok){setJobRunning(true);showTab('log');startSSE();}
    else{const err=await res.json();toast('Error: '+(err.detail||'Unknown'),false);translatePhase=false;resetBtnLabels();}
  } else {
    // Send show name override if user edited it
    const showName=document.getElementById('show-name-input').value.trim();
    if(showName)await fetch('/api/set-show-name',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:showName})});
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
        if(currentMode==='extract')loadExtractedStyles();
      }
    } else if(msg.type==='end'){
      if(evtSource){evtSource.close();evtSource=null;}
    }
  };
  evtSource.onerror=function(){if(evtSource){evtSource.close();evtSource=null;}setJobRunning(false);resetBtnLabels();checkAnalyzeStatus();};
}

// === Extract: load probe results (tracks + styles) ===
async function loadProbeResults(){
  const status=await fetch('/api/job-status').then(r=>r.json());
  const trackLines=(status.log||[]).filter(l=>l.includes('Track '));
  const trackEl=document.getElementById('track-list');
  if(!trackLines.length){trackEl.innerHTML='<div class="empty" style="font-size:12px">No tracks found</div>';return;}
  const tracks=[];
  trackLines.forEach(l=>{
    const m=l.match(/Track (\d+): \[([^\]]*)\] \(([^)]*)\)(.*)/);
    if(m)tracks.push({index:parseInt(m[1]),lang:m[2],codec:m[3],title:m[4].replace(/^\s*"?|"?\s*$/g,'')});
  });
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
  // Auto-select track 0 if it exists and is not image
  if(unique.length>0){
    const first=unique.find(t=>simplifyCodec(t.codec)!=='image');
    if(first){
      selectedTrack=first.index;
      const firstEl=trackEl.querySelector('.track-item:not(.disabled)');
      if(firstEl)firstEl.classList.add('sel');
      if(first.codec==='ass'||first.codec==='ssa'){
        document.getElementById('convert-srt-option').style.display='block';
      }
    }
  }
  // Enable Extract button
  document.getElementById('analyze-btn').textContent='Probe Tracks';
  document.getElementById('analyze-btn').disabled=false;
  checkAnalyzeStatus();
}

function selectTrack(idx,el,codec){
  selectedTrack=idx;
  document.querySelectorAll('.track-item').forEach(t=>t.classList.remove('sel'));
  el.classList.add('sel');
  // Show convert-to-SRT checkbox only for ASS tracks
  document.getElementById('convert-srt-option').style.display=(codec==='ass'||codec==='ssa')?'block':'none';
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

async function loadExtractedStyles(){
  // After extraction, detect styles from the extracted ASS files
  const status=await fetch('/api/job-status').then(r=>r.json());
  const completed=status.completed_files||[];
  // Get paths of extracted .ass files from the current directory
  const assFiles=completed.filter(f=>f.endsWith('.ass'));
  if(!assFiles.length){return;}
  // Build full paths from current browse path
  const fullPaths=assFiles.map(f=>currentPath+'/'+f);
  const res=await fetch('/api/detect-styles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({files:fullPaths})});
  const data=await res.json();
  const styles=data.styles||[];
  if(!styles.length)return;
  document.getElementById('post-extract-styles').style.display='block';
  document.getElementById('extract-style-list').innerHTML=styles.map(s=>'<label class="style-cb-row"><input type="checkbox" checked class="extract-style-cb" value="'+escHtml(s)+'"> '+escHtml(s)+'</label>').join('');
}

async function applyStyleFilter(){
  const keepStyles=Array.from(document.querySelectorAll('.extract-style-cb:checked')).map(cb=>cb.value);
  if(!keepStyles.length){toast('Select at least one style',false);return;}
  // Get extracted file paths
  const status=await fetch('/api/job-status').then(r=>r.json());
  const completed=(status.completed_files||[]).filter(f=>f.endsWith('.ass'));
  if(!completed.length){toast('No ASS files to filter',false);return;}
  const fullPaths=completed.map(f=>currentPath+'/'+f);
  toast('Filtering styles...');
  const res=await fetch('/api/filter-styles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paths:fullPaths,keep_styles:keepStyles})});
  if(res.ok){const r=await res.json();toast(r.filtered+' files updated: '+r.lines_removed+' lines removed, '+r.styles_removed+' styles removed');}
  else{const e=await res.json();toast(e.detail||'Filter failed',false);}
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
  document.getElementById('s-mode').value=s.TRANSLATION_MODE||'chunked';
  document.getElementById('s-maxlines').value=s.MAX_LINES_PER_CHUNK||1000;
  document.getElementById('s-gmaxout').value=s.GEMINI_MAX_OUTPUT_TOKENS;
  document.getElementById('s-oos').value=s.OOS_THRESHOLD;
  document.getElementById('s-retry').value=s.RETRY_ATTEMPTS;
  document.getElementById('s-cool').value=s.RETRY_COOLDOWN;
  document.getElementById('s-maxblob').value=s.MAX_BLOB_LINES;
  document.getElementById('s-maxfailed').value=s.MAX_FAILED_CHUNKS||5;
  document.getElementById('s-conflict').value=s.FILE_CONFLICT||'overwrite';
  document.getElementById('s-embed').value=String(s.EMBED_FONT!==false);
  document.getElementById('s-preserve').value=String(s.PRESERVE_ASS_POSITIONS===true);
  document.getElementById('s-tags').value=s.PRESERVE_TAGS||'pos, an, move, fad, fade;';
  document.getElementById('s-prompt').value=s.PROMPT_TEMPLATE||'';
  document.getElementById('s-fontname').value=s.FONT_NAME||'Amiri';
  document.getElementById('s-fontsize').value=s.FONT_SIZE||40;
  document.getElementById('s-outline').value=s.FONT_OUTLINE!=null?s.FONT_OUTLINE:1;
  document.getElementById('s-shadow').value=s.FONT_SHADOW!=null?s.FONT_SHADOW:0;
  document.getElementById('s-align').value=s.FONT_ALIGNMENT||2;
  document.getElementById('s-ml').value=s.FONT_MARGIN_L||20;
  document.getElementById('s-mr').value=s.FONT_MARGIN_R||20;
  document.getElementById('s-mv').value=s.FONT_MARGIN_V||30;
  // Load models from separate endpoint
  const models=await fetch('/api/models').then(r=>r.json());
  renderModelPool(models);
}
function renderModelPool(pool){
  const sorted=[...pool].sort((a,b)=>(a.priority||99)-(b.priority||99));
  const el=document.getElementById('model-pool-list');
  el.innerHTML='';
  sorted.forEach(m=>{
    const row=document.createElement('div');row.className='model-row';
    row.innerHTML='<input class="model-pri" type="number" value="'+(m.priority||1)+'" min="1"><input class="model-id" value="'+escHtml(m.id)+'" placeholder="model-id"><input class="model-num" type="number" value="'+(m.rpd||20)+'" title="RPD"><input class="model-num" type="number" value="'+(m.rpm||5)+'" title="RPM"><button class="btn-danger">x</button>';
    row.querySelector('.btn-danger').onclick=function(){row.remove();};
    el.appendChild(row);
  });
  document.getElementById('pri-err').style.display='none';
}
function getModelPool(){return Array.from(document.querySelectorAll('#model-pool-list .model-row')).map(row=>{const inp=row.querySelectorAll('input');return{priority:parseInt(inp[0].value)||1,id:inp[1].value.trim(),rpd:parseInt(inp[2].value)||20,rpm:parseInt(inp[3].value)||5};}).filter(m=>m.id);}
function addModelRow(){const pool=getModelPool();const maxP=pool.reduce((mx,m)=>Math.max(mx,m.priority),0);pool.push({priority:maxP+1,id:'gemini-new-model',rpd:20,rpm:5});renderModelPool(pool);}
function validatePriorities(){const pool=getModelPool();const pris=pool.map(m=>m.priority);const hasDup=new Set(pris).size!==pris.length;document.getElementById('pri-err').style.display=hasDup?'block':'none';document.getElementById('save-btn').disabled=hasDup;return!hasDup;}
async function saveSettings(){
  if(!validatePriorities()){toast('Fix duplicate priorities',false);return;}
  const res=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  // Save models separately
  const models=getModelPool();
  const mres=await fetch('/api/models',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({models})});
  if(res.ok&&mres.ok)toast('Settings saved');
  else{let msg='Save failed';try{const e=await(!res.ok?res:mres).json();msg=e.detail||JSON.stringify(e);}catch(x){}toast(msg,false);}
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
