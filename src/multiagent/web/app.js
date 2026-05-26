/* ============================================================
   MultiAgent Structural Modeling UI — Application Logic
   ============================================================ */

// ----- State -----
const state = {
  prompt: "",
  outputs: {},
  currentView: "node_output",
  pollTimer: null,
  selectedIssue: null,
};

// ----- Utilities -----
function $(id) { return document.getElementById(id); }
function escapeHtml(v) { return String(v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;"); }
function shortPrompt(p) { const c = String(p||"").replace(/\s+/g," ").trim(); return c.length>180?c.slice(0,180)+"...":c; }
function formatValue(v, asCode) { return typeof v==="string"?(asCode?v:v||"(empty)"):JSON.stringify(v??{},null,2); }

async function request(url, opts={}) {
  const r = await fetch(url,{headers:{"Content-Type":"application/json"},...opts});
  if(!r.ok) throw new Error(`Request failed: ${r.status}`);
  return r.json();
}

// ----- Toast Notifications -----
function toast(msg, type="info", duration=4000) {
  const c = $("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  const icons = {success:"✓",error:"✗",info:"ℹ"};
  el.innerHTML = `<span>${icons[type]||"ℹ"}</span><span class="toast-msg">${escapeHtml(msg)}</span>`;
  c.appendChild(el);
  setTimeout(()=>{el.style.opacity="0";el.style.transition="opacity 0.2s";setTimeout(()=>el.remove(),200);},duration);
}

// ----- Theme Toggle -----
function initTheme() {
  const saved = localStorage.getItem("theme")||"dark";
  document.documentElement.setAttribute("data-theme",saved);
  updateThemeUI(saved);
  $("theme-toggle").addEventListener("click",()=>{
    const cur = document.documentElement.getAttribute("data-theme");
    const next = cur==="dark"?"light":"dark";
    document.documentElement.setAttribute("data-theme",next);
    localStorage.setItem("theme",next);
    updateThemeUI(next);
  });
}
function updateThemeUI(theme) {
  $("theme-icon").textContent = theme==="dark"?"☀️":"🌙";
  $("theme-label").textContent = theme==="dark"?"Light Mode":"Dark Mode";
}

// ----- Section Navigation -----
function initNav() {
  const navItems = document.querySelectorAll(".nav-item");
  const sections = document.querySelectorAll(".section");

  function switchSection(name) {
    sections.forEach(s=>s.classList.remove("active"));
    navItems.forEach(n=>n.classList.remove("active"));
    const sec = document.getElementById(`section-${name}`);
    if(sec) sec.classList.add("active");
    const nav = document.querySelector(`.nav-item[data-section="${name}"]`);
    if(nav) nav.classList.add("active");
    // Close mobile sidebar
    $("sidebar").classList.remove("open");
  }

  navItems.forEach(item=>{
    item.addEventListener("click",()=>switchSection(item.dataset.section));
  });

  // Also support data-nav buttons in dashboard
  document.querySelectorAll("[data-nav]").forEach(btn=>{
    btn.addEventListener("click",()=>switchSection(btn.dataset.nav));
  });

  // LLM config toggle
  $("llm-config-header").addEventListener("click", () => {
    const body = $("llm-config-body");
    const toggle = $("llm-config-toggle");
    if (body.style.display === "none") {
      body.style.display = "";
      toggle.textContent = "▲";
    } else {
      body.style.display = "none";
      toggle.textContent = "▼";
    }
  });
  $("llm-config-save").addEventListener("click", (e) => { e.stopPropagation(); saveAgentLLMConfig(); });
  $("llm-config-clear").addEventListener("click", (e) => { e.stopPropagation(); clearLLMConfig(); });
  $("llm-apply-all").addEventListener("click", (e) => { e.stopPropagation(); applyAllLLMConfig(); });
}

// Mobile menu
function initMobile() {
  $("mobile-menu-btn").addEventListener("click",()=>{
    $("sidebar").classList.toggle("open");
  });
  $("sidebar-overlay").addEventListener("click",()=>{
    $("sidebar").classList.remove("open");
  });
}

// ----- Syntax Highlighting -----
function highlightJson(text) {
  return escapeHtml(text).replace(
    /(&quot;(?:\\.|[^"\\])*&quot;)(\s*:)?|\b(true|false|null)\b|-?\b\d+(?:\.\d+)?(?:e[+-]?\d+)?\b/gi,
    (m,sv,colon,lit)=>{
      if(sv){const cls=colon?"token-key":"token-string";return`<span class="${cls}">${sv}</span>${colon||""}`;}
      if(lit) return`<span class="token-literal">${m}</span>`;
      return`<span class="token-number">${m}</span>`;
    });
}
function highlightPython(text) {
  const esc = escapeHtml(text);
  return esc.replace(
    /(#.*$)|(&quot;.*?&quot;|'.*?')|\b(def|class|return|import|from|for|in|if|else|elif|while|try|except|with|as|None|True|False)\b|\b([A-Za-z_][A-Za-z0-9_]*)(?=\s*\()/gm,
    (m,comment,str,kw,callable)=>{
      if(comment) return`<span class="token-comment">${comment}</span>`;
      if(str) return`<span class="token-string">${str}</span>`;
      if(kw) return`<span class="token-keyword">${kw}</span>`;
      if(callable) return`<span class="token-function">${callable}</span>`;
      return m;
    });
}

// ----- Render Functions -----

function renderViewer() {
  const v = $("viewer");
  const key = state.currentView;
  const isCode = key==="geometry_code"||key==="complete_code"||key==="pipeline_log";
  const formatted = formatValue(state.outputs[key],isCode);
  if(isCode) v.innerHTML=highlightPython(formatted);
  else v.innerHTML=highlightJson(formatted);
}

function renderStages(stages) {
  const rail = $("stage-rail");
  rail.innerHTML = "";
  const totalAgents = stages.reduce((s,st)=>s+(st.agents||[]).length,0);
  const readyAgents = stages.reduce((s,st)=>s+(st.agents||[]).filter(a=>a.status==="ready").length,0);
  const pct = totalAgents?Math.round(readyAgents/totalAgents*100):0;
  $("pipeline-progress-text").textContent = `${readyAgents}/${totalAgents} agents ready`;
  const bar = $("pipeline-progress-bar");
  bar.style.width = pct+"%";
  bar.className = "progress-fill" + (pct===100?" success":"");

  stages.forEach((stage,i)=>{
    const agentsMarkup = (stage.agents||[]).map(a=>
      `<span class="agent-tag ${a.status}">${a.name}</span>`
    ).join("");
    const step = document.createElement("div");
    step.className = "stage-step";
    const dotCls = stage.status==="ready"?"done":(stage.status==="failed"?"failed":"");
    const lineCls = stage.status==="ready"?"done":"";
    step.innerHTML = `
      <div class="stage-marker">
        <div class="stage-dot ${dotCls}">${i+1}</div>
        <div class="stage-line ${lineCls}"></div>
      </div>
      <div class="stage-card">
        <h4>${stage.title}</h4>
        <div class="agent-tags">${agentsMarkup}</div>
        <div style="margin-top:8px">
          <div class="progress-bar"><div class="progress-fill ${stage.status==="ready"?"success":""}" style="width:${stage.agents.filter(a=>a.status==="ready").length/Math.max(stage.agents.length,1)*100}%"></div></div>
        </div>
      </div>
    `;
    rail.appendChild(step);
  });
}

// ----- Visualization -----
function extractNodes(nodeOutput, elementOutput) {
  const map = new Map();
  const add = (items)=>{
    if(!Array.isArray(items)) return;
    items.forEach(item=>{
      const id=Number(item.id??item.node_id);
      const x=Number(item.x??item.x_m??item.coordinates?.[0]);
      const y=Number(item.y??item.y_m??item.coordinates?.[1]);
      if(Number.isFinite(id)&&Number.isFinite(x)&&Number.isFinite(y)) map.set(id,{id,x,y,raw:item});
    });
  };
  add(nodeOutput.nodes);
  if(Array.isArray(nodeOutput.construction_sequence)) nodeOutput.construction_sequence.forEach(s=>add(s.nodes_added));
  if(Array.isArray(elementOutput?.nodes)) add(elementOutput.nodes);
  return Array.from(map.values()).sort((a,b)=>a.id-b.id);
}

function normalizeElement(item) {
  let n1=Number(item.node1??item.i_node??item.iNode), n2=Number(item.node2??item.j_node??item.jNode);
  if(!Number.isFinite(n1)||!Number.isFinite(n2)){const p=item.nodes;if(Array.isArray(p)&&p.length===2){n1=Number(p[0]);n2=Number(p[1]);}}
  if(!Number.isFinite(n1)||!Number.isFinite(n2)){const ri=String(item.node_i||"").replace("N",""),rj=String(item.node_j||"").replace("N","");if(/^\d+$/.test(ri)&&/^\d+$/.test(rj)){n1=Number(ri);n2=Number(rj);}}
  return {id:Number(item.element_id??item.id),node1:n1,node2:n2,type:item.type||item.element_type||"",raw:item};
}

function extractElements(elementOutput) {
  const els=[];
  if(Array.isArray(elementOutput.elements)) elementOutput.elements.forEach(e=>els.push(normalizeElement(e)));
  if(Array.isArray(elementOutput.element_definitions)) elementOutput.element_definitions.forEach(e=>els.push(normalizeElement(e)));
  if(Array.isArray(elementOutput.steps)) elementOutput.steps.forEach(s=>{(s.elements_added||[]).forEach(e=>els.push(normalizeElement(e)));});
  return els.filter(e=>Number.isFinite(e.id));
}

function projectPoint(node,bounds,w,h,pad){
  const sx=Math.max(bounds.maxX-bounds.minX,1),sy=Math.max(bounds.maxY-bounds.minY,1);
  const uw=w-pad*2,uh=h-pad*2;
  const scale=Math.min(uw/sx,uh/sy);
  const ox=(w-sx*scale)/2,oy=(h-sy*scale)/2;
  return {x:ox+(node.x-bounds.minX)*scale,y:h-(oy+(node.y-bounds.minY)*scale)};
}

function createSvgEl(name,attrs={}){
  const el=document.createElementNS("http://www.w3.org/2000/svg",name);
  Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,String(v)));
  return el;
}

function selectIssue(kind,payload){
  state.selectedIssue={kind,payload};
  renderSelectionPrompt();
  renderVisualization(state.outputs||{});
}

function buildSelectionPrompt(){
  if(!state.selectedIssue) return "";
  const origPrompt=state.prompt||$("prompt-input").value.trim();
  if(state.selectedIssue.kind==="node"){
    const n=state.selectedIssue.payload;
    return ["You are rerunning the Node Agent for a structural frame model.","","Original user request:",origPrompt,"",`A reviewer clicked node ${n.id} in the visualization and marked it as incorrect.`,"Selected node record:",JSON.stringify(n.raw??n,null,2),"","Please re-check this node against the frame geometry, story progression, bay spacing, support conditions, and neighboring elements.","If the node is wrong, regenerate a corrected node-output JSON for the full node set while preserving valid nodes when possible.","Return structured JSON only and keep the current node-output schema consistent."].join("\n");
  }
  const el=state.selectedIssue.payload;
  const relatedNodes=extractNodes(state.outputs.node_output||{},state.outputs.element_output||{}).filter(n=>n.id===el.node1||n.id===el.node2).map(n=>n.raw??n);
  return ["You are rerunning the Element Agent for a structural frame model.","","Original user request:",origPrompt,"",`A reviewer clicked element ${el.id} in the visualization and marked it as incorrect.`,"Selected element record:",JSON.stringify(el.raw??el,null,2),"","Connected node records:",JSON.stringify(relatedNodes,null,2),"","Please re-check this element against the frame topology, intended member type, node connectivity, orientation, and story/bay placement.","If the element is wrong, regenerate a corrected element-output JSON for the full element set while preserving valid members when possible.","Return structured JSON only and keep the current element-output schema consistent."].join("\n");
}

function renderSelectionPrompt(){
  const pb=$("selection-prompt"),msg=$("selection-message");
  const p=buildSelectionPrompt();pb.value=p;
  if(!state.selectedIssue){msg.textContent="Click a node or element in the visualization to generate a targeted reanalysis prompt.";return;}
  msg.textContent=state.selectedIssue.kind==="node"?`Node ${state.selectedIssue.payload.id} selected.`:`Element ${state.selectedIssue.payload.id} selected.`;
}

function renderVisualization(outputs,consistency){
  const nSvg=$("node-visualization-svg"),nEmpty=$("node-visualization-empty");
  const eSvg=$("element-visualization-svg"),eEmpty=$("element-visualization-empty");
  const nodes=extractNodes(outputs.node_output||{},outputs.element_output||{});
  const elements=extractElements(outputs.element_output||{});
  nSvg.innerHTML="";eSvg.innerHTML="";
  if(!nodes.length){nSvg.style.display="none";nEmpty.style.display="block";eSvg.style.display="none";eEmpty.style.display="block";return;}
  const bounds={minX:Math.min(...nodes.map(n=>n.x)),maxX:Math.max(...nodes.map(n=>n.x)),minY:Math.min(...nodes.map(n=>n.y)),maxY:Math.max(...nodes.map(n=>n.y))};
  const w=100,h=100,pad=10;
  const projected=new Map(nodes.map(n=>[n.id,projectPoint(n,bounds,w,h,pad)]));

  // Color map from consistency status
  const statusColor = {ok:"#10b981", warning:"#f59e0b", error:"#ef4444"};
  const nodeStats = consistency?.node_status || {};
  const elemStats = consistency?.element_status || {};

  nodes.forEach(n=>{
    const pt=projected.get(n.id);
    const st = nodeStats[n.id];
    const fill = st ? (statusColor[st.status]||"#3b82f6") : "#3b82f6";
    const title = st && st.messages && st.messages.length ? st.messages.join(" | ") : "";
    const circle=createSvgEl("circle",{cx:pt.x,cy:pt.y,r:2.3,fill:fill,class:`node-point${state.selectedIssue?.kind==="node"&&state.selectedIssue.payload.id===n.id?" selected":""}`});
    if(title) { const t = document.createElementNS("http://www.w3.org/2000/svg","title"); t.textContent=title; circle.appendChild(t); }
    circle.addEventListener("click",()=>selectIssue("node",n));
    const label=createSvgEl("text",{x:pt.x+2.5,y:pt.y-2.5,"font-size":4,fill:"#e2e8f0"});
    label.textContent=String(n.id);label.addEventListener("click",()=>selectIssue("node",n));
    nSvg.appendChild(circle);nSvg.appendChild(label);
  });
  nSvg.style.display="block";nEmpty.style.display="none";
  if(!elements.length){eSvg.style.display="none";eEmpty.style.display="block";return;}
  elements.forEach(item=>{
    if(!Number.isFinite(item.node1)||!Number.isFinite(item.node2)) return;
    const s=projected.get(item.node1),e=projected.get(item.node2);if(!s||!e) return;
    const st = elemStats[item.id];
    const stroke = st ? (statusColor[st.status]||"#f59e0b") : "#f59e0b";
    const title = st && st.messages && st.messages.length ? st.messages.join(" | ") : "";
    const line=createSvgEl("line",{x1:s.x,y1:s.y,x2:e.x,y2:e.y,stroke:stroke,"stroke-width":1.8,class:`element-line${state.selectedIssue?.kind==="element"&&state.selectedIssue.payload.id===item.id?" selected":""}`});
    if(title) { const t = document.createElementNS("http://www.w3.org/2000/svg","title"); t.textContent=title; line.appendChild(t); }
    const hitbox=createSvgEl("line",{x1:s.x,y1:s.y,x2:e.x,y2:e.y,class:"element-hitbox"});
    const mx=(s.x+e.x)/2,my=(s.y+e.y)/2;
    const label=createSvgEl("text",{x:mx+1.5,y:my-1.5,"font-size":3.2,fill:"#e2e8f0"});
    label.textContent=String(item.id);
    const choose=()=>selectIssue("element",item);
    line.addEventListener("click",choose);hitbox.addEventListener("click",choose);label.addEventListener("click",choose);
    eSvg.appendChild(line);eSvg.appendChild(hitbox);eSvg.appendChild(label);
  });
  eSvg.style.display="block";eEmpty.style.display="none";
}

// ----- Geometry Consistency Rendering -----
function renderConsistency(consistency){
  const summaryEl = document.getElementById("consistency-summary");
  const errorsEl = document.getElementById("consistency-errors");
  if(!consistency||!consistency.summary){
    summaryEl.innerHTML='<p class="form-hint">No geometry validation data yet. Run the pipeline to check node/element consistency.</p>';
    errorsEl.innerHTML="";
    return;
  }

  const s=consistency.summary;
  const statusCls=s.total_errors>0?"err":(s.total_warnings>0?"warn":"ok");

  summaryEl.innerHTML=`
    <div class="consistency-stats" style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px">
      <span class="badge badge-${statusCls}">${s.total_errors>0?"❌ Failed":s.total_warnings>0?"⚠️ Warnings":"✅ Passed"}</span>
      <span style="font-size:12px;color:var(--text-secondary)">${s.total_nodes} nodes · ${s.total_elements} elements · ${s.total_boundary_conditions} BCs</span>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:6px;font-size:11px;margin-bottom:4px">
      <div><span style="color:var(--success)">●</span> Nodes OK: ${s.nodes_ok}</div>
      <div><span style="color:var(--warning)">●</span> Nodes Warning: ${s.nodes_warning}</div>
      <div><span style="color:var(--danger)">●</span> Nodes Error: ${s.nodes_error}</div>
      <div><span style="color:var(--success)">●</span> Elements OK: ${s.elements_ok}</div>
      <div><span style="color:var(--warning)">●</span> Elements Warning: ${s.elements_warning}</div>
      <div><span style="color:var(--danger)">●</span> Elements Error: ${s.elements_error}</div>
    </div>
    ${s.expected_nodes?`<div style="font-size:11px;color:var(--text-muted)">Expected: ~${s.expected_nodes} nodes · ~${s.expected_columns} columns · ~${s.expected_beams} beams</div>`:""}
    ${s.x_grid_lines&&s.x_grid_lines.length?`<div style="font-size:10.5px;color:var(--text-muted);margin-top:2px">Grid X: ${s.x_grid_lines.map(v=>v.toFixed(2)).join(", ")}m &nbsp;|&nbsp; Grid Y: ${s.y_grid_lines.map(v=>v.toFixed(2)).join(", ")}m</div>`:""}
  `;

  // Render errors and warnings list
  const allIssues=[];
  if(consistency.errors) consistency.errors.forEach(e=>allIssues.push({type:"error",msg:e}));
  if(consistency.warnings) consistency.warnings.forEach(w=>allIssues.push({type:"warning",msg:w}));
  if(!allIssues.length){
    errorsEl.innerHTML='<p class="form-hint" style="color:var(--success)">All checks passed.</p>';
    return;
  }
  errorsEl.innerHTML=allIssues.slice(0,30).map(i=>
    `<div style="padding:4px 8px;margin-bottom:3px;border-radius:4px;font-size:11.5px;background:${i.type==="error"?"var(--danger-soft)":"var(--warning-soft)"};color:${i.type==="error"?"var(--danger)":"var(--warning)"}">
      ${i.type==="error"?"❌":"⚠️"} ${escapeHtml(i.msg)}
    </div>`
  ).join("");
  if(allIssues.length>30){
    errorsEl.innerHTML+=`<p class="form-hint">... and ${allIssues.length-30} more issues</p>`;
  }
}

// ----- Status Bar -----
function updateStatusBar(run,exec,bench){
  const map={idle:"idle",running:"running",succeeded:"succeeded",failed:"failed"};
  ["run","exec","bench"].forEach(k=>{
    const st=map[k==="run"?run.status: k==="exec"?exec.status: bench.status]||"idle";
    $(`sb-${k}-dot`).className=`status-dot ${st}`;
    $(`sb-${k}`).textContent=st.charAt(0).toUpperCase()+st.slice(1);
  });
}

// ----- Dashboard -----
function renderDashboard(payload){
  const rl=payload.rl||{},bench=payload.benchmark||{},o=payload.outputs||{};
  const totalCases=bench.total||0,completed=bench.completed||0;
  const runStatus=payload.run?.status||"idle";
  const reward=rl.reward?.total_reward||0;

  $("dashboard-stats").innerHTML=`
    <div class="stat-card"><div class="stat-label">Pipeline Status</div><div class="stat-value ${runStatus==="succeeded"?"ok":runStatus==="running"?"warn":runStatus==="failed"?"err":"info"}">${runStatus.charAt(0).toUpperCase()+runStatus.slice(1)}</div><div class="stat-sub">${payload.run?.message||"Ready"}</div></div>
    <div class="stat-card"><div class="stat-label">Total Reward</div><div class="stat-value ${reward>1.5?"ok":reward>0?"warn":"err"}">${Number(reward).toFixed(2)}</div><div class="stat-sub">${rl.reward?.error_type||"none"}</div></div>
    <div class="stat-card"><div class="stat-label">Benchmark Progress</div><div class="stat-value info">${completed}/${totalCases}</div><div class="stat-sub">Batch: ${bench.batch_id||"N/A"}</div></div>
    <div class="stat-card"><div class="stat-label">Agent Rewards</div><div class="stat-value info">${payload.agent_rewards?.total_experiences||0}</div><div class="stat-sub">Experiences recorded</div></div>
  `;
  $("dash-run-status").textContent=runStatus;
  $("dash-run-status").className=`badge badge-${runStatus}`;
  $("dash-run-msg").textContent=payload.run?.message||"Ready to run.";

  // Mini pipeline in dashboard
  const stages=payload.stages||[];
  const mini=document.getElementById("dash-pipeline-mini");
  if(stages.length){
    const ready=stages.filter(s=>s.status==="ready").length;
    mini.innerHTML=`
      <div class="progress-bar" style="margin-top:8px"><div class="progress-fill ${ready===stages.length?"success":""}" style="width:${stages.length?ready/stages.length*100:0}%"></div></div>
      <div style="display:flex;justify-content:space-between;margin-top:4px;font-size:10.5px;color:var(--text-muted)">
        ${stages.map(s=>`<span>${s.title.split(" ")[0]}</span>`).join("")}
      </div>`;
  } else { mini.innerHTML='<p class="form-hint">No pipeline data yet.</p>'; }

  // Recent activity
  const hist=rl.prompt_history||[];
  const recent=$("dash-recent");
  if(hist.length){
    recent.innerHTML=hist.slice(0,5).map(h=>`<div style="padding:6px 0;border-bottom:1px solid var(--border-light);font-size:12px"><span class="badge badge-${h.status||"idle"}" style="margin-right:8px">${h.status||"?"}</span>${escapeHtml(shortPrompt(h.prompt))}<span style="float:right;color:var(--text-muted);font-size:10.5px">${(h.created_at||"").slice(0,19)}</span></div>`).join("");
  } else { recent.innerHTML='<p class="form-hint">No recent activity.</p>'; }
}

// ----- Render Run Status -----
function renderRun(run){
  const st=run.status||"idle";
  $("run-status").textContent=st;
  $("run-status").className=`badge badge-${st}`;
  const started=run.started_at?` Started: ${run.started_at}`:"";
  const finished=run.finished_at?` Finished: ${run.finished_at}`:"";
  const err=run.error?` Error: ${run.error}`:"";
  $("run-message").textContent=`${run.message||"Ready to run."}${started}${finished}${err}`;
  const btn=$("submit-prompt");
  btn.disabled=st==="running";
  btn.textContent=st==="running"?"⏳ Running...":"▶ Run Pipeline";
}

function renderExecution(exec,diagrams,outputs){
  const st=exec.status||"idle";
  $("execution-status").textContent=st;
  $("execution-status").className=`badge badge-${st}`;
  const pp=exec.python_path?` Python: ${exec.python_path}`:"";
  const sa=exec.started_at?` Started: ${exec.started_at}`:"";
  const fa=exec.finished_at?` Finished: ${exec.finished_at}`:"";
  const er=exec.error?` Error: ${exec.error}`:"";
  $("execution-message").textContent=`${exec.message||"Ready."}${pp}${sa}${fa}${er}`;
  const btn=$("run-generated-code");
  btn.disabled=st==="running";
  btn.textContent=st==="running"?"⏳ Executing...":"⚡ Run Generated Code";
  $("execution-stdout").textContent=outputs.execution_stdout||"(empty)";
  $("execution-stderr").textContent=outputs.execution_stderr||"(empty)";
  $("python-check-viewer").textContent=JSON.stringify(outputs.python_check_output||{},null,2)||"(empty)";
  renderSectionDiagrams(diagrams,outputs);
}

function renderSectionDiagrams(sd,outputs){
  const st=sd.status||"idle";
  $("opsvis-status").textContent=st;
  $("opsvis-status").className=`badge badge-${st}`;
  const pp=sd.python_path?` Python: ${sd.python_path}`:"";
  $("opsvis-message").textContent=`${sd.message||"Run code to render."}${pp}`;
  [["axial",sd.axial_image_url],["shear",sd.shear_image_url],["moment",sd.moment_image_url]].forEach(([pref,url])=>{
    const img=$(pref+"-diagram-image"),empty=$(pref+"-diagram-empty");
    if(url){img.src=url;img.style.display="block";empty.style.display="none";}
    else{img.removeAttribute("src");img.style.display="none";empty.style.display="block";}
  });
}

// ----- RL Panel -----
function renderRL(rl){
  const reward=rl.reward||{},action=rl.policy_action||{};
  $("rl-total-reward").textContent=Number(reward.total_reward||0).toFixed(2);
  const v=Number(reward.total_reward||0);
  const circle=$("rl-score-circle");
  circle.className="rl-score-circle "+(v>=1.5?"ok":v>0?"warn":"err");
  $("rl-error-type").textContent=reward.error_type||"none";
  $("rl-policy-action").textContent=`${action.action_type||"observe"} → ${action.target_agent||"orchestrator"}`;
  $("rl-policy-reason").textContent=action.reason||"Waiting for more signals.";
  $("rl-db-path").textContent=rl.database_path?"SQLite":"No DB";

  const list=$("rl-component-list");
  list.innerHTML="";
  (reward.components||[]).forEach(c=>{
    const v=Number(c.value||0);
    const pct=Math.min(Math.abs(v)/4*100,100);
    list.innerHTML+=`
      <div class="rl-component-bar">
        <span class="rl-component-name">${escapeHtml(c.name||"unknown")}</span>
        <div class="rl-component-track"><div class="rl-component-fill" style="width:${pct}%;background:${v>=0?"var(--success)":"var(--danger)"}"></div></div>
        <span class="rl-component-value" style="color:${v>=0?"var(--success)":"var(--danger)"}">${v>=0?"+":""}${v.toFixed(2)}</span>
      </div>`;
  });
  if(!(reward.components||[]).length) list.innerHTML='<p class="form-hint">No reward components yet. Run the pipeline or save feedback.</p>';
}

// ----- History -----
function renderPromptHistory(items){
  const host=$("prompt-history-list");
  if(!items.length){host.innerHTML='<div class="card"><p class="form-hint">No prompt history yet. Submit a prompt to create the first record.</p></div>';return;}
  host.innerHTML=items.map((item,i)=>{
    const reward=item.total_reward===null||item.total_reward===undefined?"pending":Number(item.total_reward).toFixed(2);
    const runId=item.run_id||"";
    return`<div class="history-item" data-run-id="${escapeHtml(runId)}">
      <div class="history-item-top"><strong><span class="badge badge-${item.status||"idle"}">${item.status||"?"}</span></strong><span style="font-size:10.5px;color:var(--text-muted)">${escapeHtml((item.created_at||"").slice(0,19))}</span></div>
      <p>${escapeHtml(shortPrompt(item.prompt))}</p>
      <div class="history-item-meta"><span>Reward: ${reward}</span><span>Error: ${escapeHtml(item.error_type||"none")}</span><span>Policy: ${escapeHtml(item.policy_action||"pending")}</span></div>
      <div class="btn-group" style="margin-top:8px">
        <button class="btn btn-ghost btn-sm use-history-prompt">📋 Use</button>
        <button class="btn btn-primary btn-sm rerun-history-prompt">▶ Run Again</button>
        <button class="btn btn-success btn-sm run-history-code" ${runId?"":"disabled title='No run_id'"}>▶ Run Code</button>
      </div>
      <div class="history-item-result" data-result-for="${escapeHtml(runId)}" style="display:none;margin-top:8px"></div>
    </div>`;
  }).join("");
  host.querySelectorAll(".use-history-prompt").forEach((btn,i)=>{
    btn.addEventListener("click",()=>{
      const p=items[i].prompt||"";
      $("prompt-input").value=p;
      document.querySelector("[data-section='run']").click();
      toast("Prompt loaded into input box.","info");
    });
  });
  host.querySelectorAll(".rerun-history-prompt").forEach((btn,i)=>{
    btn.addEventListener("click",()=>{
      const p=items[i].prompt||"";
      $("prompt-input").value=p;
      document.querySelector("[data-section='run']").click();
      submitPrompt(p);
    });
  });
  host.querySelectorAll(".run-history-code").forEach((btn,i)=>{
    btn.addEventListener("click",async()=>{
      const runId=items[i].run_id||"";
      if(!runId){toast("No run_id for this entry.","error");return;}
      const resultEl=host.querySelector(`.history-item-result[data-result-for="${CSS.escape(runId)}"]`);
      btn.disabled=true;btn.textContent="⏳ Running...";
      if(resultEl){resultEl.style.display="block";resultEl.innerHTML='<p class="form-hint">Executing archived code...</p>';}
      try{
        const r=await fetch("/api/run-benchmark-code",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({case_id:runId})});
        const data=await r.json();
        if(resultEl){
          const status=data.status||(data.ok?"succeeded":"failed");
          resultEl.innerHTML=`
            <div><span class="badge badge-${escapeHtml(status)}">${escapeHtml(status)}</span> <span style="font-size:11px;color:var(--text-muted)">${escapeHtml(data.message||"")}</span></div>
            <details style="margin-top:6px"><summary style="cursor:pointer;font-size:11px">stdout / stderr</summary>
              <pre style="font-size:10.5px;max-height:240px;overflow:auto;background:var(--bg-elevated);padding:6px;border-radius:4px;margin-top:4px">${escapeHtml((data.stdout||"")+(data.stderr?"\n--- stderr ---\n"+data.stderr:""))}</pre>
            </details>`;
        }
        toast(data.ok?"Code executed successfully.":"Code execution failed.",data.ok?"success":"error");
      }catch(err){
        if(resultEl){resultEl.innerHTML=`<div class="badge badge-failed">network error</div> <span style="font-size:11px;color:var(--text-muted)">${escapeHtml(String(err))}</span>`;}
        toast("Run failed: "+err,"error");
      }finally{
        btn.disabled=false;btn.textContent="▶ Run Code";
      }
    });
  });
}

// ----- Benchmark -----
function renderBenchmark(bench){
  const st=bench.status||"idle";
  $("benchmark-status").textContent=st;
  $("benchmark-status").className=`badge badge-${st}`;
  const prog=bench.total>0?` Progress: ${bench.completed||0}/${bench.total}`:"";
  const batch=bench.batch_id?` Batch: ${bench.batch_id}`:"";
  $("benchmark-message").textContent=`${bench.message||"Ready."}${prog}${batch}`;

  const btn=$("run-benchmark");btn.disabled=st==="running";
  const cnt=$("benchmark-count").value||"30";
  btn.textContent=st==="running"?"⏳ Running...":`▶ Run ${cnt} Prompt Cases`;
  $("retry-failed-benchmark").disabled=st==="running";
  $("run-review-set").disabled=st==="running";

  // Progress bar
  const pw=$("benchmark-progress-wrap"),pb=$("benchmark-progress-bar");
  if(bench.total>0){pw.hidden=false;pb.style.width=(bench.completed||0)/bench.total*100+"%";}
  else{pw.hidden=true;}

  // Update nav badge
  const bdg=$("nav-bench-badge");
  if(bench.total>0){bdg.style.display="";bdg.textContent=bench.completed+"/"+bench.total;}
  else bdg.style.display="none";

  const host=$("benchmark-case-list");
  const cases=bench.cases||[];
  if(!cases.length){host.innerHTML='<div class="card"><p class="form-hint">No benchmark cases yet. Click Run Benchmark to start.</p></div>';return;}

  // Render only first 30 for performance; rest on scroll
  const toShow = cases.slice(0, 50);
  host.innerHTML = toShow.map(item=>`
    <div class="benchmark-case-item" data-case-id="${escapeHtml(item.case_id||"")}">
      <div class="benchmark-case-top">
        <span class="benchmark-case-id">${escapeHtml(item.case_id||"")}</span>
        <span class="badge badge-${item.status||"idle"}">${item.status||"?"}</span>
      </div>
      <p class="benchmark-case-prompt">${escapeHtml(shortPrompt(item.prompt))}</p>
      <details class="benchmark-full-prompt"><summary>Full Prompt</summary><pre>${escapeHtml(item.prompt||"")}</pre></details>
      <div class="benchmark-case-meta">
        <span>Tokens: ${Number(item.total_tokens||0)}</span>
        <span>Reward: ${item.reward===null||item.reward===undefined?"—":Number(item.reward).toFixed(2)}</span>
        <span>Review: ${escapeHtml(item.human_verdict||"unreviewed")}</span>
        ${item.retry_from_case_id?`<span>Retry of: ${escapeHtml(item.retry_from_case_id)}</span>`:""}
      </div>
      <div class="btn-group benchmark-case-actions">
        <button class="btn btn-ghost btn-sm view-benchmark-outputs">📄 Outputs</button>
        <button class="btn btn-ghost btn-sm view-benchmark-code">📝 Code</button>
        <button class="btn btn-ghost btn-sm run-benchmark-code">⚡ Run</button>
        <button class="btn btn-success btn-sm mark-benchmark-correct">✓</button>
        <button class="btn btn-danger btn-sm mark-benchmark-incorrect">✗</button>
        <button class="btn btn-ghost btn-sm use-benchmark-prompt">📋 Use</button>
        <button class="btn btn-ghost btn-sm copy-benchmark-prompt">📝 Copy</button>
      </div>
      <div class="benchmark-code-run-panel"></div>
      <div class="benchmark-output-panel"></div>
    </div>
  `).join("");

  host.querySelectorAll(".use-benchmark-prompt").forEach((btn,i)=>{
    btn.addEventListener("click",()=>{
      const c=toShow[i];
      $("prompt-input").value=c.prompt||"";
      document.querySelector("[data-section='run']").click();
      toast("Prompt loaded.","info");
    });
  });
  host.querySelectorAll(".copy-benchmark-prompt").forEach((btn,i)=>{
    btn.addEventListener("click",()=>{
      navigator.clipboard.writeText(toShow[i].prompt||"").then(()=>toast("Copied to clipboard.","success"),()=>toast("Copy failed.","error"));
    });
  });
  host.querySelectorAll(".view-benchmark-outputs").forEach((btn,i)=>{
    btn.addEventListener("click",()=>toggleBenchmarkOutputs(btn.closest(".benchmark-case-item"),toShow[i].case_id));
  });
  host.querySelectorAll(".view-benchmark-code").forEach((btn,i)=>{
    btn.addEventListener("click",()=>toggleBenchmarkOutputs(btn.closest(".benchmark-case-item"),toShow[i].case_id,"complete_code"));
  });
  host.querySelectorAll(".run-benchmark-code").forEach((btn,i)=>{
    btn.addEventListener("click",()=>runBenchmarkCode(btn.closest(".benchmark-case-item"),toShow[i].case_id));
  });
  host.querySelectorAll(".mark-benchmark-correct").forEach((btn,i)=>{
    btn.addEventListener("click",()=>reviewBenchmarkCase(toShow[i].case_id,"correct",btn.closest(".benchmark-case-item")?.querySelector(".benchmark-review-notes")?.value||""));
  });
  host.querySelectorAll(".mark-benchmark-incorrect").forEach((btn,i)=>{
    btn.addEventListener("click",()=>reviewBenchmarkCase(toShow[i].case_id,"incorrect",btn.closest(".benchmark-case-item")?.querySelector(".benchmark-review-notes")?.value||""));
  });
}

function renderBenchmarkCodeRun(panel,payload){
  panel.innerHTML=`
    <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 12px;border:1px solid var(--border);border-radius:var(--radius-sm) var(--radius-sm) 0 0;background:var(--bg-elevated);margin-top:8px">
      <strong style="font-size:12px">Code Execution</strong>
      <span class="badge badge-${payload.status||"idle"}">${escapeHtml(payload.status||"unknown")}</span>
    </div>
    <div style="font-size:10.5px;color:var(--text-muted);padding:6px 12px">
      Python: ${escapeHtml(payload.python_path||"unknown")} | Return: ${payload.returncode??"none"}
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;border:1px solid var(--border);border-radius:0 0 var(--radius-sm) var(--radius-sm);overflow:hidden">
      <div><h4 style="margin:0;padding:6px 10px;font-size:10.5px;color:var(--text-muted);background:var(--bg-elevated)">stdout</h4><pre class="code-viewer" style="min-height:120px;max-height:220px;border-radius:0">${escapeHtml(payload.stdout||"(empty)")}</pre></div>
      <div><h4 style="margin:0;padding:6px 10px;font-size:10.5px;color:var(--text-muted);background:var(--bg-elevated)">stderr</h4><pre class="code-viewer" style="min-height:120px;max-height:220px;border-radius:0">${escapeHtml(payload.stderr||"(empty)")}</pre></div>
    </div>`;
}

async function runBenchmarkCode(row,caseId){
  const btn=row.querySelector(".run-benchmark-code"),panel=row.querySelector(".benchmark-code-run-panel");
  btn.disabled=true;btn.textContent="⏳ Running...";
  panel.innerHTML=`<p class="form-hint">Running code for ${escapeHtml(caseId)}...</p>`;
  try{
    const p=await request("/api/run-benchmark-code",{method:"POST",body:JSON.stringify({case_id:caseId})});
    renderBenchmarkCodeRun(panel,p);
    toast(p.message||"Done.","success");
  }catch(e){toast(e.message,"error");}
  finally{btn.disabled=false;btn.textContent="⚡ Run";}
}

async function toggleBenchmarkOutputs(row,caseId,preferred="node_output"){
  const panel=row.querySelector(".benchmark-output-panel");
  if(panel.dataset.open==="true"){
    panel.dataset.open="false";panel.innerHTML="";return;
  }
  panel.dataset.open="true";
  panel.innerHTML='<p class="form-hint">Loading archived outputs...</p>';
  const p=await request(`/api/benchmark-case-artifacts?case_id=${encodeURIComponent(caseId)}`);
  if(!p.available){panel.innerHTML=`<p class="form-hint">${escapeHtml(p.message||"No outputs.")}</p>`;return;}
  const outputs=p.outputs||{};
  const tabs=[["complete_code","Code"],["node_output","Node"],["element_output","Element"],["geometry_code","Geom Code"],["load_output","Loads"],["compiled_model","Compiled"],["pipeline_log","Log"]];
  panel.innerHTML=`
    <div style="margin-top:8px;font-size:11px;color:var(--text-muted);margin-bottom:6px">Archived Outputs — ${escapeHtml(p.artifact_dir||"")}</div>
    <div class="tabs" style="margin-bottom:6px">${tabs.map(([k,label])=>`<button class="tab-btn ${k===preferred?"active":""}" data-artifact="${k}">${label}</button>`).join("")}</div>
    <pre class="code-viewer" style="min-height:180px;max-height:360px"></pre>`;
  const viewer=panel.querySelector(".code-viewer");
  const renderArt=(key)=>{
    const txt=formatValue(outputs[key],key.includes("code")||key.includes("log"));
    if(!String(txt).trim()||txt==="(empty)"){viewer.textContent=`No content for ${key}.`;return;}
    viewer.innerHTML=(key.includes("code")||key.includes("log"))?highlightPython(txt):highlightJson(txt);
  };
  renderArt(preferred);
  panel.querySelectorAll(".tab-btn").forEach(tab=>{
    tab.addEventListener("click",()=>{
      panel.querySelectorAll(".tab-btn").forEach(t=>t.classList.remove("active"));
      tab.classList.add("active");renderArt(tab.dataset.artifact);
    });
  });
}

// ----- Agent Rewards -----
async function loadAgentRewards(){
  const host=$("agent-rewards-content");
  try{
    const d=await request("/api/agent-rewards");
    if(!d.ok){host.innerHTML=`<p class="form-hint">${d.message}</p>`;return;}
    const summary=d.summary||[];
    if(!summary.length){host.innerHTML='<div class="card"><p class="form-hint">No agent reward data yet. Enable RL and run the pipeline to collect data.</p></div>';return;}
    host.innerHTML=`
      <div class="card" style="margin-bottom:14px">
        <table class="data-table agent-rewards-table">
          <thead><tr><th>Agent</th><th>Runs</th><th>Successes</th><th>Avg Reward</th><th>Avg Base</th><th>Avg Validation</th><th>Avg Downstream</th><th>Variants</th></tr></thead>
          <tbody>${summary.map(r=>`
            <tr><td>${escapeHtml(r.agent_name)}</td><td>${r.total_runs}</td><td>${r.success_count}</td><td style="color:${r.avg_reward>=0.5?"var(--success)":"var(--danger)"}">${Number(r.avg_reward).toFixed(3)}</td><td>${Number(r.avg_base||0).toFixed(3)}</td><td>${Number(r.avg_validation||0).toFixed(3)}</td><td>${Number(r.avg_downstream||0).toFixed(3)}</td><td>${r.variant_count}</td></tr>
          `).join("")}</tbody>
        </table>
      </div>`;
    const recent=d.recent_experiences||[];
    if(recent.length){
      host.innerHTML+=`<div class="card"><div class="card-header"><h3>Recent Experiences</h3></div><div style="max-height:300px;overflow-y:auto">${recent.slice(0,20).map(e=>`
        <div style="padding:8px 0;border-bottom:1px solid var(--border-light);font-size:12px;display:flex;justify-content:space-between;gap:12px">
          <span><strong>${escapeHtml(e.agent_name)}</strong> <span style="color:var(--text-muted)">${escapeHtml(e.prompt_variant||"default")}</span></span>
          <span style="color:${e.reward>=0.5?"var(--success)":"var(--danger)"};font-weight:600">${Number(e.reward).toFixed(3)}</span>
          <span style="color:var(--text-muted);font-size:10.5px">${(e.created_at||"").slice(0,19)}</span>
        </div>`).join("")}</div></div>`;
    }
  }catch(e){host.innerHTML=`<p class="form-hint">Error: ${e.message}</p>`;}
}

// ----- Polling -----
function syncPolling(run,exec,sectionDiagrams,bench={}){
  const shouldPoll=(run.status||"idle")==="running"||(exec.status||"idle")==="running"||(sectionDiagrams.status||"idle")==="running"||(bench.status||"idle")==="running";
  if(shouldPoll) startPolling(); else stopPolling();
}
function startPolling(){
  if(state.pollTimer) return;
  state.pollTimer=setInterval(()=>{loadState().catch(()=>stopPolling());},2500);
}
function stopPolling(){
  if(!state.pollTimer) return;
  clearInterval(state.pollTimer);state.pollTimer=null;
}

// ----- Hydrate State -----
const TIER_CONFIG = {
  tier1: {
    label: "Core Modeling",
    agents: ["problem_analysis", "construction_planning", "node_agent", "element_agent"],
  },
  tier2: {
    label: "Code Generation",
    agents: ["load_assignment", "geometry_code_translator", "complete_code_generator"],
  },
  tier3: {
    label: "Verification",
    agents: ["python_check_agent"],
  },
};

function renderLLMConfig(tierData) {
  tierData = tierData || {};
  const tiers = tierData.tiers || {};

  const rows = Object.entries(TIER_CONFIG).map(([tid, tdef]) => {
    const cfg = tiers[tid] || {};
    const agentsList = tdef.agents.map(a => `<code>${escapeHtml(a)}</code>`).join(", ");
    return `<div class="tier-card">
      <div class="tier-header">
        <strong>${escapeHtml(tdef.label)}</strong>
        <span class="form-hint">${agentsList}</span>
      </div>
      <div class="tier-inputs">
        <input class="form-input llm-model-name" data-tier="${escapeHtml(tid)}" placeholder="Model name" value="${escapeHtml(cfg.model_name||"")}">
        <input class="form-input llm-api-key" data-tier="${escapeHtml(tid)}" type="password" placeholder="API key" value="${escapeHtml(cfg.api_key||"")}">
        <input class="form-input llm-base-url" data-tier="${escapeHtml(tid)}" placeholder="Base URL" value="${escapeHtml(cfg.base_url||"")}">
      </div>
    </div>`;
  }).join("");

  $("llm-config-table").innerHTML = rows;

  const configured = Object.values(tiers).filter(c => c.api_key || c.model_name).length;
  $("llm-config-status").textContent = configured > 0
    ? `${configured}/3 tier(s) configured — overrides active`
    : "Using server defaults (DEEPSEEK_API_KEY / DEEPSEEK_MODEL)";
}

function collectLLMConfig() {
  const tiers = {};
  document.querySelectorAll(".llm-model-name").forEach(input => {
    const tid = input.dataset.tier;
    if (!tiers[tid]) tiers[tid] = {};
    tiers[tid].model_name = input.value.trim();
  });
  document.querySelectorAll(".llm-api-key").forEach(input => {
    const tid = input.dataset.tier;
    if (!tiers[tid]) tiers[tid] = {};
    tiers[tid].api_key = input.value.trim();
  });
  document.querySelectorAll(".llm-base-url").forEach(input => {
    const tid = input.dataset.tier;
    if (!tiers[tid]) tiers[tid] = {};
    tiers[tid].base_url = input.value.trim();
  });
  return tiers;
}

async function saveAgentLLMConfig() {
  const tiers = collectLLMConfig();
  const p = await request("/api/agent-llm-config", { method: "POST", body: JSON.stringify({ tiers }) });
  if (p.state) hydrateState(p.state);
  toast(p.message, p.ok ? "success" : "error");
}

function clearLLMConfig() {
  document.querySelectorAll(".llm-model-name,.llm-api-key,.llm-base-url").forEach(el => el.value = "");
  saveAgentLLMConfig();
}

function applyAllLLMConfig() {
  const firstModel = document.querySelector(".llm-model-name")?.value || "";
  const firstKey = document.querySelector(".llm-api-key")?.value || "";
  const firstUrl = document.querySelector(".llm-base-url")?.value || "";
  if (!firstModel && !firstKey && !firstUrl) {
    toast("Fill in the first tier's fields first, then click 'Apply to All'.", "info");
    return;
  }
  document.querySelectorAll(".llm-model-name").forEach(el => { if (!el.value) el.value = firstModel; });
  document.querySelectorAll(".llm-api-key").forEach(el => { if (!el.value) el.value = firstKey; });
  document.querySelectorAll(".llm-base-url").forEach(el => { if (!el.value) el.value = firstUrl; });
  toast("Applied first agent's config to all empty fields.", "success");
}

function hydrateState(payload){
  state.prompt=payload.prompt||"";
  state.outputs=payload.outputs||{};
  state.consistency=payload.geometry_consistency||null;
  $("prompt-input").value=state.prompt;
  const cc=state.prompt.length;$("prompt-char-count").textContent=`${cc} characters`;
  $("prompt-token-est").textContent=`~${Math.ceil(cc/4)} tokens`;

  renderRun(payload.run||{});
  renderExecution(payload.execution||{},payload.section_diagrams||{},payload.outputs||{});
  renderVisualization(payload.outputs||{},state.consistency);
  renderConsistency(state.consistency);
  renderStages(payload.stages||[]);
  renderRL(payload.rl||{});
  renderPromptHistory(payload.rl?.prompt_history||[]);
  renderBenchmark(payload.benchmark||{});
  renderDashboard(payload);
  renderLLMConfig(payload.agent_llm_config || {});
  renderViewer();
  renderSelectionPrompt();
  updateStatusBar(payload.run||{},payload.execution||{},payload.benchmark||{});

  // Nav badge for run status
  const rs=payload.run?.status||"idle";
  const rBadge=$("nav-run-badge");
  if(rs==="succeeded"){rBadge.style.display="";rBadge.textContent="OK";rBadge.className="nav-badge ok";}
  else if(rs==="failed"){rBadge.style.display="";rBadge.textContent="FAIL";rBadge.className="nav-badge err";}
  else if(rs==="running"){rBadge.style.display="";rBadge.textContent="...";rBadge.className="nav-badge warn";}
  else rBadge.style.display="none";

  syncPolling(payload.run||{},payload.execution||{},payload.section_diagrams||{},payload.benchmark||{});
}

// ----- API Calls -----
async function loadState(){
  const p=await request("/api/state");
  hydrateState(p);
}

async function submitPrompt(promptOverride=null){
  const prompt=(promptOverride??$("prompt-input").value).trim();
  if(!prompt){toast("Prompt cannot be empty.","error");return;}
  const p=await request("/api/submit",{method:"POST",body:JSON.stringify({prompt})});
  if(p.state) hydrateState(p.state);
  toast(p.message,p.ok?"success":"error");
}

async function sendFeedback(verdict){
  const p=await request("/api/feedback",{method:"POST",body:JSON.stringify({
    prompt:$("prompt-input").value.trim(),verdict,
    notes:$("feedback-notes").value.trim(),selected_object:state.selectedIssue||null
  })});
  if(p.state) hydrateState(p.state);
  toast(p.message,p.ok?"success":"error");
}

async function runGeneratedCode(){
  const p=await request("/api/run-generated-code",{method:"POST",body:"{}"});
  if(p.state) hydrateState(p.state);
  toast(p.message,p.ok?"success":"error");
}

async function runBenchmark(){
  const count=Number($("benchmark-count").value)||30;
  const seed=Number($("benchmark-seed").value)||20260516;
  const start_from=Number($("benchmark-start-from").value)||1;
  const p=await request("/api/run-benchmark",{method:"POST",body:JSON.stringify({count,seed,start_from})});
  if(p.state) hydrateState(p.state);
  toast(p.message,p.ok?"success":"error");
}

async function retryFailedBenchmark(){
  const p=await request("/api/retry-failed-benchmark",{method:"POST",body:"{}"});
  if(p.state) hydrateState(p.state);
  toast(p.message,p.ok?"success":"error");
}

async function runReviewSet(){
  const p=await request("/api/run-review-set",{method:"POST",body:"{}"});
  if(p.state) hydrateState(p.state);
  toast(p.message,p.ok?"success":"error");
}

async function reviewBenchmarkCase(caseId,verdict,notes){
  const p=await request("/api/review-benchmark",{method:"POST",body:JSON.stringify({case_id:caseId,verdict,notes})});
  if(p.state) hydrateState(p.state);
  toast(p.message,p.ok?"success":"error");
}

// ----- Event Bindings -----
function bindEvents(){
  $("submit-prompt").addEventListener("click",()=>submitPrompt().catch(e=>toast(e.message,"error")));
  $("reload-state").addEventListener("click",()=>loadState().catch(e=>toast(e.message,"error")));
  $("reload-state-2").addEventListener("click",()=>loadState().catch(e=>toast(e.message,"error")));

  $("prompt-input").addEventListener("input",()=>{
    const cc=$("prompt-input").value.length;
    $("prompt-char-count").textContent=`${cc} characters`;
    $("prompt-token-est").textContent=`~${Math.ceil(cc/4)} tokens`;
  });

  $("mark-correct").addEventListener("click",()=>sendFeedback("correct").catch(e=>toast(e.message,"error")));
  $("mark-incorrect").addEventListener("click",()=>sendFeedback("incorrect").catch(e=>toast(e.message,"error")));
  $("run-generated-code").addEventListener("click",()=>runGeneratedCode().catch(e=>toast(e.message,"error")));

  function updateBenchBtn(){
    const btn=$("run-benchmark");
    if(btn.disabled) return;
    btn.textContent=`▶ Run ${$("benchmark-count").value||"30"} Prompt Cases`;
  }
  $("benchmark-count").addEventListener("input",updateBenchBtn);
  $("benchmark-start-from").addEventListener("input",updateBenchBtn);
  updateBenchBtn();

  $("run-benchmark").addEventListener("click",()=>runBenchmark().catch(e=>toast(e.message,"error")));
  $("retry-failed-benchmark").addEventListener("click",()=>retryFailedBenchmark().catch(e=>toast(e.message,"error")));
  $("run-review-set").addEventListener("click",()=>runReviewSet().catch(e=>toast(e.message,"error")));

  $("use-selection-prompt").addEventListener("click",()=>{
    const p=buildSelectionPrompt();
    if(!p){toast("Select a node or element first.","error");return;}
    $("prompt-input").value=p;
    document.querySelector("[data-section='run']").click();
    toast("Reanalysis prompt loaded.","success");
  });
  $("run-selection-reanalysis").addEventListener("click",()=>{
    const p=buildSelectionPrompt();
    if(!p){toast("Select a node or element first.","error");return;}
    $("prompt-input").value=p;
    document.querySelector("[data-section='run']").click();
    submitPrompt(p);
  });

  // Viewer tabs
  $("viewer-tabs").addEventListener("click",e=>{
    if(!e.target.classList.contains("tab-btn")) return;
    $("viewer-tabs").querySelectorAll(".tab-btn").forEach(t=>t.classList.remove("active"));
    e.target.classList.add("active");
    state.currentView=e.target.dataset.view;
    renderViewer();
  });

  // Refresh agent rewards
  $("refresh-agent-rewards").addEventListener("click",()=>loadAgentRewards().catch(e=>toast(e.message,"error")));
}

// ----- Init -----
initTheme();
initNav();
initMobile();
bindEvents();
loadState().catch(e=>{console.error(e);toast("Failed to load state.","error");});
// Load agent rewards on section switch
document.querySelector('.nav-item[data-section="agent-rewards"]').addEventListener("click",()=>loadAgentRewards().catch(()=>{}));
