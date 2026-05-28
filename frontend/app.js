// ===================== STATE =====================
const API_URL = "https://accountastudy.onrender.com/api";
const API_ORIGIN = API_URL.replace(/\/api$/, "");

/** Turn relative /uploads/... paths into absolute URLs for <img> when the UI is served from Live Server or another origin. */
function absUploadUrl(path) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return API_ORIGIN + (path.startsWith("/") ? path : "/" + path);
}

/** Convert data:image/...;base64,... to Blob for multipart upload */
function dataURLtoBlob(dataurl) {
  const arr = dataurl.split(",");
  const mime = (arr[0].match(/:(.*?);/) || [])[1] || "image/jpeg";
  const bstr = atob(arr[1]);
  let n = bstr.length;
  const u8arr = new Uint8Array(n);
  while (n--) u8arr[n] = bstr.charCodeAt(n);
  return new Blob([u8arr], { type: mime });
}

const S = {
  user: null,
  submissions: [],
  sessions: [],
  activeSessionId: null,
  timerState:'idle',timerStart:null,timerElapsed:0,timerInterval:null,
  currentSubject:'Mathematics',
  currentPage:'dashboard',
  charts:{},
  lbMode:'weekly',
  verifyTarget:null,
  verifyStatus:'completed',
  adminFilter:'all',
  timerFiles:{timer:null,quest:null},
  leaderboardData: [],
};

// ===================== AUTH =====================
function switchView(v){
  document.getElementById('loginView').style.display=v==='login'?'block':'none';
  document.getElementById('registerView').style.display=v==='register'?'block':'none';
}

async function doLogin() {
  const email = document.getElementById("loginEmail").value;
  const password = document.getElementById("loginPass").value;
  try {
    const res = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) { alert(data.message || "Login failed"); return; }
    localStorage.setItem("token", data.token);
    // login endpoint already returns user, no need for /users/me
    await loginUser(data.user);
  } catch (err) {
    console.error(err);
    alert("Error connecting to server");
  }
}

async function doRegister() {
  const name = document.getElementById("regName").value;
  const email = document.getElementById("regEmail").value;
  const password = document.getElementById("regPass").value;
  try {
    const res = await fetch(`${API_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password })
    });
    const data = await res.json();
    if (!res.ok) { alert(data.message || "Register failed"); return; }
    alert("Registered successfully 🎉 Please log in.");
    switchView('login');
  } catch (err) {
    alert("Server error");
  }
}

function authHeader() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function loginUser(user){
  S.user=user;
  document.getElementById('authScreen').style.display='none';
  document.getElementById('app').style.display='flex';
  const avatar = user.avatar || (user.name ? user.name[0].toUpperCase() : '?');
  const color = user.color || '#3B82F6';
  document.getElementById('sbAvatar').textContent=avatar;
  document.getElementById('sbAvatar').style.background=color;
  document.getElementById('sbName').textContent=user.name;
  document.getElementById('sbRole').textContent=user.role==='admin'?'⚡ Administrator':'🎓 Student';
  document.getElementById('sbStreak').textContent='🔥 '+(user.streak||0);
  if(user.role==='admin'){
    document.getElementById('nav-admin-verify').style.display='flex';
    document.getElementById('nav-admin-users').style.display='flex';
    document.getElementById('submitBtn').style.display='none';
    document.getElementById('nav-submit').style.display='none';
  }
  await Promise.all([fetchSubmissions(), fetchSessions()]);
  fetchLeaderboard();
  initCharts();
  updatePendingBadge();
  renderDashboard();
  renderLb();
  renderAdminSubmissions();
  renderAnalytics();
  renderTodaySub();
  renderTimerSessions();
  updateDeadlineBanner();
  toast(`Welcome back, ${user.name.split(' ')[0]}!`,'success');
  nav('dashboard');
}

async function fetchSubmissions() {
  try {
    const isAdmin = S.user?.role === "admin";
    const url = isAdmin
      ? `${API_URL}/submission/all?limit=200`
      : `${API_URL}/submission/my`;
    const res = await fetch(url, { headers: { ...authHeader() } });
    if (!res.ok) return;
    const data = await res.json();
    let raw = data.submissions || [];
    if (!isAdmin) {
      raw = raw.map((s) => ({
        ...s,
        _id: s._id || s.id,
        hours: s.hours ?? s.hoursStudied,
        questScreenshot: s.questScreenshot || s.questionScreenshot,
        verified: s.isVerified ?? s.verified,
      }));
    } else {
      raw = raw.map((s) => ({
        ...s,
        _id: s._id || s.id,
        userId: s.student ? { _id: s.student.id, name: s.student.name, email: s.student.email, avatar: s.student.avatar, streak: s.student.streak } : s.userId,
        hours: s.hoursStudied,
        questScreenshot: s.questionScreenshot,
        verified: s.isVerified,
      }));
    }
    S.submissions = raw.map((s) => ({
      ...s,
      timerScreenshot: absUploadUrl(s.timerScreenshot),
      questScreenshot: absUploadUrl(s.questScreenshot || s.questionScreenshot),
    }));
  } catch (err) {
    console.error("Failed to fetch submissions:", err);
  }
}

async function fetchSessions() {
  if (!S.user || S.user.role === "admin") return;
  try {
    const res = await fetch(`${API_URL}/session/user`, { headers: { ...authHeader() } });
    if (!res.ok) return;
    const data = await res.json();
    S.sessions = (data.sessions || []).map((s) => ({
      subject: s.subject,
      duration: s.duration,
      endTime: s.endTime,
    }));
  } catch (err) {
    console.error("Failed to fetch sessions:", err);
  }
}



async function fetchLeaderboard() {
  try {
    const res = await fetch(`${API_URL}/leaderboard?mode=${S.lbMode}`, {
      headers: { ...authHeader() }
    });
    if (!res.ok) return;
    const data = await res.json();
    // Backend returns { leaderboard: [...] }
    S.leaderboardData = data.leaderboard || data.students || data.users || (Array.isArray(data) ? data : []);
    renderLb();
    renderAdminUsers();
  } catch (err) {
    console.error("Failed to fetch leaderboard:", err);
  }
}

// ===================== NAV =====================
const pageMeta={
  dashboard:{title:'Dashboard',sub:'Overview of your study activity'},
  submit:{title:'Submit Daily Proof',sub:'Upload screenshots for admin verification'},
  timer:{title:'Study Timer',sub:'Track your focused study sessions'},
  leaderboard:{title:'Leaderboard',sub:'Rankings & standings'},
  analytics:{title:'My Analytics',sub:'Deep dive into your performance'},
  'admin-verify':{title:'Verify Submissions',sub:'Review and assign student status'},
  'admin-users':{title:'Student Manager',sub:'Manage all enrolled students'},
};

function nav(page){
  if((page==='admin-verify'||page==='admin-users')&&S.user?.role!=='admin'){toast('Admin only','error');return;}
  if(page!=='timer' && S.timerState==='idle') document.body.classList.remove('focus-mode');
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
  document.getElementById('page-'+page).classList.add('active');
  const navEl=document.getElementById('nav-'+page);
  if(navEl) navEl.classList.add('active');
  const meta=pageMeta[page]||{title:page,sub:''};
  document.getElementById('topbarTitle').textContent=meta.title;
  document.getElementById('topbarSub').textContent=meta.sub;
  S.currentPage=page;
  if(page==='leaderboard'){fetchLeaderboard().then(()=>setTimeout(animateLbBars,80));}
  if(page==='analytics'){buildActGrid();}
  if(page==='admin-verify'){fetchSubmissions().then(renderAdminSubmissions);}
  if(page==='submit'){renderTodaySub();updateSubWindowBanner();}
}

// ===================== DASHBOARD =====================
function renderDashboard(){
  const u=S.user;
  if(!u||u.role==='admin') return;
  document.getElementById('dToday').textContent=fmtHours((u.totalHours||0)%8);
  document.getElementById('dStreak').textContent=(u.streak||0)+' days';
  document.getElementById('sbStreak').textContent='🔥 '+(u.streak||0);
  const myId=u._id||u.id;
  const students=(S.leaderboardData||[]);
  const sorted=[...students].sort((a,b)=>(b.totalHours||b.hrs||0)-(a.totalHours||a.hrs||0));
  const rank=sorted.findIndex(x=>String(x._id||x.id||x.userId)===String(myId))+1;
  document.getElementById('dRank').textContent=rank>0?'#'+rank:'#—';
  const todaySub=getTodaySub(myId);
  const statusEl=document.getElementById('dStatus');
  statusEl.innerHTML=todaySub?renderStatusBadge(todaySub.status):'<span class="status-badge s-pending">⏳ Pending</span>';
  const banner=document.getElementById('dashBanner');
  if(!todaySub||todaySub.status==='pending'){
    banner.innerHTML='<div class="deadline-banner active"><span style="font-size:18px">📸</span><div style="flex:1"><div style="font-weight:700;font-size:13.5px;color:var(--warning-dark)">Don\'t forget your daily proof submission!</div><div style="font-size:12.5px;color:var(--text2)">Submit between 6 PM – 7:30 PM with screenshots of your timer and questions solved.</div></div><button class="btn btn-sm" style="background:var(--warning);color:#fff;border:none;flex-shrink:0" onclick="nav(\'submit\')">Submit Now →</button></div>';
    document.getElementById('submitBadge').style.display='flex';
  } else {
    banner.innerHTML='<div class="deadline-banner done"><span style="font-size:18px">✅</span><div><div style="font-weight:700;font-size:13.5px;color:var(--success-dark)">Today\'s proof submitted successfully!</div><div style="font-size:12.5px;color:var(--text2)">Submitted at '+fmtTime(todaySub)+'  ·  Status: '+renderStatusBadge(todaySub.status)+'</div></div></div>';
    document.getElementById('submitBadge').style.display='none';
  }
  renderRecentSessions();
  renderSubHistory();
  updateMyStats();
}

function getTodaySub(uid){
  const today=new Date().toISOString().split('T')[0];
  return S.submissions.find(s=>{
    if (s.date !== today) return false;
    const subUid = s.userId?._id || s.userId;
    // GET /submission/my omits userId; list is already scoped to the logged-in student
    if (subUid == null) return true;
    return subUid===uid || subUid===String(uid);
  });
}

function renderStatusBadge(s){
  const map={completed:'s-completed',halfday:'s-halfday',leave:'s-leave',fine:'s-fine',pending:'s-pending'};
  const labels={completed:'✅ Completed',halfday:'🟡 Half Day',leave:'❌ Leave',fine:'🔴 Fine',pending:'⏳ Pending'};
  return `<span class="status-badge ${map[s]||'s-pending'}">${labels[s]||s}</span>`;
}

function renderRecentSessions(){
  const sessions=S.sessions.slice(0,5);
  if(!sessions.length){
    document.getElementById('recentSessions').innerHTML='<div style="color:var(--text3);font-size:13px;padding:20px 0;text-align:center">No sessions yet. <a style="color:var(--primary);cursor:pointer" onclick="nav(\'timer\')">Start studying →</a></div>';
    return;
  }
  document.getElementById('recentSessions').innerHTML=sessions.map(s=>`
    <div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--border)">
      <div style="width:34px;height:34px;border-radius:8px;background:var(--primary-light);display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0">${subjectEmoji(s.subject)}</div>
      <div style="flex:1"><div style="font-weight:600;font-size:13.5px">${s.subject}</div><div style="font-size:11.5px;color:var(--text3)">${fmtTimeAgo(s.endTime)}</div></div>
      <div style="font-family:var(--display);font-weight:600;font-size:14px;color:var(--text)">${fmtDur(s.duration)}</div>
    </div>
  `).join('');
}

function renderSubHistory(){
  const uid=S.user?._id||S.user?.id;
  const subs=S.submissions.filter(s=>{
    const subUid=s.userId?._id||s.userId;
    return subUid===uid||subUid===String(uid);
  }).sort((a,b)=>b.date.localeCompare(a.date)).slice(0,6);
  if(!subs.length){
    document.getElementById('subHistory').innerHTML='<div style="color:var(--text3);font-size:13px;padding:20px 0;text-align:center">No submissions yet</div>';
    return;
  }
  document.getElementById('subHistory').innerHTML=subs.map(s=>`
    <div style="display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid var(--border)">
      <div style="flex:1"><div style="font-weight:600;font-size:13px">${fmtDateShort(s.date)}</div><div style="font-size:11.5px;color:var(--text3)">${s.subject} · ${s.hours}h</div></div>
      ${renderStatusBadge(s.status)}
    </div>
  `).join('');
}

// ===================== SUBMIT PROOF =====================
function triggerUpload(id){ /* handled by input */ }

function handleFileUpload(input,previewId,zoneId){
  const file=input.files[0];
  if(!file) return;
  const key=input.id==='timerFile'?'timer':'quest';
  const reader=new FileReader();
  reader.onload=e=>{
    S.timerFiles[key]=e.target.result;
    const preview=document.getElementById(previewId);
    preview.src=e.target.result;
    preview.style.display='block';
    document.getElementById(zoneId).querySelector('[id$="UploadContent"]').style.display='none';
  };
  reader.readAsDataURL(file);
}

async function submitProof() {
  const timerB64 = S.timerFiles.timer;
  const questB64 = S.timerFiles.quest;
  if (!timerB64 || !questB64) { alert("Please upload both screenshots."); return; }
  const hours = parseFloat(document.getElementById("subHours").value);
  if (!hours || hours <= 0) { alert("Please enter valid hours studied."); return; }
  try {
    const formData = new FormData();
    formData.append("timerScreenshot", dataURLtoBlob(timerB64), "timer.jpg");
    formData.append("questionScreenshot", dataURLtoBlob(questB64), "questions.jpg");
    formData.append("subject", document.getElementById("subSubject").value);
    formData.append("hoursStudied", String(hours));
    formData.append("notes", document.getElementById("subNotes").value || "");
    const res = await fetch(`${API_URL}/submission/upload`, {
      method: "POST",
      headers: { ...authHeader() },
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) { alert(data.message || "Upload failed"); return; }
    toast("Submitted successfully ✅", "success");
    await fetchSubmissions();
    renderTodaySub();
    renderDashboard();
    updatePendingBadge();
  } catch (err) {
    console.error(err);
    alert("Upload error");
  }
}
// async function submitProof() {
//   const timerFile = document.getElementById("timerScreenshot").files[0];
//   const questionFile = document.getElementById("questionScreenshot").files[0];
//   const hours = document.getElementById("subHours").value;
//   const subject = document.getElementById("subSubject").value;
//   const notes = document.getElementById("subNotes").value;

//   if (!timerFile || !questionFile) {
//     alert("Please upload both screenshots");
//     return;
//   }

//   if (!hours || hours <= 0) {
//     alert("Enter valid hours");
//     return;
//   }

//   try {
//     const formData = new FormData();
//     formData.append("timerScreenshot", timerFile);
//     formData.append("questionScreenshot", questionFile);
//     formData.append("hoursStudied", hours);
//     formData.append("subject", subject);
//     formData.append("notes", notes);

//     const res = await fetch(`${API_URL}/submission/upload`, {
//       method: "POST",
//       headers: {
//         Authorization: `Bearer ${localStorage.getItem("token")}`
//       },
//       body: formData
//     });

//     const data = await res.json();

//     if (!res.ok) {
//       alert(data.message || "Upload failed ❌");
//       return;
//     }

//     alert("Submitted successfully ✅");

//     await fetchSubmissions();

//   } catch (err) {
//     console.error(err);
//     alert("Upload error ❌");
//   }
// }

function renderTodaySub(){
  if(!S.user||S.user.role==='admin') return;
  const uid=S.user._id||S.user.id;
  const sub=getTodaySub(uid);
  const el=document.getElementById('todaySubStatus');
  if(!sub){
    el.innerHTML='<div style="text-align:center;padding:16px 0"><div style="font-size:32px;margin-bottom:8px">📭</div><div style="font-size:13px;color:var(--text3)">Not submitted yet</div></div>';
  } else {
    el.innerHTML=`
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">${renderStatusBadge(sub.status)}<span style="font-size:12px;color:var(--text3)">${sub.verified?'Verified':'Awaiting review'}</span></div>
      <div style="font-size:12.5px;color:var(--text2)"><strong>Subject:</strong> ${sub.subject}</div>
      <div style="font-size:12.5px;color:var(--text2);margin-top:4px"><strong>Hours claimed:</strong> ${sub.hours}h</div>
      ${sub.adminNotes?`<div style="margin-top:10px;padding:10px;background:var(--bg);border-radius:var(--r);font-size:12.5px;color:var(--text2)"><strong>Admin note:</strong> ${sub.adminNotes}</div>`:''}
    `;
  }
  updateSubWindowBanner();
}

function updateSubWindowBanner(){
  const el=document.getElementById('subWindowBanner');
  if(!el) return;
  const now=new Date();
  const h=now.getHours(),m=now.getMinutes();
  const isWindow=(h===18&&m>=0)||(h===19&&m<=30);
  const isPast=(h>19)||(h===19&&m>30);
  const uid=S.user?._id||S.user?.id;
  const sub=getTodaySub(uid);
  if(sub&&sub.status!=='pending'){
    el.innerHTML=`<div class="deadline-banner done"><span>✅</span><div style="font-size:13px;color:var(--success-dark);font-weight:600">Proof verified — Status: ${renderStatusBadge(sub.status)}</div></div>`;
  } else if(sub){
    el.innerHTML=`<div class="deadline-banner done"><span>📤</span><div style="font-size:13px;color:var(--success-dark);font-weight:600">Submitted! Awaiting admin verification.</div></div>`;
  } else if(isWindow){
    el.innerHTML=`<div class="deadline-banner active"><span>⏰</span><div style="font-size:13px;color:var(--warning-dark);font-weight:600">Submission window is OPEN (closes 7:30 PM). Submit now!</div></div>`;
  } else if(isPast){
    el.innerHTML=`<div class="deadline-banner missed"><span>❌</span><div style="font-size:13px;color:var(--error-dark);font-weight:600">Submission window closed. You will receive a 🔴 Fine.</div></div>`;
  } else {
    el.innerHTML=`<div class="deadline-banner active"><span>📅</span><div style="font-size:13px;color:var(--warning-dark)">Submission window opens at <strong>6:00 PM</strong>. Prepare your screenshots.</div></div>`;
  }
}

function updateDeadlineBanner(){
  if(!S.user||S.user.role==='admin') return;
  const h=new Date().getHours();
  const el=document.getElementById('deadlineTag');
  if(h>=18&&h<20){ el.innerHTML='<span class="pill pill-amber">⏰ Submit before 7:30 PM</span>'; }
  else { el.innerHTML=''; }
}

// ===================== TIMER =====================
function pickSubject(el,subj){
  document.querySelectorAll('#subjectPicker .pill').forEach(p=>{p.className='pill pill-gray';p.style.cursor='pointer';p.style.padding='6px 14px';p.style.fontSize='13px';});
  el.className='pill pill-blue';
  S.currentSubject=subj;
  document.getElementById('timerSubLabel').textContent=subj.toUpperCase();
}

async function tStart(){
  if(S.timerState==='running') return;
  try {
    const res = await fetch(`${API_URL}/session/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeader() },
      body: JSON.stringify({ subject: S.currentSubject }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      toast(data.message || "Could not start session (try again or stop any active session)", "error");
      return;
    }
    S.activeSessionId = data.session?.id || null;
  } catch (e) {
    console.error(e);
    toast("Could not reach server to start session", "error");
    return;
  }
  S.timerState='running';
  S.timerStart=Date.now()-S.timerElapsed;
  S.timerInterval=setInterval(tickTimer,1000);
  document.getElementById('tStartBtn').style.display='none';
  document.getElementById('tPauseBtn').style.display='inline-flex';
  document.getElementById('tStopBtn').style.display='inline-flex';
  document.getElementById('timerDisp').className='timer-digits running';
  document.getElementById('tNote').textContent=S.currentSubject+' session in progress…';
  document.body.classList.add('focus-mode');
  toast('Session started! Stay focused.','info');
}

function tPause(){
  S.timerState='paused';
  S.timerElapsed=Date.now()-S.timerStart;
  clearInterval(S.timerInterval);
  document.getElementById('tPauseBtn').style.display='none';
  document.getElementById('tResumeBtn').style.display='inline-flex';
  document.getElementById('timerDisp').className='timer-digits paused';
  document.getElementById('tNote').textContent='Session paused';
}

function tResume(){
  S.timerState='running';
  S.timerStart=Date.now()-S.timerElapsed;
  S.timerInterval=setInterval(tickTimer,1000);
  document.getElementById('tResumeBtn').style.display='none';
  document.getElementById('tPauseBtn').style.display='inline-flex';
  document.getElementById('timerDisp').className='timer-digits running';
  document.getElementById('tNote').textContent=S.currentSubject+' session resumed…';
}

async function tStop(){
  const elapsed=S.timerState==='running'?Date.now()-S.timerStart:S.timerElapsed;
  clearInterval(S.timerInterval);
  const secs=Math.floor(elapsed/1000);
  try {
    const body = S.activeSessionId ? { sessionId: S.activeSessionId } : {};
    const res = await fetch(`${API_URL}/session/stop`, {
      method:'POST',
      headers:{'Content-Type':'application/json',...authHeader()},
      body: JSON.stringify(body),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.session?.duration != null) {
        S.sessions.unshift({
          subject: data.session.subject || S.currentSubject,
          duration: data.session.duration,
          endTime: data.session.endTime || new Date(),
        });
      } else {
        S.sessions.unshift({ subject: S.currentSubject, duration: secs, endTime: new Date() });
      }
    } else {
      S.sessions.unshift({ subject: S.currentSubject, duration: secs, endTime: new Date() });
    }
  } catch(e){
    console.error('Session save failed',e);
    S.sessions.unshift({subject:S.currentSubject,duration:secs,endTime:new Date()});
  }
  S.activeSessionId = null;
  if(S.user) S.user.totalHours=(S.user.totalHours||0)+secs/3600;
  S.timerState='idle';S.timerElapsed=0;S.timerStart=null;
  document.getElementById('timerDisp').textContent='00:00:00';
  document.getElementById('timerDisp').className='timer-digits';
  document.getElementById('tNote').textContent='Press Start to begin a study session';
  document.getElementById('tStartBtn').style.display='inline-flex';
  document.getElementById('tPauseBtn').style.display='none';
  document.getElementById('tResumeBtn').style.display='none';
  document.getElementById('tStopBtn').style.display='none';
  document.getElementById('timerRing').style.strokeDashoffset='728.97';
  document.body.classList.remove('focus-mode');
  renderTimerSessions();
  toast(`Session complete: ${fmtDur(secs)} of ${S.currentSubject}`,'success');
}

function tickTimer(){
  const el=Date.now()-S.timerStart;
  const s=Math.floor(el/1000);
  const h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=s%60;
  document.getElementById('timerDisp').textContent=pad(h)+':'+pad(m)+':'+pad(sec);
  const progress=Math.min(s/7200,1);
  document.getElementById('timerRing').style.strokeDashoffset=728.97*(1-progress);
}

function renderTimerSessions(){
  const el=document.getElementById('timerSessions');
  if(!S.sessions.length){el.innerHTML='<div style="color:var(--text3);font-size:13px;padding:16px 0;text-align:center">No sessions yet today</div>';return;}
  el.innerHTML=S.sessions.slice(0,4).map(s=>`
    <div style="display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--border)">
      <span style="font-size:16px">${subjectEmoji(s.subject)}</span>
      <div style="flex:1;font-weight:500;font-size:13.5px">${s.subject}</div>
      <span style="font-family:var(--display);font-weight:600;font-size:14px;color:var(--text)">${fmtDur(s.duration)}</span>
    </div>
  `).join('');
}

// ===================== LEADERBOARD =====================
function lbSwitch(el,mode){
  document.querySelectorAll('.tabs .tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  S.lbMode=mode;
  fetchLeaderboard().then(()=>setTimeout(animateLbBars,80));
}

function getLbData(){
  return S.leaderboardData||[];
}

function renderLb(){
  const data=getLbData();
  if(!data.length){
    const el=document.getElementById('lbList');
    if(el) el.innerHTML='<div style="color:var(--text3);font-size:13px;padding:20px 0;text-align:center">Loading leaderboard…</div>';
    return;
  }
  const max=data[0]?.hrs||data[0]?.totalHours||1;
  const rankEmoji=(i)=>i===0?'🥇':i===1?'🥈':i===2?'🥉':'';
  const myId=S.user?._id||S.user?.id;
  document.getElementById('lbList').innerHTML=data.map((u,i)=>{
    const uid=u._id||u.id||u.userId;
    const avatar=u.avatar||(u.name?u.name[0].toUpperCase():'?');
    const color=u.color||'#3B82F6';
    return `
      <div class="lb-row ${uid===myId?'you':''}">
        <div class="lb-rank">${rankEmoji(i)||(i+1)}</div>
        <div class="lb-av" style="background:${color}">${avatar}</div>
        <div class="lb-info">
          <div class="lb-name">${u.name}${uid===myId?' (You)':''}</div>
          <div class="lb-meta">🔥 ${u.streak||0}d · ${u.completed||0} completed</div>
        </div>
        <div class="lb-bar-wrap"><div class="lb-bar-fill" style="width:0%" data-w="${Math.round((u.hrs||u.totalHours||0)/max*100)}%"></div></div>
        <div class="lb-hrs">${fmtHours(u.hrs||u.totalHours||0)}</div>
      </div>
    `;
  }).join('');
  updateMyStats(data);
}

function animateLbBars(){
  document.querySelectorAll('.lb-bar-fill').forEach(el=>{setTimeout(()=>{el.style.width=el.dataset.w;},50);});
}

function updateMyStats(data){
  if(!S.user||S.user.role==='admin') return;
  const lb=data||getLbData();
  const myId=S.user._id||S.user.id;
  const rank=lb.findIndex(u=>String(u._id||u.id||u.userId)===String(myId))+1;
  document.getElementById('myRankBig').textContent=rank>0?'#'+rank:'#—';
  document.getElementById('myRankSub').textContent='out of '+lb.length+' students';
  document.getElementById('myTotalHrs').textContent=fmtHours(S.user.totalHours||0);
  document.getElementById('myStreakLb').textContent=(S.user.streak||0)+' days';
  document.getElementById('myCompleted').textContent=S.user.totalCompleted ?? S.user.completed ?? 0;
  document.getElementById('myFines').textContent=S.user.totalFines ?? S.user.fines ?? 0;
  document.getElementById('dRank').textContent=rank>0?'#'+rank:'#—';
}

// ===================== ANALYTICS =====================
function renderAnalytics(){
  if(!S.user||S.user.role==='admin') return;
  const uid=S.user._id||S.user.id;
  const subs=S.submissions.filter(s=>{
    const subUid=s.userId?._id||s.userId;
    return (subUid===uid||subUid===String(uid))&&s.status!=='pending';
  });
  const total=subs.length;
  const completed=subs.filter(s=>s.status==='completed').length;
  const fines=subs.filter(s=>s.status==='fine').length;
  const avgHrs=total>0?(subs.reduce((a,s)=>a+s.hours,0)/total).toFixed(1):0;
  const goalHit=total>0?Math.round(subs.filter(s=>s.hours>=4).length/total*100):0;
  document.getElementById('aConsist').textContent=total>0?Math.round(completed/total*100)+'%':'—%';
  document.getElementById('aAvgHrs').textContent=avgHrs+'h';
  document.getElementById('aGoal').textContent=goalHit+'%';
  document.getElementById('aFines').textContent=fines;
}

function buildActGrid(){
  const grid=document.getElementById('actGrid');
  const weeks=13;
  let html='';
  for(let w=0;w<weeks;w++){
    html+='<div class="act-col">';
    for(let d=0;d<7;d++){
      const r=Math.random();
      let cls='';
      if(r>0.75) cls='act-5';
      else if(r>0.55) cls='act-4';
      else if(r>0.4) cls='act-3';
      else if(r>0.25) cls='act-1';
      html+=`<div class="act-cell ${cls}"></div>`;
    }
    html+='</div>';
  }
  grid.innerHTML=html;
}

// ===================== ADMIN =====================
function updatePendingBadge(){
  const pending=S.submissions.filter(s=>s.status==='pending').length;
  document.getElementById('pendingBadge').textContent=pending;
  document.getElementById('pendingCount').textContent=pending+' pending';
}

function adminFilter(el,mode){
  document.querySelectorAll('.tabs .tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  S.adminFilter=mode;
  renderAdminSubmissions();
}

function getStudentFromSub(sub){
  const allUsers=S.leaderboardData||[];
  const subUid=sub.userId?._id||sub.userId;
  // submissions may have userId populated as object
  if(sub.userId && typeof sub.userId === 'object') return sub.userId;
  return allUsers.find(u=>(u._id||u.id)===subUid)||{name:'Unknown',avatar:'?',color:'#94A3B8'};
}

function renderAdminSubmissions(){
  let subs=S.submissions;
  if(S.adminFilter==='pending') subs=subs.filter(s=>s.status==='pending');
  if(S.adminFilter==='verified') subs=subs.filter(s=>s.verified);
  subs=[...subs].sort((a,b)=>b.date.localeCompare(a.date));
  const grid=document.getElementById('submissionGrid');
  const noEl=document.getElementById('noSubmissions');
  if(!subs.length){grid.innerHTML='';noEl.style.display='block';return;}
  noEl.style.display='none';
  grid.innerHTML=subs.map(sub=>{
    const student=getStudentFromSub(sub);
    const avatar=student.avatar||(student.name?student.name[0].toUpperCase():'?');
    const color=student.color||'#94A3B8';
    const subId=sub._id||sub.id;
    return `
      <div class="submission-card">
        <div class="sub-header">
          <div style="display:flex;align-items:center;gap:10px">
            <div style="width:32px;height:32px;border-radius:8px;background:${color};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#fff">${avatar}</div>
            <div>
              <div style="font-weight:600;font-size:13.5px;color:var(--text)">${student.name}</div>
              <div style="font-size:11.5px;color:var(--text3)">${fmtDateShort(sub.date)}</div>
            </div>
          </div>
          ${renderStatusBadge(sub.status)}
        </div>
        <div class="sub-body">
          <div style="display:flex;gap:8px;margin-bottom:10px">
            <span class="pill pill-blue">${subjectEmoji(sub.subject)} ${sub.subject}</span>
            <span class="pill pill-gray">⏱ ${sub.hours}h</span>
          </div>
          <div class="sub-screenshots">
            ${sub.timerScreenshot
              ?`<div class="sub-ss" onclick="openLightbox('${sub.timerScreenshot}')"><img src="${sub.timerScreenshot}"><div class="ss-label">Timer</div></div>`
              :`<div class="sub-ss" style="font-size:12px;color:var(--text3);flex-direction:column;gap:4px"><span style="font-size:24px">⏱</span><span>No screenshot</span></div>`
            }
            ${sub.questScreenshot
              ?`<div class="sub-ss" onclick="openLightbox('${sub.questScreenshot}')"><img src="${sub.questScreenshot}"><div class="ss-label">Questions</div></div>`
              :`<div class="sub-ss" style="font-size:12px;color:var(--text3);flex-direction:column;gap:4px"><span style="font-size:24px">📝</span><span>No screenshot</span></div>`
            }
          </div>
          ${sub.notes?`<div style="font-size:12.5px;color:var(--text2);padding:8px;background:var(--bg);border-radius:var(--r);margin-bottom:10px;line-height:1.5">"${sub.notes.slice(0,100)}${sub.notes.length>100?'…':''}"</div>`:''}
          <div style="display:flex;gap:8px">
            <button class="btn btn-primary btn-sm w100" style="justify-content:center" onclick="openVerifyModal('${subId}')">
              ${sub.verified?'✏️ Update Status':'✓ Verify'}
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

let currentVerifyId=null;
function openVerifyModal(subId){
  const sub=S.submissions.find(s=>String(s._id||s.id)===String(subId));
  if(!sub) return;
  currentVerifyId=subId;
  S.verifyStatus=sub.status==='pending'?'completed':sub.status;
  const student=getStudentFromSub(sub);
  document.getElementById('vModalName').textContent=student.name;
  document.getElementById('vModalDate').textContent='Submission for '+fmtDateShort(sub.date);
  document.getElementById('vModalNotes').textContent=sub.notes||'No notes provided';
  document.getElementById('vModalSubject').textContent=sub.subject;
  document.getElementById('vModalHours').textContent=sub.hours+'h claimed';
  document.getElementById('vAdminNotes').value=sub.adminNotes||'';
  const ssHtml=[
    sub.timerScreenshot?`<div class="sub-ss" onclick="openLightbox('${sub.timerScreenshot}')"><img src="${sub.timerScreenshot}"><div class="ss-label">Timer Screenshot</div></div>`
    :`<div class="sub-ss"><span style="font-size:32px">⏱</span><div class="ss-label">No Timer Screenshot</div></div>`,
    sub.questScreenshot?`<div class="sub-ss" onclick="openLightbox('${sub.questScreenshot}')"><img src="${sub.questScreenshot}"><div class="ss-label">Questions Screenshot</div></div>`
    :`<div class="sub-ss"><span style="font-size:32px">📝</span><div class="ss-label">No Questions Screenshot</div></div>`
  ];
  document.getElementById('vModalScreenshots').innerHTML=ssHtml.join('');
  document.querySelectorAll('.status-opt').forEach(el=>el.classList.remove('selected'));
  const statusMap={completed:'.so-completed',halfday:'.so-halfday',leave:'.so-leave',fine:'.so-fine'};
  const sel=document.querySelector(statusMap[S.verifyStatus]||'.so-completed');
  if(sel) sel.classList.add('selected');
  document.getElementById('verifyModal').classList.add('open');
}

function closeVerifyModal(){document.getElementById('verifyModal').classList.remove('open');}

function selectStatus(el,status){
  document.querySelectorAll('.status-opt').forEach(e=>e.classList.remove('selected'));
  el.classList.add('selected');
  S.verifyStatus=status;
}

async function saveVerification(){
  const sub=S.submissions.find(s=>String(s._id||s.id)===String(currentVerifyId));
  if(!sub){closeVerifyModal();return;}
  const adminNotes=document.getElementById('vAdminNotes').value;
  try {
    const subId=sub._id||sub.id;
    const res=await fetch(`${API_URL}/submission/verify`, {
      method:'POST',
      headers:{'Content-Type':'application/json',...authHeader()},
      body:JSON.stringify({ submissionId: subId, status: S.verifyStatus, adminNotes })
    });
    if(!res.ok){
      const err=await res.json();
      toast(err.message||'Verification failed','error');
      return;
    }
  } catch(err){
    toast('Network error during verification','error');
    return;
  }
  sub.status=S.verifyStatus;
  sub.adminNotes=adminNotes;
  sub.verified=true;
  sub.verifiedAt=new Date().toISOString();
  const student=getStudentFromSub(sub);
  closeVerifyModal();
  updatePendingBadge();
  renderAdminSubmissions();
  renderLb();
  renderDashboard();
  renderTodaySub();
  renderAdminUsers();
  toast(`Status set to "${S.verifyStatus}" for ${student?.name?.split(' ')[0]||'student'}`,'success');
}

function renderAdminUsers(){
  const students=(S.leaderboardData||[]).filter(u=>u.role==='student'||!u.role).sort((a,b)=>(b.totalHours||b.hrs||0)-(a.totalHours||a.hrs||0));
  if(!students.length){
    document.getElementById('adminUsersTbody').innerHTML='<tr><td colspan="8" style="text-align:center;color:var(--text3);padding:20px">Loading students…</td></tr>';
    return;
  }
  document.getElementById('adminUsersTbody').innerHTML=students.map((u)=>{
    const uid=u._id||u.id||u.userId;
    const avatar=u.avatar||(u.name?u.name[0].toUpperCase():'?');
    const color=u.color||'#3B82F6';
    const lastSub=S.submissions.filter(s=>{
      const subUid=s.userId?._id||s.userId;
      return subUid===uid||subUid===String(uid);
    }).sort((a,b)=>b.date.localeCompare(a.date))[0];
    return `<tr>
      <td><div style="display:flex;align-items:center;gap:10px"><div style="width:32px;height:32px;border-radius:8px;background:${color};display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;color:#fff">${avatar}</div><span style="font-weight:600;color:var(--text)">${u.name}</span></div></td>
      <td style="font-size:13px">${u.email||'—'}</td>
      <td style="font-family:var(--display);font-weight:600">${fmtHours(u.totalHours||u.hrs||0)}</td>
      <td><span style="color:var(--warning);font-weight:600">🔥 ${u.streak||0}d</span></td>
      <td><span style="color:var(--success-dark);font-weight:600">${u.totalCompleted ?? u.completed ?? u.completedCount ?? 0}</span></td>
      <td><span style="color:var(--error);font-weight:600">${u.totalFines ?? u.fines ?? 0}</span></td>
      <td>${lastSub?renderStatusBadge(lastSub.status):'<span class="pill pill-gray">No data</span>'}</td>
      <td><button class="btn btn-danger btn-sm" onclick="removeUser('${uid}')">Remove</button></td>
    </tr>`;
  }).join('');
}

function filterStudents(q){
  const rows=document.querySelectorAll('#adminUsersTbody tr');
  rows.forEach(r=>{r.style.display=r.textContent.toLowerCase().includes(q.toLowerCase())?'':'none';});
}

async function removeUser(id){
  if(!confirm('Remove this student?')) return;
  try {
    const res=await fetch(`${API_URL}/admin/user/${id}`,{method:'DELETE',headers:{...authHeader()}});
    if(!res.ok){ const err=await res.json(); toast(err.message||'Failed to remove student','error'); return; }
  } catch(err){ toast('Network error','error'); return; }
  S.leaderboardData=S.leaderboardData.filter(u=>(u._id||u.id)!==id);
  S.submissions=S.submissions.filter(s=>{const uid=s.userId?._id||s.userId; return uid!==id;});
  renderAdminUsers();
  renderLb();
  toast('Student removed','info');
}

// ===================== CHARTS =====================
function initCharts(){
  const tc='#94A3B8',gc='rgba(226,232,240,0.8)';
  const wCtx=document.getElementById('weekChart').getContext('2d');
  S.charts.week=new Chart(wCtx,{
    type:'bar',
    data:{
      labels:['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],
      datasets:[{data:[3.5,5.2,4.1,6.8,5.5,7.2,4.5],backgroundColor:'rgba(59,130,246,0.7)',borderRadius:6,borderSkipped:false}]
    },
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
      scales:{x:{grid:{display:false},ticks:{color:tc}},y:{grid:{color:gc},ticks:{color:tc,callback:v=>v+'h'},border:{dash:[3,3]}}}}
  });
  const sCtx=document.getElementById('subjectChart').getContext('2d');
  S.charts.subj=new Chart(sCtx,{
    type:'doughnut',
    data:{labels:['Math','Physics','Coding','Chem','Bio'],datasets:[{data:[35,22,18,15,10],backgroundColor:['#3B82F6','#8B5CF6','#22C55E','#F59E0B','#EF4444'],borderColor:'#fff',borderWidth:3,hoverOffset:6}]},
    options:{responsive:true,maintainAspectRatio:false,cutout:'70%',plugins:{legend:{position:'right',labels:{color:tc,boxWidth:10,padding:10}}}}
  });
  const tCtx=document.getElementById('trendChart').getContext('2d');
  S.charts.trend=new Chart(tCtx,{
    type:'line',
    data:{labels:Array.from({length:30},(_,i)=>i===29?'Today':`${30-i}d`),datasets:[{data:Array.from({length:30},()=>+(Math.random()*7+1).toFixed(1)),borderColor:'#3B82F6',backgroundColor:'rgba(59,130,246,0.06)',fill:true,tension:0.4,pointRadius:0,borderWidth:2}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
      scales:{x:{grid:{display:false},ticks:{color:tc,maxTicksLimit:6}},y:{grid:{color:gc},ticks:{color:tc,callback:v=>v+'h'},border:{dash:[3,3]}}}}
  });
  const stCtx=document.getElementById('statusChart').getContext('2d');
  const uid=S.user?._id||S.user?.id;
  const subs=S.submissions.filter(s=>{const subUid=s.userId?._id||s.userId; return (subUid===uid||subUid===String(uid))&&s.status!=='pending';});
  S.charts.status=new Chart(stCtx,{
    type:'bar',
    data:{
      labels:['✅ Completed','🟡 Half Day','❌ Leave','🔴 Fine'],
      datasets:[{data:[subs.filter(s=>s.status==='completed').length,subs.filter(s=>s.status==='halfday').length,subs.filter(s=>s.status==='leave').length,subs.filter(s=>s.status==='fine').length],backgroundColor:['rgba(34,197,94,0.8)','rgba(245,158,11,0.8)','rgba(148,163,184,0.8)','rgba(239,68,68,0.8)'],borderRadius:8,borderSkipped:false}]
    },
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
      scales:{x:{grid:{display:false},ticks:{color:tc}},y:{grid:{color:gc},ticks:{color:tc,stepSize:1},border:{dash:[3,3]}}}}
  });
}

// ===================== LIGHTBOX =====================
function openLightbox(src){
  document.getElementById('lightboxImg').src=src;
  document.getElementById('lightbox').classList.add('open');
}

// ===================== UTILS =====================
function fmtDur(s){const h=Math.floor(s/3600),m=Math.floor((s%3600)/60);if(h>0)return h+'h '+m+'m';return m+'m '+Math.floor(s%60)+'s';}
function fmtHours(h){if(h>=100)return Math.round(h)+'h';if(h>10)return h.toFixed(1)+'h';const hrs=Math.floor(h),mins=Math.round((h-hrs)*60);if(hrs>0)return hrs+'h '+mins+'m';return mins+'m';}
function fmtDateShort(d){if(!d)return '';const dt=new Date(d);return dt.toLocaleDateString('en-IN',{day:'numeric',month:'short'});}
function fmtTimeAgo(d){if(!d)return '';const diff=Math.floor((Date.now()-new Date(d))/3600000);if(diff<1)return 'Just now';if(diff<24)return diff+'h ago';return Math.floor(diff/24)+'d ago';}
function fmtTime(sub){if(!sub?.submittedAt)return '';return new Date(sub.submittedAt).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'});}
function pad(n){return String(n).padStart(2,'0');}
function subjectEmoji(s){const m={Mathematics:'📐',Physics:'⚛️',Chemistry:'🧪',Programming:'💻',Biology:'🔬',History:'📜',Literature:'📚',Economics:'💹'};return m[s]||'📖';}

function toast(msg,type='info'){
  const el=document.createElement('div');
  el.className=`toast toast-${type}`;
  const icons={success:'✓',error:'✕',info:'ℹ',warning:'⚠'};
  const colors={success:'var(--success)',error:'var(--error)',info:'var(--primary)',warning:'var(--warning)'};
  el.innerHTML=`<span style="font-size:15px;color:${colors[type]};font-weight:700">${icons[type]}</span><span>${msg}</span>`;
  document.getElementById('toast').appendChild(el);
  setTimeout(()=>el.style.opacity='0',2800);
  setTimeout(()=>el.remove(),3100);
}

// ===================== INIT =====================
document.addEventListener('keydown',e=>{
  if(e.key==='Enter'){
    if(document.getElementById('loginView').style.display!=='none') doLogin();
    else if(document.getElementById('registerView').style.display!=='none') doRegister();
  }
});

(async ()=>{
  const days=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const now=new Date();
  const h=now.getHours();
  const greet=h<12?'good morning':h<17?'good afternoon':'good evening';
  document.getElementById('topbarSub').textContent=`${days[now.getDay()]}, ${greet}!`;
  const token=localStorage.getItem('token');
  if(token){
    try{
      const userRes=await fetch(`${API_URL}/auth/me`,{headers:{Authorization:`Bearer ${token}`}});
      if(userRes.ok){
        const userData=await userRes.json();
        await loginUser(userData.user);
      } else {
        localStorage.removeItem('token');
      }
    } catch(err){
      console.warn('Session restore failed:',err);
    }
  }
})();