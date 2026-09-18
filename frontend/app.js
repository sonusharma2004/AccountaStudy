// ===================== STATE =====================
const API_URL = (location.hostname === "localhost" || location.hostname === "127.0.0.1")
  ? "http://localhost:5001/api"
  : "https://accountability-api-five.vercel.app/api";
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

// ===================== THEME =====================
// The <head> script already applied the theme; this only keeps the button,
// the charts and the browser UI in sync once the page is interactive.

function currentTheme(){
  return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
}

/** Read a CSS token so canvas-drawn charts match the stylesheet. */
function themeToken(name){
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function applyTheme(theme, {persist = true} = {}){
  const dark = theme === 'dark';
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  if(persist){
    try{ localStorage.setItem('theme', dark ? 'dark' : 'light'); }catch(e){}
  }
  // Show the icon for the theme you would switch *to*, the usual convention.
  // Both the topbar and the login screen carry a toggle.
  ['themeIconSun','themeIconSunAuth'].forEach(id=>{
    const el = document.getElementById(id);
    if(el) el.style.display = dark ? 'none' : '';
  });
  ['themeIconMoon','themeIconMoonAuth'].forEach(id=>{
    const el = document.getElementById(id);
    if(el) el.style.display = dark ? '' : 'none';
  });
  const btn = document.getElementById('themeBtn');
  if(btn) btn.title = dark ? 'Switch to light theme' : 'Switch to dark theme';
  // Chart.js paints to a canvas, so it cannot inherit the new tokens.
  if(S.charts && Object.keys(S.charts).length) initCharts();
}

function toggleTheme(){
  applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
}

function initTheme(){
  applyTheme(currentTheme(), {persist: false});
  // Follow the OS only while the user has not made a choice of their own.
  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  const onSystemChange = e => {
    let saved = null;
    try{ saved = localStorage.getItem('theme'); }catch(err){}
    if(!saved) applyTheme(e.matches ? 'dark' : 'light', {persist: false});
  };
  if(mq.addEventListener) mq.addEventListener('change', onSystemChange);
  else if(mq.addListener) mq.addListener(onSystemChange);
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
  adminUsers: [],
  pendingUsers: [],
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
    const res = await fetchWithTimeout(`${API_URL}/auth/login`, {
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
    alert(err.name === "AbortError" ? backendUnavailableMessage() : "Error connecting to server");
  }
}

let regStudentType = 'fulltime';
function setRegType(type){
  regStudentType = type;
  const ft = document.getElementById('regTypeFulltime');
  const it = document.getElementById('regTypeIntern');
  if(type==='fulltime'){
    ft.style.border='2px solid var(--primary)'; ft.style.background='var(--primary-light)';
    it.style.border='2px solid var(--border)'; it.style.background='var(--bg)';
  } else {
    it.style.border='2px solid var(--primary)'; it.style.background='var(--primary-light)';
    ft.style.border='2px solid var(--border)'; ft.style.background='var(--bg)';
  }
}

async function doRegister() {
  const name = document.getElementById("regName").value;
  const email = document.getElementById("regEmail").value;
  const password = document.getElementById("regPass").value;
  const joinCode = (document.getElementById("regJoinCode")?.value || "").trim().toUpperCase();
  try {
    const res = await fetch(`${API_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password, studentType: regStudentType, joinCode })
    });
    const data = await res.json();
    if (!res.ok) { alert(data.message || "Register failed"); return; }
    alert(
      data.message ||
      "Registration received. Your admin will approve your account before you can log in."
    );
    switchView('login');
  } catch (err) {
    alert("Server error");
  }
}

// Only ask for a join code when the server is actually enforcing one.
async function initSignupMode() {
  try {
    const res = await fetchWithTimeout(`${API_URL}/auth/signup-info`);
    if (!res.ok) return;
    const data = await res.json();
    const group = document.getElementById("joinCodeGroup");
    if (group) group.style.display = data.joinCodeRequired ? "" : "none";
  } catch {
    // Offline or backend asleep — leave the field hidden; the API still rejects
    // a missing code, so nobody slips through.
  }
}

// ===================== PROFILE DRAWER =====================
function openProfileDrawer(){
  const u = S.user; if(!u) return;
  const avatar = u.avatar || (u.name ? u.name[0].toUpperCase() : '?');
  const color = u.color || 'var(--fill-primary)';
  document.getElementById('pdAvatar').textContent = avatar;
  document.getElementById('pdAvatar').style.background = color;
  document.getElementById('pdName').textContent = u.name || '—';
  document.getElementById('pdRole').textContent = u.role === 'admin' ? '⚡ Administrator' : '🎓 Student';
  document.getElementById('pdEmail').textContent = u.email || '—';
  const type = u.studentType || 'fulltime';
  document.getElementById('pdType').innerHTML = type === 'intern' ? '💼 Intern' : '🎓 Full-time Aspirant';
  const joined = u.createdAt ? new Date(u.createdAt).toLocaleDateString('en-IN', {day:'numeric', month:'long', year:'numeric'}) : '—';
  document.getElementById('pdJoined').textContent = joined;
  document.getElementById('pdStreak').textContent = u.streak || 0;
  document.getElementById('pdHours').textContent = fmtHours(u.totalStudyHours || u.totalHours || 0);
  document.getElementById('profileDrawer').style.display = 'block';
}

function closeProfileDrawer(){
  document.getElementById('profileDrawer').style.display = 'none';
}

function doLogout(){
  if(!confirm('Are you sure you want to logout?')) return;
  localStorage.removeItem('token');
  S.user = null;
  closeProfileDrawer();
  document.getElementById('app').style.display = 'none';
  document.getElementById('authScreen').style.display = 'flex';
  switchView('login');
  toast('Logged out successfully', 'success');
}

function authHeader() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Fetch with timeout — avoids login hanging forever when the API is unreachable. */
async function fetchWithTimeout(url, options = {}, ms = 30000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    return await fetch(url, { ...options, signal: ctrl.signal });
  } finally {
    clearTimeout(timer);
  }
}

function backendUnavailableMessage() {
  return (
    "Backend server is not responding.\n\n" +
    "Fix:\n" +
    `1. Open ${API_ORIGIN}/api/health in a new tab\n` +
    "2. Check that it reports \"database\": \"connected\"\n" +
    "3. Check your internet connection, then try login again"
  );
}

async function refreshUserProfile(){
  try {
    const res=await fetch(`${API_URL}/auth/me`,{headers:authHeader()});
    if(!res.ok) return;
    const data=await res.json();
    const u=data.user||data.data||data;
    if(u&&(u._id||u.id)){ S.user={...S.user,...u}; renderDashboard(); renderSubmitAllowance(); }
  } catch(e){ /* silent */ }
}

async function loginUser(user){
  S.user=user;
  document.getElementById('authScreen').style.display='none';
  document.getElementById('app').style.display='flex';
  const avatar = user.avatar || (user.name ? user.name[0].toUpperCase() : '?');
  const color = user.color || 'var(--fill-primary)';
  document.getElementById('sbAvatar').textContent=avatar;
  document.getElementById('sbAvatar').style.background=color;
  document.getElementById('sbName').textContent=user.name;
  document.getElementById('sbRole').textContent=user.role==='admin'?'⚡ Administrator':'🎓 Student';
  document.getElementById('sbStreak').textContent='🔥 '+(user.streak||0);
  if(user.role==='admin'){
    document.getElementById('navGroupAdmin').style.display='';
    document.getElementById('nav-admin-verify').style.display='flex';
    document.getElementById('nav-admin-register').style.display='flex';
    document.getElementById('nav-admin-users').style.display='flex';
    document.getElementById('submitBtn').style.display='none';
    document.getElementById('nav-submit').style.display='none';
    document.getElementById('nav-my-register').style.display='none';
    document.getElementById('nav-timer').style.display='none';
    document.getElementById('nav-analytics').style.display='none';
  }
  await Promise.all([fetchSubmissions(), fetchSessions(), fetchSubmitGate()]);
  fetchLeaderboard();
  if(user.role==='admin') fetchAdminUsers().then(()=>{renderPendingApprovals();renderAdminUsers();});
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
  // An admin's day starts with the submissions waiting to be reviewed.
  nav(user.role==='admin' ? 'admin-verify' : 'dashboard');
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
  'admin-register':{title:'Monthly Register',sub:'Every student, every day, at a glance'},
  'my-register':{title:'My Register',sub:'Your attendance and deposit for the month'},
};

// Pages that only make sense for someone who studies. An admin has no sessions
// or submissions of their own, so these render empty for them.
const STUDENT_ONLY_PAGES = ['submit','timer','analytics','my-register'];
const ADMIN_ONLY_PAGES = ['admin-verify','admin-users','admin-register'];

function nav(page){
  const isAdmin = S.user?.role === 'admin';
  if(ADMIN_ONLY_PAGES.includes(page) && !isAdmin){toast('Admin only','error');return;}
  if(STUDENT_ONLY_PAGES.includes(page) && isAdmin){ page='admin-verify'; }
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
  if(page==='analytics'){buildActGrid();initCharts();}
  if(page==='admin-verify'){fetchSubmissions().then(renderAdminSubmissions);}
  if(page==='admin-users'){fetchAdminUsers().then(()=>{renderPendingApprovals();renderAdminUsers();});}
  if(page==='admin-register'){loadRegister();}
  if(page==='my-register'){loadMyRegister();}
  if(page==='dashboard'){renderDashboard();}
  if(page==='submit'){S.forceFormOpen=false;renderTodaySub();renderSubmitAllowance();refreshSubmitPage();}
  else {stopGateTicker();}
}

// ===================== DASHBOARD =====================
// The API files every date against the student's own calendar day (IST), so the
// browser has to use local date parts too. toISOString() would give UTC and be
// a day behind for anything submitted after midnight.
function localDateStr(value){
  const d = value ? new Date(value) : new Date();
  if(Number.isNaN(d.getTime())) return '';
  const pad = n => String(n).padStart(2,'0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
}

function todayStr(){ return localDateStr(); }

function getTodayStudySeconds(){
  const today = todayStr();
  return (S.sessions||[]).filter(s=>{
    const d = s.date || localDateStr(s.startTime||s.endTime||Date.now());
    return d === today;
  }).reduce((a,s)=>a+(s.duration||0), 0);
}

// The admin dashboard answers "what needs me right now?", not "how did I do?".
async function renderAdminDashboard(){
  if(S.user?.role!=='admin') return;
  document.getElementById('adminDash').style.display='';
  document.getElementById('studentDash').style.display='none';
  const banner=document.getElementById('dashBanner');
  if(banner) banner.innerHTML='';

  try{
    const res=await fetch(`${API_URL}/admin/stats`,{headers:{...authHeader()}});
    if(!res.ok) return;
    const s=(await res.json()).stats||{};

    document.getElementById('aSubmitted').textContent=s.todaySubmissions??0;
    document.getElementById('aSubmittedSub').textContent=`of ${s.totalStudents??0} students`;
    document.getElementById('aPending').textContent=s.pendingVerifications??0;
    document.getElementById('aMissing').textContent=s.notSubmittedToday??0;
    document.getElementById('aDeposit').textContent=`₹${s.depositHeld??0}`;
    document.getElementById('aFines').textContent=
      s.finesThisMonth ? `${s.finesThisMonth} fine${s.finesThisMonth>1?'s':''} this month` : 'No fines this month';

    const today=s.today||{};
    const order=['completed','gt','halfday','leave','emergency','fine','pending'];
    const shown=order.filter(k=>today[k]>0);
    document.getElementById('aBreakdown').innerHTML = shown.length
      ? shown.map(k=>{
          const m=REG_STATUS[k];
          return `<div class="cal-count-row">
            <span style="display:flex;align-items:center;gap:8px"><span class="rg-legend-swatch" style="background:${m.swatch}"></span>${m.full}</span>
            <strong>${today[k]}</strong></div>`;
        }).join('')
      : '<div style="color:var(--text3);font-size:13px;text-align:center;padding:16px 0">Nothing submitted yet today.</div>';
  }catch(err){
    console.error('Admin stats failed:',err);
  }

  // The roster endpoint already reports each student's status for today.
  if(!S.adminUsers?.length) await fetchAdminUsers();
  const missing=(S.adminUsers||[]).filter(u=>!u.todayStatus?.status);
  document.getElementById('aMissingCount').textContent=missing.length;
  document.getElementById('aMissingList').innerHTML = missing.length
    ? missing.map(u=>`<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)">
        <div style="width:28px;height:28px;border-radius:7px;background:var(--fill-primary);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:var(--on-fill)">${u.avatar||'?'}</div>
        <div style="flex:1;min-width:0">
          <div style="font-weight:600;font-size:13px;color:var(--text)">${u.name}</div>
          <div style="font-size:11.5px;color:var(--text3);word-break:break-all">${u.email||''}</div>
        </div></div>`).join('')
    : '<div style="color:var(--success-dark);font-size:13px;text-align:center;padding:16px 0">Everyone has submitted. 🎉</div>';
}

function renderDashboard(){
  const u=S.user;
  if(u?.role==='admin'){ renderAdminDashboard(); return; }
  const sd=document.getElementById('studentDash');
  const ad=document.getElementById('adminDash');
  if(sd) sd.style.display='';
  if(ad) ad.style.display='none';
  if(!u) return;
  const todaySecs = getTodayStudySeconds();
  document.getElementById('dToday').textContent = todaySecs > 0 ? fmtDur(todaySecs) : '0m';
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
  const lr=u.leavesRemaining??3; const hr=u.halfDaysRemaining??3;
  const dlEl=document.getElementById('dashLeavesLeft'); if(dlEl) dlEl.textContent=lr;
  const dhEl=document.getElementById('dashHalfLeft'); if(dhEl) dhEl.textContent=hr;
  const banner=document.getElementById('dashBanner');
  if(!todaySub||todaySub.status==='pending'){
    const w=S.gate?.window;
    const when=w ? `Submit between ${w.opensAt} and ${w.closesAt}` : 'Submit before the deadline';
    banner.innerHTML=`<div class="deadline-banner active"><span style="font-size:18px">📸</span><div style="flex:1"><div style="font-weight:700;font-size:13.5px;color:var(--warning-dark)">Don't forget your daily proof submission!</div><div style="font-size:12.5px;color:var(--text2)">${when} with screenshots of your timer and questions solved.</div></div><button class="btn btn-sm" style="background:var(--fill-warning);color:var(--on-fill);border:none;flex-shrink:0" onclick="nav('submit')">Submit Now →</button></div>`;
    document.getElementById('submitBadge').style.display='flex';
  } else {
    banner.innerHTML='<div class="deadline-banner done"><span style="font-size:18px">✅</span><div><div style="font-weight:700;font-size:13.5px;color:var(--success-dark)">Today\'s proof submitted successfully!</div><div style="font-size:12.5px;color:var(--text2)">Submitted at '+fmtTime(todaySub)+'  ·  Status: '+renderStatusBadge(todaySub.status)+'</div></div></div>';
    document.getElementById('submitBadge').style.display='none';
  }
  renderRecentSessions();
  renderSubHistory();
  updateMyStats();
}

function openStatModal(type){
  const u=S.user; if(!u) return;
  const myId=u._id||u.id;
  const todaySub=getTodaySub(myId);
  const students=(S.leaderboardData||[]);
  const sorted=[...students].sort((a,b)=>(b.totalHours||b.hrs||0)-(a.totalHours||a.hrs||0));
  const rank=sorted.findIndex(x=>String(x._id||x.id||x.userId)===String(myId))+1;
  let html='';
  if(type==='today'){
    const todaySessions=S.sessions.filter(s=>{
      const d=s.date||localDateStr(s.startTime||s.endTime||Date.now());
      return d===todayStr();
    });
    const totalSecs=todaySessions.reduce((a,s)=>a+(s.duration||0),0);
    html=`<div style="text-align:center;margin-bottom:24px">
      <div style="font-size:48px;margin-bottom:8px">⏱</div>
      <div style="font-size:32px;font-weight:700;color:var(--primary-dark)">${fmtDur(totalSecs)}</div>
      <div style="color:var(--text3);font-size:13px;margin-top:4px">Total study time today</div>
    </div>
    <div style="font-weight:600;margin-bottom:12px;color:var(--text)">Today's Sessions (${todaySessions.length})</div>
    ${todaySessions.length?todaySessions.map(s=>`
      <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:var(--bg);border-radius:10px;margin-bottom:8px">
        <div style="font-weight:500">${s.subject||'Study'}</div>
        <div style="color:var(--primary-dark);font-weight:600">${fmtDur(s.duration||0)}</div>
      </div>`).join(''):'<div style="color:var(--text3);text-align:center;padding:20px">No sessions recorded today yet.</div>'}`;
  } else if(type==='streak'){
    const history=S.submissions.slice(0,14).map(s=>({date:s.date,status:s.status}));
    html=`<div style="text-align:center;margin-bottom:24px">
      <div style="font-size:48px;margin-bottom:8px">🔥</div>
      <div style="font-size:36px;font-weight:700;color:var(--success-dark)">${u.streak||0}</div>
      <div style="color:var(--text3);font-size:14px">Day Streak</div>
      <div style="margin-top:8px;font-size:13px;color:var(--text2)">Longest streak: <strong>${u.longestStreak||u.streak||0} days</strong></div>
    </div>
    <div style="font-weight:600;margin-bottom:12px">Recent Submission History</div>
    ${history.length?history.map(s=>`
      <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:var(--bg);border-radius:10px;margin-bottom:8px">
        <div style="color:var(--text2);font-size:13px">${s.date}</div>
        ${renderStatusBadge(s.status)}
      </div>`).join(''):'<div style="color:var(--text3);text-align:center;padding:20px">No submission history yet.</div>'}`;
  } else if(type==='rank'){
    const top5=sorted.slice(0,5);
    html=`<div style="text-align:center;margin-bottom:24px">
      <div style="font-size:48px;margin-bottom:8px">🏆</div>
      <div style="font-size:36px;font-weight:700;color:var(--warning-dark)">${rank>0?'#'+rank:'#—'}</div>
      <div style="color:var(--text3);font-size:14px">Your Leaderboard Position</div>
      <div style="font-size:13px;color:var(--text2);margin-top:6px">Total study: <strong>${fmtHours(u.totalStudyHours||u.totalHours||0)}</strong></div>
    </div>
    <div style="font-weight:600;margin-bottom:12px">Top 5 Students</div>
    ${top5.map((s,i)=>{
      const isMe=String(s._id||s.id||s.userId)===String(myId);
      return `<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;background:${isMe?'var(--primary-light)':'var(--bg)'};border-radius:10px;margin-bottom:8px;${isMe?'border:1.5px solid var(--primary)':''}">
        <div style="font-size:20px">${i===0?'🥇':i===1?'🥈':i===2?'🥉':'#'+(i+1)}</div>
        <div style="flex:1;font-weight:${isMe?'700':'500'}">${s.name||s.username||'Student'}${isMe?' (You)':''}</div>
        <div style="color:var(--primary-dark);font-weight:600">${fmtHours(s.totalHours||s.hrs||0)}</div>
      </div>`;
    }).join('')}`;
  } else if(type==='status'){
    const lr=u.leavesRemaining??3; const hdr=u.halfDaysRemaining??3;
    html=`<div style="text-align:center;margin-bottom:24px">
      <div style="font-size:48px;margin-bottom:8px">📋</div>
      <div style="margin-bottom:8px">${todaySub?renderStatusBadge(todaySub.status):'<span class="status-badge s-pending">⏳ Pending</span>'}</div>
      <div style="color:var(--text3);font-size:13px">${todaySub?'Submitted at '+fmtTime(todaySub):'No submission yet today'}</div>
    </div>
    <div style="display:flex;gap:10px;background:var(--success-light);border-radius:10px;padding:12px 14px;margin-bottom:16px">
      <div style="flex:1;text-align:center">
        <div style="font-size:22px;font-weight:700;color:var(--success-dark)">${lr}</div>
        <div style="font-size:12px;color:var(--success-dark);font-weight:600">🏖️ Leaves Left</div>
      </div>
      <div style="width:1px;background:var(--st-completed-br)"></div>
      <div style="flex:1;text-align:center">
        <div style="font-size:22px;font-weight:700;color:var(--warning-dark)">${hdr}</div>
        <div style="font-size:12px;color:var(--warning-dark);font-weight:600">🟡 Half Days Left</div>
      </div>
    </div>
    <div style="font-weight:600;margin-bottom:12px">Your Stats</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div style="background:var(--bg);border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:var(--success-dark)">${u.totalCompleted||0}</div>
        <div style="font-size:12px;color:var(--text3)">✅ Completed</div>
      </div>
      <div style="background:var(--bg);border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:var(--warning-dark)">${u.totalHalfDay||0}</div>
        <div style="font-size:12px;color:var(--text3)">🟡 Half Days Used</div>
      </div>
      <div style="background:var(--bg);border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:var(--text2)">${u.totalLeave||0}</div>
        <div style="font-size:12px;color:var(--text3)">🏖️ Leaves Used</div>
      </div>
      <div style="background:var(--bg);border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:var(--error-dark)">${u.totalFines||0}</div>
        <div style="font-size:12px;color:var(--text3)">🔴 Fines</div>
      </div>
    </div>
    ${todaySub&&todaySub.adminNotes?`<div style="margin-top:16px;padding:12px;background:var(--warning-light);border-radius:10px;font-size:13px;color:var(--text2)"><strong>Admin Note:</strong> ${todaySub.adminNotes}</div>`:''}
    ${!todaySub?`<div style="margin-top:16px"><button class="btn btn-primary" style="width:100%" onclick="closeStatModal();nav('submit')">Submit Today's Proof →</button></div>`:''}`;
  }
  document.getElementById('statModalContent').innerHTML=html;
  const modal=document.getElementById('statModal');
  modal.style.display='flex';
  setTimeout(()=>modal.querySelector('div').style.transform='scale(1)',10);
}

function closeStatModal(){
  document.getElementById('statModal').style.display='none';
}

function getTodaySub(uid){
  const today=todayStr();
  return S.submissions.find(s=>{
    if (s.date !== today) return false;
    const subUid = s.userId?._id || s.userId;
    // GET /submission/my omits userId; list is already scoped to the logged-in student
    if (subUid == null) return true;
    return subUid===uid || subUid===String(uid);
  });
}

function isLeaveSubmission(sub){
  if(!sub) return false;
  if(sub.status === 'leave' || sub.status === 'emergency') return true;
  if(sub.submissionType === 'leave' || sub.submissionType === 'emergency') return true;
  const t = sub.timerScreenshot || '';
  const q = sub.questScreenshot || '';
  // Backend writes 'leave/placeholder.jpg' for both kinds of absence
  return t.includes('leave/') || q.includes('leave/');
}

function isEmergencySubmission(sub){
  return sub?.submissionType === 'emergency' || sub?.status === 'emergency';
}

// Generate a screenshot tile with graceful onerror fallback when the file is missing.
// Used in admin verify cards and the verify modal.
function renderScreenshotTile(url, label, icon, size='small'){
  const safeUrl = (url || '').replace(/'/g, "\\'");
  const fallbackInline = `this.style.display='none';this.parentElement.innerHTML='<div style=\\'display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:6px;color:var(--text3);background:var(--bg2);border-radius:8px\\'><span style=\\'font-size:${size==='large'?32:24}px\\'>${icon}</span><span style=\\'font-size:${size==='large'?13:11.5}px;font-weight:500\\'>Screenshot unavailable</span></div>';`;
  if (!url) {
    return `<div class="sub-ss" style="font-size:12px;color:var(--text3);flex-direction:column;gap:4px"><span style="font-size:${size==='large'?32:24}px">${icon}</span><span>No screenshot</span></div>`;
  }
  return `<div class="sub-ss" onclick="openLightbox('${safeUrl}')"><img src="${url}" onerror="${fallbackInline}"><div class="ss-label">${label}</div></div>`;
}

function renderStatusBadge(s){
  const map={completed:'s-completed',halfday:'s-halfday',leave:'s-leave',fine:'s-fine',
             gt:'s-gt',emergency:'s-emergency',pending:'s-pending'};
  const labels={completed:'✅ Completed',halfday:'🟡 Half Day',leave:'❌ Leave',fine:'🔴 Fine',
                gt:'📗 Grand Test',emergency:'🚑 Emergency',pending:'⏳ Pending'};
  return `<span class="status-badge ${map[s]||'s-pending'}">${labels[s]||s}</span>`;
}

function renderRecentSessions(){
  const sessions=S.sessions.slice(0,5);
  if(!sessions.length){
    document.getElementById('recentSessions').innerHTML='<div style="color:var(--text3);font-size:13px;padding:20px 0;text-align:center">No sessions yet. <a style="color:var(--primary-dark);cursor:pointer" onclick="nav(\'timer\')">Start studying →</a></div>';
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
    if(subUid==null) return true;
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
// Track current submission type
S.submissionType = 'fullday';

function renderSubmitAllowance(){
  const u=S.user; if(!u) return;
  const lr=u.leavesRemaining??3; const hr=u.halfDaysRemaining??3;
  const slEl=document.getElementById('submitLeavesLeft'); if(slEl) slEl.textContent=lr;
  const shEl=document.getElementById('submitHalfLeft'); if(shEl) shEl.textContent=hr;
  // Update count badges on cards
  const lc=document.getElementById('leaveCount');
  if(lc) lc.textContent=lr>0?lr+' remaining':'None left';
  if(lc) lc.style.color=lr>0?'var(--success-dark)':'#EF4444';
  const hc=document.getElementById('halfDayCount');
  if(hc) hc.textContent=hr>0?hr+' remaining':'None left';
  if(hc) hc.style.color=hr>0?'var(--warning-dark)':'#EF4444';
  // Visually disable cards with 0 count
  const leaveCard=document.getElementById('typeLeave');
  if(leaveCard){
    leaveCard.style.opacity=lr>0?'1':'0.45';
    leaveCard.style.pointerEvents=lr>0?'auto':'none';
  }
  const hdCard=document.getElementById('typeHalfDay');
  if(hdCard){
    hdCard.style.opacity=hr>0?'1':'0.45';
    hdCard.style.pointerEvents=hr>0?'auto':'none';
  }
}

function setSubmissionType(type){
  const u=S.user;
  // Guard: prevent selecting exhausted types
  if(type==='leave' && (u?.leavesRemaining??3)<=0){ toast('No leaves remaining!','error'); return; }
  if(type==='halfday' && (u?.halfDaysRemaining??3)<=0){ toast('No half days remaining!','error'); return; }
  S.submissionType = type;
  const types = ['fullday','halfday','gt','leave','emergency'];
  const colors = {fullday:'var(--primary)',halfday:'var(--warning-dark)',gt:'var(--st-completed-fg)',leave:'var(--success-dark)',emergency:'var(--primary-dark)'};
  const bgs = {fullday:'var(--primary-light)',halfday:'var(--warning-light)',gt:'var(--st-completed-bg)',leave:'var(--success-light)',emergency:'var(--st-pending-bg)'};
  const ids = {fullday:'typeFullDay',halfday:'typeHalfDay',gt:'typeGT',leave:'typeLeave',emergency:'typeEmergency'};
  types.forEach(t=>{
    const el=document.getElementById(ids[t]);
    if(!el) return;
    if(t===type){
      el.style.border=`2px solid ${colors[t]}`;
      el.style.background=bgs[t];
    } else {
      el.style.border='2px solid var(--border)';
      el.style.background='var(--bg)';
    }
  });

  const noShots = type==='leave' || type==='emergency';
  const isGT = type==='gt';
  document.getElementById('screenshotSection').style.display=noShots?'none':'block';
  document.getElementById('leaveSection').style.display=noShots?'block':'none';
  // A Grand Test is evidenced by the single result screenshot.
  document.getElementById('questUploadGroup').style.display=isGT?'none':'block';
  document.getElementById('timerUploadLabel').textContent=isGT?'Grand Test Screenshot':'Study Timer Screenshot';
  document.getElementById('timerUploadHeading').textContent=isGT?'Upload Grand Test Result':'Upload Timer Screenshot';
  const reasonLabel=document.querySelector('#leaveSection .form-label');
  if(reasonLabel) reasonLabel.textContent = type==='emergency'
    ? 'What happened? (Optional)' : 'Reason for Leave (Optional)';
}

function triggerUpload(id){ /* handled by input */ }

// Vercel rejects any request over 4.5MB before it reaches the API, and a
// submission carries two images, so each one is resized well under half of that.
const MAX_IMAGE_EDGE = 1280;
const IMAGE_QUALITY = 0.8;

function compressImage(file){
  return new Promise((resolve,reject)=>{
    const reader=new FileReader();
    reader.onerror=()=>reject(new Error('Could not read that file.'));
    reader.onload=e=>{
      const img=new Image();
      img.onerror=()=>reject(new Error('That file is not a readable image.'));
      img.onload=()=>{
        const scale=Math.min(1, MAX_IMAGE_EDGE/Math.max(img.width,img.height));
        const canvas=document.createElement('canvas');
        canvas.width=Math.round(img.width*scale);
        canvas.height=Math.round(img.height*scale);
        canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);
        resolve(canvas.toDataURL('image/jpeg',IMAGE_QUALITY));
      };
      img.src=e.target.result;
    };
    reader.readAsDataURL(file);
  });
}

async function handleFileUpload(input,previewId,zoneId){
  const file=input.files[0];
  if(!file) return;
  const key=input.id==='timerFile'?'timer':'quest';
  const zone=document.getElementById(zoneId);
  const content=zone.querySelector('[id$="UploadContent"]');
  try{
    const dataUrl=await compressImage(file);
    S.timerFiles[key]=dataUrl;
    const preview=document.getElementById(previewId);
    preview.src=dataUrl;
    preview.style.display='block';
    if(content) content.style.display='none';
  }catch(err){
    S.timerFiles[key]=null;
    input.value='';
    if(content) content.style.display='';
    alert(err.message||'Could not process that image. Try a different screenshot.');
  }
}

// A rejected upload never reaches the API, so the response is the host's HTML
// error page rather than our JSON. Turn that into something a student can act on.
async function readUploadResponse(res){
  try{
    return await res.json();
  }catch{
    if(res.status===413){
      return { message:'Those screenshots are too large to send. Crop them or use a plain screenshot rather than a photo of the screen, then try again.' };
    }
    return { message:`Upload failed (error ${res.status}). Check your connection and try again.` };
  }
}

async function submitProof() {
  const type = S.submissionType || 'fullday';

  if(type === 'leave' || type === 'emergency'){
    // No screenshots for either kind of absence.
    const fallback = type==='emergency' ? "Emergency leave" : "Student requested leave";
    try {
      const formData = new FormData();
      formData.append("subject", "Other");
      formData.append("hoursStudied", "0.5");
      formData.append("notes", document.getElementById("leaveReason").value || fallback);
      formData.append("submissionType", type);
      const res = await fetch(`${API_URL}/submission/upload`, {
        method: "POST",
        headers: { ...authHeader() },
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) { await handleSubmitRejection(res, data); return; }
      toast(data.message || "Form submitted successfully", "success");
      document.getElementById("leaveReason").value = "";
      await fetchSubmissions();
      renderTodaySub();
      renderDashboard();
      updatePendingBadge();
      await refreshUserProfile();
      renderSubmitAllowance();
      S.forceFormOpen = false;
      await refreshSubmitPage();
      if(S.myRegister) loadMyRegister();
    } catch(err){ console.error(err); alert("Submission error"); }
    return;
  }

  // Full Day, Half Day or Grand Test — screenshots required
  const isGT = type === 'gt';
  const timerB64 = S.timerFiles.timer;
  const questB64 = S.timerFiles.quest;
  if (!timerB64) {
    alert(isGT ? "Please upload your Grand Test screenshot." : "Please upload both screenshots.");
    return;
  }
  if (!isGT && !questB64) { alert("Please upload both screenshots."); return; }
  const hours = parseFloat(document.getElementById("subHours").value);
  if (!hours || hours <= 0) { alert("Please enter valid hours studied."); return; }
  try {
    const formData = new FormData();
    formData.append("timerScreenshot", dataURLtoBlob(timerB64), isGT ? "grandtest.jpg" : "timer.jpg");
    if (!isGT) formData.append("questionScreenshot", dataURLtoBlob(questB64), "questions.jpg");
    formData.append("subject", document.getElementById("subSubject").value);
    formData.append("hoursStudied", String(hours));
    formData.append("notes", document.getElementById("subNotes").value || "");
    formData.append("submissionType", type);
    const res = await fetch(`${API_URL}/submission/upload`, {
      method: "POST",
      headers: { ...authHeader() },
      body: formData,
    });
    const data = await readUploadResponse(res);
    if (!res.ok) { await handleSubmitRejection(res, data); return; }
    toast(data.message || "Form submitted successfully", "success");
    clearScreenshotPickers();
    await fetchSubmissions();
    renderTodaySub();
    renderDashboard();
    updatePendingBadge();
    if(type==='halfday'){ await refreshUserProfile(); renderSubmitAllowance(); }
    S.forceFormOpen = false;
    await refreshSubmitPage();
    if(S.myRegister) loadMyRegister();
  } catch (err) {
    console.error(err);
    alert("Upload error");
  }
}

// 423 means the window or the two-attempt cap stopped it, not bad input, so the
// page re-reads its state and closes the form rather than leaving it inviting.
async function handleSubmitRejection(res, data){
  const message = data?.message || "Submission failed";
  if (res.status === 423) {
    toast(message, "error");
    S.forceFormOpen = false;
    await refreshSubmitPage();
    return;
  }
  alert(message);
}

function clearScreenshotPickers(){
  S.timerFiles = {};
  ['timer','quest'].forEach(k=>{
    const preview=document.getElementById(k==='timer'?'timerPreview':'questPreview');
    const content=document.getElementById(k==='timer'?'timerUploadContent':'questUploadContent');
    const input=document.getElementById(k==='timer'?'timerFile':'questFile');
    if(preview){ preview.style.display='none'; preview.src=''; }
    if(content) content.style.display='';
    if(input) input.value='';
  });
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

// ---------- Submission window + attempt gate ----------
// The server owns the clock and the attempt count. The page mirrors them and
// only counts seconds locally, so a student cannot unlock the form by changing
// their device time.
S.gate = null;
S.serverSkewMs = 0;
S.gateTicker = null;
S.forceFormOpen = false;

async function fetchSubmitGate(){
  if(!S.user || S.user.role==='admin') return null;
  try{
    const res=await fetch(`${API_URL}/submission/today-status`,{headers:{...authHeader()}});
    if(!res.ok) return null;
    const data=await res.json();
    S.gate=data;
    if(data.window?.serverTime){
      S.serverSkewMs=Date.parse(data.window.serverTime)-Date.now();
    }
    return data;
  }catch(err){
    console.error('Could not load submission window:',err);
    return null;
  }
}

function serverNow(){ return new Date(Date.now()+S.serverSkewMs); }

function countdownText(seconds){
  const s=Math.max(0,Math.floor(seconds));
  const h=Math.floor(s/3600), m=Math.floor((s%3600)/60), sec=s%60;
  const pad=n=>String(n).padStart(2,'0');
  return h>0 ? `${h}h ${pad(m)}m ${pad(sec)}s` : `${m}m ${pad(sec)}s`;
}

// Seconds left, recomputed from the server's anchor so the number keeps moving
// between refreshes without drifting.
function secondsLeft(){
  const w=S.gate?.window;
  if(!w) return {state:'open',open:0,close:0};
  const elapsed=(Date.now()+S.serverSkewMs-Date.parse(w.serverTime))/1000;
  const untilOpen=w.secondsUntilOpen-elapsed;
  const untilClose=w.secondsUntilClose-elapsed;
  let state=w.state;
  if(state==='before'&&untilOpen<=0) state='open';
  if(state==='open'&&untilClose<=0) state='late';
  return {state,open:untilOpen,close:untilClose};
}

function startGateTicker(){
  stopGateTicker();
  S.gateTicker=setInterval(()=>{
    updateSubWindowBanner();
    updateDeadlineBanner();
  },1000);
}
function stopGateTicker(){ if(S.gateTicker){ clearInterval(S.gateTicker); S.gateTicker=null; } }

function updateSubWindowBanner(){
  const el=document.getElementById('subWindowBanner');
  if(!el||!S.gate) return;
  const g=S.gate, w=g.window||{};
  const {state,open,close}=secondsLeft();

  const gw=document.getElementById('guidelineWindow');
  if(gw&&w.opensAt) gw.textContent=`${w.opensAt} – ${w.closesAt}`;

  if(state==='before'){
    el.innerHTML=`<div class="deadline-banner active"><span>🔒</span><div style="font-size:13px;color:var(--warning-dark)">
      Submissions open at <strong>${w.opensAt}</strong> — in <strong>${countdownText(open)}</strong>. Get your screenshots ready.</div></div>`;
  } else if(state==='open'){
    const urgent=close<=1800;
    el.innerHTML=`<div class="deadline-banner ${urgent?'missed':'active'}"><span>${urgent?'⚠️':'⏳'}</span><div style="font-size:13px;color:${urgent?'var(--error-dark)':'var(--warning-dark)'};font-weight:600">
      Time left to submit: <strong style="font-variant-numeric:tabular-nums">${countdownText(close)}</strong> — closes at ${w.closesAt}</div></div>`;
  } else {
    el.innerHTML=`<div class="deadline-banner missed"><span>❌</span><div style="font-size:13px;color:var(--error-dark);font-weight:600">
      Deadline passed at ${w.closesAt}. Anything you send now is marked <strong>LATE</strong> for the admin.</div></div>`;
  }
}

// Decides whether the student sees the form, a success panel, or a lock notice.
function renderSubmitGate(){
  const g=S.gate;
  const card=document.getElementById('submitFormCard');
  const panel=document.getElementById('submitLockPanel');
  if(!g||!card||!panel) return;

  const note=document.getElementById('submitAttemptNote');
  if(note){
    note.textContent = g.attemptsLeft>1
      ? ''
      : g.attemptsLeft===1 && g.submitted
        ? 'This is your final submission for today — check both screenshots before sending.'
        : '';
  }

  const editing = S.forceFormOpen && g.canSubmit;
  const showForm = g.canSubmit && (!g.submitted || editing);
  card.style.display = showForm ? '' : 'none';

  if(showForm && !g.submitted){ panel.style.display='none'; return; }

  panel.style.display='';
  if(g.submitted){
    const statusLine = g.isVerified
      ? `Admin reviewed it: ${renderStatusBadge(g.status)}`
      : 'Waiting for the admin to review it.';
    const lateTag = g.isLate
      ? `<span class="pill pill-red" style="margin-left:8px">LATE</span>` : '';
    const canFix = g.canSubmit && g.attemptsLeft>0;
    panel.innerHTML=`<div class="card" style="border-left:3px solid var(--success);text-align:center">
      <div style="font-size:40px;line-height:1">✅</div>
      <div style="font-weight:800;font-size:19px;color:var(--success-dark);margin-top:8px">Form submitted successfully${lateTag}</div>
      <div style="font-size:13.5px;color:var(--text2);margin-top:6px">${statusLine}</div>
      <div style="display:flex;justify-content:center;gap:24px;margin:18px 0 6px;flex-wrap:wrap">
        <div><div style="font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.4px">Subject</div>
             <div style="font-weight:700;color:var(--text)">${g.subject||'—'}</div></div>
        <div><div style="font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.4px">Hours</div>
             <div style="font-weight:700;color:var(--text)">${g.hoursStudied??'—'}</div></div>
        <div><div style="font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.4px">Submissions used</div>
             <div style="font-weight:700;color:var(--text)">${g.attemptsUsed} of ${g.attemptsAllowed}</div></div>
      </div>
      ${canFix
        ? `<div style="font-size:13px;color:var(--text2);margin-top:12px">Uploaded the wrong screenshot? You can replace it <strong>once</strong>.</div>
           <button class="btn btn-ghost" style="margin-top:10px" onclick="reopenSubmitForm()">✏️ Replace my submission</button>`
        : `<div style="font-size:13px;color:var(--text3);margin-top:12px">${g.lockReason||'The form is closed for today.'}</div>`}
    </div>`;
  } else {
    panel.innerHTML=`<div class="card" style="border-left:3px solid var(--warning);text-align:center">
      <div style="font-size:40px;line-height:1">🔒</div>
      <div style="font-weight:800;font-size:18px;color:var(--text);margin-top:8px">Form is not open yet</div>
      <div style="font-size:13.5px;color:var(--text2);margin-top:6px">${g.lockReason||''}</div>
    </div>`;
  }
}

function reopenSubmitForm(){
  S.forceFormOpen=true;
  renderSubmitGate();
  document.getElementById('submitFormCard')?.scrollIntoView({behavior:'smooth',block:'start'});
  toast('You have one correction left — re-upload both screenshots','info');
}

async function refreshSubmitPage(){
  await fetchSubmitGate();
  renderSubmitGate();
  updateSubWindowBanner();
  startGateTicker();
}

function updateDeadlineBanner(){
  if(!S.user||S.user.role==='admin') return;
  const el=document.getElementById('deadlineTag');
  if(!el) return;
  const g=S.gate;
  if(!g||g.submitted){ el.innerHTML=''; return; }
  const {state,close}=secondsLeft();
  if(state==='open'&&close<=3*3600){
    el.innerHTML=`<span class="pill pill-amber">⏰ ${countdownText(close)} left to submit</span>`;
  } else if(state==='late'){
    el.innerHTML='<span class="pill pill-red">⏰ Deadline passed</span>';
  } else { el.innerHTML=''; }
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
    let res = await fetch(`${API_URL}/session/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeader() },
      body: JSON.stringify({ subject: S.currentSubject }),
    });
    let data = await res.json().catch(() => ({}));

    // If an orphaned/stale session is blocking us, auto-stop it silently and retry once
    if (res.status === 409 && data.session?.id) {
      try {
        await fetch(`${API_URL}/session/stop`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeader() },
          body: JSON.stringify({ sessionId: data.session.id }),
        });
      } catch(_) { /* ignore */ }
      // Retry start
      res = await fetch(`${API_URL}/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader() },
        body: JSON.stringify({ subject: S.currentSubject }),
      });
      data = await res.json().catch(() => ({}));
    }

    if (!res.ok) {
      toast(data.message || "Could not start session — please try again.", "error");
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
    const color=u.color||'var(--fill-primary)';
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

function openAnalyticsModal(type){
  const u=S.user; if(!u) return;
  const uid=u._id||u.id;
  const subs=S.submissions.filter(s=>{
    const subUid=s.userId?._id||s.userId;
    return (subUid===uid||subUid===String(uid)||subUid==null)&&s.status!=='pending';
  });
  const total=subs.length;
  const completed=subs.filter(s=>s.status==='completed');
  const fines=subs.filter(s=>s.status==='fine');
  const halfdays=subs.filter(s=>s.status==='halfday');
  const leaves=subs.filter(s=>s.status==='leave');
  const avgHrs=total>0?(subs.reduce((a,s)=>a+(s.hours||s.hoursStudied||0),0)/total).toFixed(1):0;
  const goalDays=subs.filter(s=>(s.hours||s.hoursStudied||0)>=4);
  const consistPct=total>0?Math.round(completed.length/total*100):0;
  const goalPct=total>0?Math.round(goalDays.length/total*100):0;
  let html='';
  if(type==='consistency'){
    html=`<div style="text-align:center;margin-bottom:24px">
      <div style="font-size:48px;margin-bottom:8px">📈</div>
      <div style="font-size:36px;font-weight:700;color:var(--primary-dark)">${consistPct}%</div>
      <div style="color:var(--text3);font-size:14px">Consistency Rate</div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px">
      <div style="background:var(--bg);border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:var(--success-dark)">${completed.length}</div>
        <div style="font-size:12px;color:var(--text3)">✅ Completed days</div>
      </div>
      <div style="background:var(--bg);border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:var(--text2)">${total}</div>
        <div style="font-size:12px;color:var(--text3)">📅 Total days tracked</div>
      </div>
    </div>
    <div style="font-weight:600;margin-bottom:12px">Recent Completed Days</div>
    ${completed.slice(0,5).map(s=>`<div style="display:flex;justify-content:space-between;padding:10px 14px;background:var(--bg);border-radius:10px;margin-bottom:8px">
      <div style="color:var(--text2);font-size:13px">${s.date}</div>
      <div style="color:var(--success-dark);font-weight:600">${(s.hours||s.hoursStudied||0).toFixed(1)}h</div>
    </div>`).join('')||'<div style="color:var(--text3);text-align:center;padding:16px">No completed days yet.</div>'}`;
  } else if(type==='avghrs'){
    const bySubject={};
    subs.forEach(s=>{const subj=s.subject||'Other';bySubject[subj]=(bySubject[subj]||0)+(s.hours||s.hoursStudied||0);});
    html=`<div style="text-align:center;margin-bottom:24px">
      <div style="font-size:48px;margin-bottom:8px">⚡</div>
      <div style="font-size:36px;font-weight:700;color:var(--success-dark)">${avgHrs}h</div>
      <div style="color:var(--text3);font-size:14px">Average daily study hours</div>
      <div style="font-size:13px;color:var(--text2);margin-top:4px">Total: <strong>${subs.reduce((a,s)=>a+(s.hours||s.hoursStudied||0),0).toFixed(1)}h</strong> across ${total} days</div>
    </div>
    <div style="font-weight:600;margin-bottom:12px">Hours by Subject</div>
    ${Object.entries(bySubject).sort((a,b)=>b[1]-a[1]).map(([subj,hrs])=>`
      <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:var(--bg);border-radius:10px;margin-bottom:8px">
        <div style="font-weight:500">${subj}</div>
        <div style="color:var(--success-dark);font-weight:600">${hrs.toFixed(1)}h</div>
      </div>`).join('')||'<div style="color:var(--text3);text-align:center;padding:16px">No data yet.</div>'}`;
  } else if(type==='goal'){
    html=`<div style="text-align:center;margin-bottom:24px">
      <div style="font-size:48px;margin-bottom:8px">🎯</div>
      <div style="font-size:36px;font-weight:700;color:var(--warning-dark)">${goalPct}%</div>
      <div style="color:var(--text3);font-size:14px">Goal Hit Rate (days ≥ 4h)</div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px">
      <div style="background:var(--bg);border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:var(--warning-dark)">${goalDays.length}</div>
        <div style="font-size:12px;color:var(--text3)">🎯 Goal days (≥4h)</div>
      </div>
      <div style="background:var(--bg);border-radius:10px;padding:14px;text-align:center">
        <div style="font-size:22px;font-weight:700;color:var(--text2)">${total-goalDays.length}</div>
        <div style="font-size:12px;color:var(--text3)">📉 Below goal days</div>
      </div>
    </div>
    <div style="font-weight:600;margin-bottom:12px">Goal Achieved Days</div>
    ${goalDays.slice(0,5).map(s=>`<div style="display:flex;justify-content:space-between;padding:10px 14px;background:var(--bg);border-radius:10px;margin-bottom:8px">
      <div style="color:var(--text2);font-size:13px">${s.date}</div>
      <div style="color:var(--warning-dark);font-weight:600">${(s.hours||s.hoursStudied||0).toFixed(1)}h ✓</div>
    </div>`).join('')||'<div style="color:var(--text3);text-align:center;padding:16px">No goal days yet. Aim for 4h/day!</div>'}`;
  } else if(type==='fines'){
    html=`<div style="text-align:center;margin-bottom:24px">
      <div style="font-size:48px;margin-bottom:8px">🔴</div>
      <div style="font-size:36px;font-weight:700;color:var(--error-dark)">${fines.length}</div>
      <div style="color:var(--text3);font-size:14px">Total Fines</div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:16px">
      <div style="background:var(--bg);border-radius:10px;padding:12px;text-align:center">
        <div style="font-size:20px;font-weight:700;color:var(--error-dark)">${fines.length}</div>
        <div style="font-size:11px;color:var(--text3)">🔴 Fines</div>
      </div>
      <div style="background:var(--bg);border-radius:10px;padding:12px;text-align:center">
        <div style="font-size:20px;font-weight:700;color:var(--text2)">${leaves.length}</div>
        <div style="font-size:11px;color:var(--text3)">❌ Leaves</div>
      </div>
      <div style="background:var(--bg);border-radius:10px;padding:12px;text-align:center">
        <div style="font-size:20px;font-weight:700;color:var(--warning-dark)">${halfdays.length}</div>
        <div style="font-size:11px;color:var(--text3)">🟡 Half Days</div>
      </div>
    </div>
    <div style="font-weight:600;margin-bottom:12px">Fine History</div>
    ${fines.slice(0,5).map(s=>`<div style="display:flex;justify-content:space-between;padding:10px 14px;background:var(--error-light);border-radius:10px;margin-bottom:8px">
      <div style="color:var(--text2);font-size:13px">${s.date}</div>
      <span class="status-badge s-fine">🔴 Fine</span>
    </div>`).join('')||'<div style="color:var(--success-dark);text-align:center;padding:16px;font-weight:600">🎉 No fines! Great work!</div>'}`;
  }
  document.getElementById('statModalContent').innerHTML=html;
  const modal=document.getElementById('statModal');
  modal.style.display='flex';
}

// Hours the logged-in student actually logged, keyed by calendar day.
function myHoursByDate(){
  const uid=S.user?._id||S.user?.id;
  const map={};
  (S.submissions||[]).forEach(s=>{
    const subUid=s.userId?._id||s.userId;
    if(subUid!=null && String(subUid)!==String(uid)) return;
    if(!s.date) return;
    map[s.date]=(map[s.date]||0)+(s.hoursStudied||s.hours||0);
  });
  return map;
}

function buildActGrid(){
  const grid=document.getElementById('actGrid');
  if(!grid) return;
  const hours=myHoursByDate();
  const weeks=13;
  // Walk back to the Sunday that starts the earliest column.
  const start=new Date();
  start.setDate(start.getDate()-(weeks*7-1));
  start.setDate(start.getDate()-start.getDay());

  let html='';
  for(let w=0;w<weeks;w++){
    html+='<div class="act-col">';
    for(let d=0;d<7;d++){
      const cell=new Date(start);
      cell.setDate(start.getDate()+w*7+d);
      const h=hours[localDateStr(cell)]||0;
      let cls='';
      if(h>=6) cls='act-5';
      else if(h>=4) cls='act-4';
      else if(h>=2) cls='act-3';
      else if(h>0) cls='act-1';
      html+=`<div class="act-cell ${cls}" title="${localDateStr(cell)} — ${h?h.toFixed(1)+'h':'no study'}"></div>`;
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
  return allUsers.find(u=>(u._id||u.id)===subUid)||{name:'Unknown',avatar:'?',color:'var(--text3)'};
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
    const color=student.color||'var(--fill-primary)';
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
            ${sub.isLate?'<span class="pill pill-red">⏰ Late</span>':''}
            ${sub.attemptCount>1?'<span class="pill pill-amber">✏️ Corrected</span>':''}
          </div>
          ${isLeaveSubmission(sub)
            ? (isEmergencySubmission(sub)
              ?`<div style="background:var(--primary-light);border:1px solid var(--st-pending-br);border-radius:10px;padding:14px;text-align:center;margin-bottom:10px">
                  <div style="font-size:28px;margin-bottom:6px">🚑</div>
                  <div style="font-weight:700;color:var(--primary-dark);font-size:13px">Emergency Leave</div>
                  <div style="font-size:11.5px;color:var(--primary-dark);margin-top:2px">Outside the monthly leave quota</div>
                </div>`
              :`<div style="background:var(--success-light);border:1px solid var(--st-completed-br);border-radius:10px;padding:14px;text-align:center;margin-bottom:10px">
                  <div style="font-size:28px;margin-bottom:6px">🏖️</div>
                  <div style="font-weight:700;color:var(--success-dark);font-size:13px">Leave Request</div>
                  <div style="font-size:11.5px;color:var(--success-dark);margin-top:2px">No screenshots required</div>
                </div>`)
            : sub.submissionType==='gt'
            ?`<div class="sub-screenshots" style="grid-template-columns:1fr">
              ${renderScreenshotTile(sub.timerScreenshot, 'Grand Test', '📗', 'small')}
            </div>`
            :`<div class="sub-screenshots">
              ${renderScreenshotTile(sub.timerScreenshot, 'Timer', '⏱', 'small')}
              ${renderScreenshotTile(sub.questScreenshot, 'Questions', '📝', 'small')}
            </div>`
          }
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
  if(isLeaveSubmission(sub)){
    document.getElementById('vModalScreenshots').innerHTML = `<div style="grid-column:span 2;background:var(--success-light);border:1px solid var(--st-completed-br);border-radius:12px;padding:24px;text-align:center">
      <div style="font-size:42px;margin-bottom:8px">🏖️</div>
      <div style="font-weight:700;color:var(--success-dark);font-size:15px">Leave Request</div>
      <div style="font-size:13px;color:var(--success-dark);margin-top:4px">Student requested leave — no screenshots required</div>
    </div>`;
  } else {
    const ssHtml = [
      renderScreenshotTile(sub.timerScreenshot, 'Timer Screenshot', '⏱', 'large'),
      renderScreenshotTile(sub.questScreenshot, 'Questions Screenshot', '📝', 'large'),
    ];
    document.getElementById('vModalScreenshots').innerHTML = ssHtml.join('');
  }
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
  // Verification changes streaks, points and today's status, so pull fresh rows.
  fetchAdminUsers().then(()=>{renderPendingApprovals();renderAdminUsers();});
  if(S.register) loadRegister();
  toast(`Status set to "${S.verifyStatus}" for ${student?.name?.split(' ')[0]||'student'}`,'success');
}

// ===================== STUDENT'S OWN REGISTER =====================
// Read only by design: the only way a day changes is by submitting proof.
S.myRegister = null;
S.myRegMonth = null;

function shiftMyMonth(delta){
  const [y,m]=(S.myRegMonth||todayStr().slice(0,7)).split('-').map(Number);
  const d=new Date(y, m-1+delta, 1);
  S.myRegMonth=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
  loadMyRegister();
}

async function loadMyRegister(){
  if(!S.user || S.user.role==='admin') return;
  const month=S.myRegMonth||todayStr().slice(0,7);
  S.myRegMonth=month;
  try{
    const res=await fetch(`${API_URL}/submission/my-register?month=${month}`,{headers:{...authHeader()}});
    if(!res.ok){ toast('Could not load your register','error'); return; }
    S.myRegister=await res.json();
    renderMyRegister();
  }catch(err){
    console.error('My register failed:',err);
    toast('Could not load your register','error');
  }
}

function renderMyRegister(){
  const data=S.myRegister;
  if(!data) return;
  document.getElementById('myRegMonthLabel').textContent=monthLabel(data.month);
  document.getElementById('myRegWeekdays').innerHTML=
    ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d=>`<div>${d}</div>`).join('');

  const cells=[];
  for(let i=0;i<data.firstWeekday;i++) cells.push('<div class="cal-cell empty"></div>');
  data.days.forEach(d=>{
    const cell=data.cells[d];
    const meta=cell?REG_STATUS[cell.status]:null;
    const classes=['cal-cell'];
    if(meta) classes.push('cal-'+cell.status);
    if(d===data.today) classes.push('today');
    if(d>data.today) classes.push('future');
    if(cell?.isLate) classes.push('cal-late');
    const tip=cell
      ? `${meta?meta.full:cell.status}${cell.isLate?' · submitted late':''}${cell.hours?` · ${cell.hours}h`:''}${cell.adminNotes?` · "${cell.adminNotes}"`:''}`
      : (d>data.today?'Not yet':'Nothing recorded');
    cells.push(`<div class="${classes.join(' ')}" title="${tip}">
      <span class="cal-date">${Number(d.slice(8,10))}</span>
      ${meta?`<span class="cal-mark">${meta.label}</span>`:''}
    </div>`);
  });
  document.getElementById('myRegGrid').innerHTML=cells.join('');

  document.getElementById('myRegLegend').innerHTML=Object.entries(REG_STATUS).map(([,v])=>
    `<span class="rg-legend-item"><span class="rg-legend-swatch" style="background:${v.swatch}"></span>${v.full}</span>`
  ).join('');

  const order=['completed','gt','halfday','leave','emergency','fine','pending'];
  const rows=order.filter(s=>data.counts[s]).map(s=>{
    const m=REG_STATUS[s];
    return `<div class="cal-count-row">
      <span style="display:flex;align-items:center;gap:8px"><span class="rg-legend-swatch" style="background:${m.swatch}"></span>${m.full}</span>
      <strong>${data.counts[s]}</strong></div>`;
  }).join('');
  document.getElementById('myRegCounts').innerHTML=
    rows || '<div style="color:var(--text3);font-size:13px;text-align:center;padding:10px 0">Nothing recorded this month yet.</div>';

  const low=data.deposit<=0;
  document.getElementById('myRegDeposit').innerHTML=`
    <div style="font-family:var(--display);font-size:28px;font-weight:800;color:${low?'var(--error-dark)':'var(--text)'}">₹${data.deposit}</div>
    <div style="font-size:12.5px;color:var(--text2);margin-top:6px">
      ${data.finesThisMonth
        ? `${data.finesThisMonth} fine${data.finesThisMonth>1?'s':''} this month · <strong style="color:var(--error-dark)">−₹${data.deductedThisMonth}</strong>`
        : 'No fines this month 🎉'}
    </div>
    <div style="font-size:11.5px;color:var(--text3);margin-top:6px">Each fine costs ₹${data.fineAmount}.</div>`;

  document.getElementById('myRegAllowance').innerHTML=`
    <div class="cal-count-row"><span>🏖️ Leaves left</span><strong>${data.leavesRemaining}</strong></div>
    <div class="cal-count-row"><span>🟡 Half days left</span><strong>${data.halfDaysRemaining}</strong></div>
    <div class="cal-count-row"><span>🔥 Current streak</span><strong>${data.streak}</strong></div>
    <div style="font-size:11.5px;color:var(--text3);margin-top:8px">Emergency leave doesn't use your 3 leaves. Quotas reset on the 1st.</div>`;
}

// ===================== MONTHLY REGISTER =====================
// The spreadsheet replacement: students down the side, days across the top.
const REG_STATUS = {
  completed:{label:'✅', full:'Completed', cls:'rg-completed', swatch:'var(--st-completed-bg)'},
  gt:       {label:'GT', full:'Grand Test', cls:'rg-gt', swatch:'var(--st-gt-bg)'},
  halfday:  {label:'½',  full:'Half Day', cls:'rg-halfday', swatch:'var(--st-halfday-bg)'},
  leave:    {label:'L',  full:'Leave', cls:'rg-leave', swatch:'var(--st-leave-bg)'},
  emergency:{label:'🚑', full:'Emergency Leave', cls:'rg-emergency', swatch:'var(--st-emergency-bg)'},
  fine:     {label:'F',  full:'Fine', cls:'rg-fine', swatch:'var(--st-fine-bg)'},
  pending:  {label:'•',  full:'Awaiting review', cls:'rg-pending', swatch:'var(--st-pending-bg)'},
};
const REG_SETTABLE = ['completed','gt','halfday','leave','emergency','fine'];

S.register = null;
S.registerMonth = null;

function monthLabel(month){
  const [y,m]=month.split('-').map(Number);
  return new Date(y, m-1, 1).toLocaleDateString('en-GB',{month:'long',year:'numeric'});
}

function shiftRegisterMonth(delta){
  const [y,m]=(S.registerMonth||todayStr().slice(0,7)).split('-').map(Number);
  const d=new Date(y, m-1+delta, 1);
  S.registerMonth=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
  loadRegister();
}

async function loadRegister(){
  if(S.user?.role!=='admin') return;
  const month=S.registerMonth||todayStr().slice(0,7);
  S.registerMonth=month;
  try{
    const res=await fetch(`${API_URL}/admin/register?month=${month}`,{headers:{...authHeader()}});
    if(!res.ok){ toast('Could not load the register','error'); return; }
    S.register=await res.json();
    renderRegister();
  }catch(err){
    console.error('Register load failed:',err);
    toast('Could not load the register','error');
  }
}

function renderRegister(){
  const data=S.register;
  if(!data) return;
  document.getElementById('registerMonthLabel').textContent=monthLabel(data.month);

  const legend=document.getElementById('registerLegend');
  legend.innerHTML=Object.entries(REG_STATUS).map(([,v])=>
    `<span class="rg-legend-item"><span class="rg-legend-swatch" style="background:${v.swatch}"></span>${v.full}</span>`
  ).join('')+`<span class="rg-legend-item" style="margin-left:4px">Fine costs ₹${data.fineAmount} off the deposit</span>`;

  const empty=document.getElementById('registerEmpty');
  const table=document.getElementById('registerTable');
  if(!data.students.length){ empty.style.display='block'; table.style.display='none'; return; }
  empty.style.display='none'; table.style.display='';

  const dayNum=d=>Number(d.slice(8,10));
  const isWeekend=d=>{const x=new Date(d+'T00:00:00');return x.getDay()===0||x.getDay()===6;};

  document.getElementById('registerHead').innerHTML=`<tr>
    <th class="rg-name">Student</th>
    <th class="rg-meta">₹ Dep</th>
    <th class="rg-meta">Lv</th>
    <th class="rg-meta">½D</th>
    ${data.days.map(d=>`<th class="${d===data.today?'rg-today':''}${isWeekend(d)?' rg-weekend':''}" title="${d}">${dayNum(d)}</th>`).join('')}
  </tr>`;

  document.getElementById('registerBody').innerHTML=data.students.map(st=>{
    const type=st.studentType==='intern'?'Intern':'Full Time';
    const cells=data.days.map(d=>{
      const cell=st.cells[d];
      const future=d>data.today;
      const meta=cell?REG_STATUS[cell.status]:null;
      const classes=['rg-day'];
      if(d===data.today) classes.push('rg-today');
      else if(isWeekend(d)) classes.push('rg-weekend');
      if(cell?.isLate) classes.push('rg-late-dot');
      const inner=meta?`<span class="rg-chip ${meta.cls}">${meta.label}</span>`:'';
      const tip=cell
        ? `${st.name} · ${d} · ${meta?meta.full:cell.status}${cell.isLate?' (late)':''}`
        : `${st.name} · ${d} · nothing recorded`;
      const click=future?'':`onclick="openCellMenu(event,'${st.id}','${d}')"`;
      return `<td class="${classes.join(' ')}" style="${future?'cursor:default;opacity:.4':''}" title="${tip}" ${click}>${inner}</td>`;
    }).join('');
    const low=st.deposit<=0;
    return `<tr${st.isActive===false?' style="opacity:.5"':''}>
      <td class="rg-name" title="${st.email}">
        <div>${st.name}</div><div class="rg-sub">${type}</div>
      </td>
      <td class="rg-meta rg-deposit" style="${low?'color:var(--error-dark)':''}" title="Click to change the deposit"
          onclick="editDeposit('${st.id}','${(st.name||'').replace(/'/g,"\\'")}',${st.deposit})">₹${st.deposit}</td>
      <td class="rg-meta">${st.leavesRemaining}</td>
      <td class="rg-meta">${st.halfDaysRemaining}</td>
      ${cells}
    </tr>`;
  }).join('');
}

function openCellMenu(event, studentId, date){
  event.stopPropagation();
  const menu=document.getElementById('cellMenu');
  const student=S.register?.students.find(s=>s.id===studentId);
  const cell=student?.cells[date];

  menu.innerHTML=`
    <div style="font-size:11px;color:var(--text3);padding:4px 10px 8px;border-bottom:1px solid var(--border);margin-bottom:6px">
      ${student?student.name:''} · ${date}
    </div>
    ${REG_SETTABLE.map(s=>{
      const m=REG_STATUS[s];
      const active=cell?.status===s;
      return `<div class="cell-menu-item" onclick="setCellStatus('${studentId}','${date}','${s}')">
        <span class="rg-legend-swatch" style="background:${m.swatch}"></span>
        <span style="flex:1">${m.full}</span>
        ${active?'<span style="color:var(--primary-dark);font-weight:700">✓</span>':''}
      </div>`;
    }).join('')}
    ${cell?.hasScreenshots
      ? `<div class="cell-menu-item" style="border-top:1px solid var(--border);margin-top:6px;padding-top:10px"
             onclick="openVerifyFromRegister('${cell.submissionId}')">🖼 View screenshots</div>`
      : ''}`;

  menu.style.display='block';
  // Keep the popover on screen when the cell is near an edge.
  const r=event.currentTarget.getBoundingClientRect();
  const w=menu.offsetWidth, h=menu.offsetHeight;
  menu.style.left=`${Math.min(r.left, window.innerWidth-w-12)}px`;
  menu.style.top=`${r.bottom+h>window.innerHeight ? Math.max(8, r.top-h-4) : r.bottom+4}px`;
}

function closeCellMenu(){
  const menu=document.getElementById('cellMenu');
  if(menu) menu.style.display='none';
}
document.addEventListener('click', closeCellMenu);

async function setCellStatus(studentId, date, status){
  closeCellMenu();
  try{
    const res=await fetch(`${API_URL}/admin/register/mark`,{
      method:'POST',
      headers:{'Content-Type':'application/json',...authHeader()},
      body:JSON.stringify({userId:studentId, date, status}),
    });
    const data=await res.json();
    if(!res.ok){ toast(data.message||'Could not set that status','error'); return; }
    // Patch the row in place so the grid does not jump back to the top.
    const student=S.register.students.find(s=>s.id===studentId);
    if(student){
      student.cells[date]=data.cell;
      Object.assign(student, data.student);
    }
    renderRegister();
    toast(data.message,'success');
    fetchSubmissions().then(()=>{updatePendingBadge();renderAdminSubmissions();});
  }catch(err){
    console.error(err);
    toast('Network error','error');
  }
}

async function editDeposit(studentId, name, current){
  closeCellMenu();
  const raw=prompt(`Deposit for ${name} (in ₹):`, current);
  if(raw===null) return;
  const amount=parseInt(String(raw).replace(/[^0-9]/g,''),10);
  if(Number.isNaN(amount)){ toast('Enter a number','error'); return; }
  try{
    const res=await fetch(`${API_URL}/admin/user/${studentId}/deposit`,{
      method:'PUT',
      headers:{'Content-Type':'application/json',...authHeader()},
      body:JSON.stringify({amount}),
    });
    const data=await res.json();
    if(!res.ok){ toast(data.message||'Could not update the deposit','error'); return; }
    const student=S.register.students.find(s=>s.id===studentId);
    if(student) student.deposit=data.deposit;
    renderRegister();
    toast(data.message,'success');
  }catch(err){ toast('Network error','error'); }
}

function openVerifyFromRegister(submissionId){
  closeCellMenu();
  nav('admin-verify');
  setTimeout(()=>openVerifyModal(submissionId), 200);
}

// Same grid, as a file you can open in Excel or paste into a sheet.
function exportRegisterCsv(){
  const data=S.register;
  if(!data) return;
  const head=['Student','Type','Email','Deposit','Leaves Left','Half Days Left',
              ...data.days.map(d=>d.slice(8,10))];
  const rows=data.students.map(st=>[
    st.name, st.studentType==='intern'?'Intern':'Full Time', st.email,
    st.deposit, st.leavesRemaining, st.halfDaysRemaining,
    ...data.days.map(d=>{
      const c=st.cells[d];
      if(!c) return '';
      return (REG_STATUS[c.status]?.full||c.status)+(c.isLate?' (late)':'');
    }),
  ]);
  const esc=v=>`"${String(v??'').replace(/"/g,'""')}"`;
  const csv=[head,...rows].map(r=>r.map(esc).join(',')).join('\r\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');
  a.href=url; a.download=`register-${data.month}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
  toast('Register downloaded','success');
}

// The leaderboard only lists students with verified study this week, so the
// roster comes from the admin endpoint instead — otherwise a student who has
// just registered would be invisible here and could not be managed.
async function fetchAdminUsers(){
  if(S.user?.role!=='admin') return;
  try{
    const [rosterRes,pendingRes]=await Promise.all([
      fetch(`${API_URL}/admin/users`,{headers:{...authHeader()}}),
      fetch(`${API_URL}/admin/pending`,{headers:{...authHeader()}}),
    ]);
    if(rosterRes.ok) S.adminUsers=(await rosterRes.json()).users||[];
    if(pendingRes.ok) S.pendingUsers=(await pendingRes.json()).pending||[];
  }catch(err){
    console.error('Failed to fetch students:',err);
  }
}

function renderPendingApprovals(){
  const card=document.getElementById('pendingApprovalCard');
  const list=document.getElementById('pendingApprovalList');
  const badge=document.getElementById('approvalBadge');
  if(!card||!list) return;
  const pending=S.pendingUsers||[];

  if(badge){
    badge.textContent=pending.length;
    badge.style.display=pending.length?'':'none';
  }
  if(!pending.length){ card.style.display='none'; return; }

  card.style.display='';
  document.getElementById('pendingApprovalCount').textContent=
    `${pending.length} waiting`;
  list.innerHTML=pending.map(u=>{
    const safeName=(u.name||'').replace(/'/g,"\\'");
    const type=u.studentType==='intern'?'Intern':'Full-time aspirant';
    return `<div style="display:flex;align-items:center;gap:12px;padding:12px 14px;background:var(--bg);border-radius:10px;margin-bottom:8px">
      <div style="width:36px;height:36px;border-radius:9px;background:var(--warning);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;color:#fff;flex-shrink:0">${u.avatar||'?'}</div>
      <div style="min-width:0;flex:1">
        <div style="font-weight:600;color:var(--text)">${u.name}</div>
        <div style="font-size:12.5px;color:var(--text3);word-break:break-all">${u.email} · ${type}</div>
      </div>
      <button class="btn btn-primary btn-sm" onclick="approveStudent('${u.id}','${safeName}')">Approve</button>
      <button class="btn btn-danger btn-sm" onclick="rejectStudent('${u.id}','${safeName}')">Reject</button>
    </div>`;
  }).join('');
}

async function approveStudent(id,name){
  try{
    const res=await fetch(`${API_URL}/admin/user/${id}/approve`,{method:'PUT',headers:{...authHeader()}});
    const data=await res.json();
    if(!res.ok){ toast(data.message||'Could not approve','error'); return; }
    await fetchAdminUsers();
    renderPendingApprovals();
    renderAdminUsers();
    toast(`${name} approved`,'success');
  }catch(err){ toast('Network error','error'); }
}

async function rejectStudent(id,name){
  if(!confirm(`Reject ${name}? Their account will be deleted and they will need to register again.`)) return;
  try{
    const res=await fetch(`${API_URL}/admin/user/${id}`,{method:'DELETE',headers:{...authHeader()}});
    const data=await res.json();
    if(!res.ok){ toast(data.message||'Could not reject','error'); return; }
    await fetchAdminUsers();
    renderPendingApprovals();
    renderAdminUsers();
    toast(`${name} rejected`,'info');
  }catch(err){ toast('Network error','error'); }
}

function renderAdminUsers(){
  const tbody=document.getElementById('adminUsersTbody');
  if(!tbody) return;
  const students=S.adminUsers||[];
  if(!students.length){
    tbody.innerHTML='<tr><td colspan="8" style="text-align:center;color:var(--text3);padding:20px">No students yet. Share your join code, or use “+ Add Student”.</td></tr>';
    return;
  }
  tbody.innerHTML=students.map((u)=>{
    const uid=u.id;
    const avatar=u.avatar||(u.name?u.name[0].toUpperCase():'?');
    const today=u.todayStatus?.status;
    const safeName=(u.name||'').replace(/'/g,"\\'");
    return `<tr${u.isActive===false?' style="opacity:.55"':''}>
      <td><div style="display:flex;align-items:center;gap:10px"><div style="width:32px;height:32px;border-radius:8px;background:var(--fill-primary);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;color:var(--on-fill)">${avatar}</div><span style="font-weight:600;color:var(--text)">${u.name}</span></div></td>
      <td style="font-size:13px">${u.email||'—'}</td>
      <td style="font-family:var(--display);font-weight:600">${fmtHours(u.totalStudyHours||0)}</td>
      <td><span style="color:var(--warning-dark);font-weight:600">🔥 ${u.streak||0}d</span></td>
      <td><span style="color:var(--success-dark);font-weight:600">${u.totalCompleted||0}</span></td>
      <td><span style="color:var(--error-dark);font-weight:600">${u.totalFines||0}</span></td>
      <td>${today&&today!=='none'?renderStatusBadge(today):'<span class="pill pill-gray">Not submitted</span>'}</td>
      <td style="white-space:nowrap">
        <button class="btn btn-secondary btn-sm" onclick="resetStudentPassword('${uid}','${safeName}')">Reset Password</button>
        <button class="btn btn-danger btn-sm" onclick="removeUser('${uid}')">Remove</button>
      </td>
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
  S.adminUsers=(S.adminUsers||[]).filter(u=>u.id!==id);
  S.submissions=S.submissions.filter(s=>{const uid=s.userId?._id||s.userId; return uid!==id;});
  renderAdminUsers();
  renderLb();
  toast('Student removed','info');
}

async function openAddStudent(){
  const name=prompt('Student full name:');
  if(!name) return;
  const email=prompt('Student email:');
  if(!email) return;
  const studentType=confirm('Is this student an intern?\n\nOK = Intern, Cancel = Full-time aspirant')?'intern':'fulltime';
  try{
    const res=await fetch(`${API_URL}/admin/student`,{
      method:'POST',
      headers:{'Content-Type':'application/json',...authHeader()},
      body:JSON.stringify({name,email,studentType})
    });
    const data=await res.json();
    if(!res.ok){ toast(data.message||'Could not create student','error'); return; }
    alert(`${data.student.name} is ready.\n\nEmail: ${data.student.email}\nTemporary password: ${data.temporaryPassword}\n\nShare this with them now — it is not shown again.`);
    await fetchAdminUsers();
    renderPendingApprovals();
    renderAdminUsers();
    toast('Student added','success');
  }catch(err){ toast('Network error','error'); }
}

async function resetStudentPassword(id,name){
  if(!confirm(`Reset the password for ${name||'this student'}?`)) return;
  try{
    const res=await fetch(`${API_URL}/admin/user/${id}/password`,{
      method:'PUT',
      headers:{'Content-Type':'application/json',...authHeader()},
      body:JSON.stringify({})
    });
    const data=await res.json();
    if(!res.ok){ toast(data.message||'Could not reset password','error'); return; }
    alert(`New temporary password for ${name}:\n\n${data.temporaryPassword}\n\nShare this with them now — it is not shown again.`);
  }catch(err){ toast('Network error','error'); }
}

// The CSV endpoints need the auth header, so fetch the file and hand the browser
// a blob rather than pointing a plain link at the URL.
async function exportCsv(kind){
  try{
    const res=await fetch(`${API_URL}/admin/export/${kind}`,{headers:{...authHeader()}});
    if(!res.ok){ toast('Export failed','error'); return; }
    const blob=await res.blob();
    const name=(res.headers.get('Content-Disposition')||'').match(/filename="([^"]+)"/)?.[1]
      || `${kind}-${todayStr()}.csv`;
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url; a.download=name;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    toast('Download started','success');
  }catch(err){ toast('Export failed','error'); }
}

// ===================== CHARTS =====================
function initCharts(){
  // These plot the signed-in student's own hours, so there is nothing to draw
  // for an admin and the canvases are hidden anyway.
  if(S.user?.role==='admin') return;
  // Safe to call again after new data arrives; Chart.js refuses to reuse a canvas.
  Object.values(S.charts||{}).forEach(c=>{ try{ c.destroy(); }catch{} });
  S.charts={};
  const tc=themeToken('--text3'), gc=themeToken('--border');
  const hoursByDate=myHoursByDate();
  const wCtx=document.getElementById('weekChart').getContext('2d');
  // Last 7 days, oldest first, labelled by weekday.
  const weekDays=Array.from({length:7},(_,i)=>{
    const d=new Date(); d.setDate(d.getDate()-(6-i)); return d;
  });
  S.charts.week=new Chart(wCtx,{
    type:'bar',
    data:{
      labels:weekDays.map(d=>['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][d.getDay()]),
      datasets:[{data:weekDays.map(d=>+(hoursByDate[localDateStr(d)]||0).toFixed(1)),backgroundColor:'rgba(59,130,246,0.7)',borderRadius:6,borderSkipped:false}]
    },
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
      scales:{x:{grid:{display:false},ticks:{color:tc}},y:{grid:{color:gc},ticks:{color:tc,callback:v=>v+'h'},border:{dash:[3,3]}}}}
  });
  const sCtx=document.getElementById('subjectChart').getContext('2d');
  const myUid=S.user?._id||S.user?.id;
  const bySubject={};
  (S.submissions||[]).forEach(s=>{
    const subUid=s.userId?._id||s.userId;
    if(subUid!=null && String(subUid)!==String(myUid)) return;
    const name=s.subject||'Other';
    bySubject[name]=(bySubject[name]||0)+(s.hoursStudied||s.hours||0);
  });
  const subjectNames=Object.keys(bySubject).sort((a,b)=>bySubject[b]-bySubject[a]).slice(0,6);
  S.charts.subj=new Chart(sCtx,{
    type:'doughnut',
    data:{
      labels:subjectNames.length?subjectNames:['No data yet'],
      datasets:[{
        data:subjectNames.length?subjectNames.map(n=>+bySubject[n].toFixed(1)):[1],
        backgroundColor:['#3B82F6','#8B5CF6','#22C55E','#F59E0B','#EF4444','#14B8A6'],
        borderColor:themeToken('--white'),borderWidth:3,hoverOffset:6
      }]
    },
    options:{responsive:true,maintainAspectRatio:false,cutout:'70%',plugins:{legend:{position:'right',labels:{color:tc,boxWidth:10,padding:10}}}}
  });
  const tCtx=document.getElementById('trendChart').getContext('2d');
  const trendDays=Array.from({length:30},(_,i)=>{
    const d=new Date(); d.setDate(d.getDate()-(29-i)); return d;
  });
  S.charts.trend=new Chart(tCtx,{
    type:'line',
    data:{
      labels:trendDays.map((d,i)=>i===29?'Today':`${29-i}d`),
      datasets:[{data:trendDays.map(d=>+(hoursByDate[localDateStr(d)]||0).toFixed(1)),borderColor:'#3B82F6',backgroundColor:'rgba(59,130,246,0.06)',fill:true,tension:0.4,pointRadius:0,borderWidth:2}]
    },
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
  initTheme();
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
        return;
      }
      localStorage.removeItem('token');
    } catch(err){
      console.warn('Session restore failed:',err);
    }
  }
  initSignupMode();
})();