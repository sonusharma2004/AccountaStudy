/**
 * End-to-end smoke test for AccountaStudy.
 * Exercises the full student + admin journey against a running backend.
 *
 * Usage: node scripts/e2e-test.js [baseUrl]
 */
const BASE = process.argv[2] || 'http://localhost:5001/api';

let pass = 0;
let fail = 0;

function check(name, ok, detail = '') {
  if (ok) {
    pass++;
    console.log(`  ✅ ${name}`);
  } else {
    fail++;
    console.log(`  ❌ ${name}${detail ? ' — ' + detail : ''}`);
  }
}

async function api(path, { method = 'GET', token, body, form } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body) headers['Content-Type'] = 'application/json';
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: form || (body ? JSON.stringify(body) : undefined),
  });
  let data = null;
  try { data = await res.json(); } catch (_) { /* non-json */ }
  return { status: res.status, data };
}

function pngBlob() {
  // Minimal valid 1x1 PNG
  const b64 =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
  return new Blob([Buffer.from(b64, 'base64')], { type: 'image/png' });
}

(async () => {
  console.log(`\n🧪 AccountaStudy End-to-End Test\n   Target: ${BASE}\n`);

  // ── 1. Health ──
  console.log('1. Health check');
  const health = await api('/health');
  check('GET /health returns 200', health.status === 200, `got ${health.status}`);
  check('database connected', health.data?.database === 'connected', `db=${health.data?.database}`);
  if (health.data?.database !== 'connected') {
    console.log('\n⛔ Database not connected — aborting remaining tests.\n');
    process.exit(1);
  }

  // ── 2. Registration ──
  console.log('\n2. Registration');
  const email = `e2e_${Date.now()}@school.edu`;
  const reg = await api('/auth/register', {
    method: 'POST',
    body: { name: 'E2E Tester', email, password: 'test1234', studentType: 'intern' },
  });
  check('register new student', reg.status === 201 && reg.data?.success, `status ${reg.status}`);
  check('returns JWT token', !!reg.data?.token);
  check('studentType saved as intern', reg.data?.user?.studentType === 'intern');
  check('starts with 3 leaves', reg.data?.user?.leavesRemaining === 3);
  check('starts with 3 half days', reg.data?.user?.halfDaysRemaining === 3);

  const dupe = await api('/auth/register', {
    method: 'POST',
    body: { name: 'Dupe', email, password: 'test1234' },
  });
  check('duplicate email rejected (409)', dupe.status === 409, `got ${dupe.status}`);

  // ── 3. Login ──
  console.log('\n3. Login');
  const login = await api('/auth/login', {
    method: 'POST',
    body: { email, password: 'test1234' },
  });
  check('login succeeds', login.status === 200 && login.data?.success);
  const token = login.data?.token;
  check('token issued', !!token);

  const badLogin = await api('/auth/login', {
    method: 'POST',
    body: { email, password: 'wrongpass' },
  });
  check('wrong password rejected (401)', badLogin.status === 401, `got ${badLogin.status}`);

  const noAuth = await api('/auth/me');
  check('protected route blocked without token (401)', noAuth.status === 401, `got ${noAuth.status}`);

  // ── 4. Profile ──
  console.log('\n4. Profile');
  const me = await api('/auth/me', { token });
  check('GET /auth/me returns profile', me.status === 200 && me.data?.user?.email === email);
  check('password never exposed', !JSON.stringify(me.data).includes('password'));

  // ── 5. Study timer ──
  console.log('\n5. Study timer session');
  const start = await api('/session/start', {
    method: 'POST', token, body: { subject: 'Programming' },
  });
  check('start session', start.status === 201 && start.data?.success, `status ${start.status}`);

  const restart = await api('/session/start', {
    method: 'POST', token, body: { subject: 'Physics' },
  });
  check('restart auto-closes orphaned session (no 409)', restart.status === 201, `got ${restart.status}`);

  await new Promise((r) => setTimeout(r, 1200));
  const stop = await api('/session/stop', { method: 'POST', token });
  check('stop session', stop.status === 200 && stop.data?.success);
  check('duration recorded', (stop.data?.session?.duration ?? 0) >= 1, `duration=${stop.data?.session?.duration}`);

  const sessions = await api('/session/user', { token });
  check('sessions listed', sessions.status === 200 && Array.isArray(sessions.data?.sessions));
  check('today summary present', !!sessions.data?.todaySummary);

  // ── 6. Submission with screenshots ──
  console.log('\n6. Daily proof submission');
  const fd = new FormData();
  fd.append('subject', 'Programming');
  fd.append('hoursStudied', '3.5');
  fd.append('notes', 'E2E automated test submission');
  fd.append('submissionType', 'full');
  fd.append('timerScreenshot', pngBlob(), 'timer.png');
  fd.append('questionScreenshot', pngBlob(), 'questions.png');
  const upload = await api('/submission/upload', { method: 'POST', token, form: fd });
  check('upload submission with 2 screenshots', upload.status === 201 && upload.data?.success, `status ${upload.status} ${upload.data?.message || ''}`);
  check('timer screenshot path returned', !!upload.data?.submission?.timerScreenshot);
  check('status defaults to pending', upload.data?.submission?.status === 'pending');

  const mySubs = await api('/submission/my', { token });
  check('submission history returns record', mySubs.status === 200 && mySubs.data?.total >= 1);

  const todayStatus = await api('/submission/today-status', { token });
  check('today-status shows submitted', todayStatus.data?.submitted === true);

  // ── 7. Static screenshot serving ──
  console.log('\n7. Screenshot static serving');
  const shotPath = upload.data?.submission?.timerScreenshot;
  if (shotPath) {
    const origin = BASE.replace(/\/api$/, '');
    const img = await fetch(origin + shotPath);
    check('uploaded screenshot is publicly served', img.status === 200, `HTTP ${img.status}`);
  } else {
    check('uploaded screenshot is publicly served', false, 'no path returned');
  }

  // ── 8. Leaderboard ──
  console.log('\n8. Leaderboard');
  for (const mode of ['daily', 'weekly', 'overall']) {
    const lb = await api(`/leaderboard?mode=${mode}`, { token });
    check(`leaderboard mode=${mode}`, lb.status === 200 && Array.isArray(lb.data?.leaderboard), `status ${lb.status}`);
  }

  // ── 9. Admin access control ──
  console.log('\n9. Admin access control');
  const forbidden = await api('/submission/all', { token });
  check('student blocked from admin route (403)', forbidden.status === 403, `got ${forbidden.status}`);

  const adminLogin = await api('/auth/login', {
    method: 'POST', body: { email: 'admin@school.edu', password: 'admin123' },
  });
  check('admin login', adminLogin.status === 200 && adminLogin.data?.user?.role === 'admin');
  const adminToken = adminLogin.data?.token;

  // ── 10. Admin verification ──
  console.log('\n10. Admin verification');
  const all = await api('/submission/all?limit=200', { token: adminToken });
  check('admin lists submissions', all.status === 200 && Array.isArray(all.data?.submissions));

  const target = all.data?.submissions?.find((s) => s.student?.email === email);
  check('new submission visible to admin', !!target);

  if (target) {
    const verify = await api('/submission/verify', {
      method: 'POST', token: adminToken,
      body: { submissionId: target.id, status: 'completed', adminNotes: 'E2E verified' },
    });
    check('verify as completed', verify.status === 200 && verify.data?.success, verify.data?.message);
    check('streak incremented to 1', verify.data?.studentUpdated?.streak === 1, `streak=${verify.data?.studentUpdated?.streak}`);
    check('points awarded 100', verify.data?.studentUpdated?.points === 100, `points=${verify.data?.studentUpdated?.points}`);

    const reverify = await api('/submission/verify', {
      method: 'POST', token: adminToken,
      body: { submissionId: target.id, status: 'fine', adminNotes: 'E2E re-verify' },
    });
    check('re-verify to fine works', reverify.status === 200);
    check('streak reset to 0 on fine', reverify.data?.studentUpdated?.streak === 0, `streak=${reverify.data?.studentUpdated?.streak}`);
  }

  // ── 11. Admin dashboards ──
  console.log('\n11. Admin dashboards');
  const users = await api('/admin/users', { token: adminToken });
  check('admin users list', users.status === 200 && users.data?.total > 0);
  const stats = await api('/admin/stats', { token: adminToken });
  check('admin system stats', stats.status === 200 && !!stats.data?.stats);
  const analytics = await api('/admin/analytics?days=30', { token: adminToken });
  check('admin analytics', analytics.status === 200 && Array.isArray(analytics.data?.dailyTrend));

  // ── 12. Validation guards ──
  console.log('\n12. Validation guards');
  // Fresh account: the earlier one already has a verified submission for today,
  // which correctly short-circuits with 409 before subject validation runs.
  const freshEmail = `e2e_val_${Date.now()}@school.edu`;
  const freshReg = await api('/auth/register', {
    method: 'POST',
    body: { name: 'E2E Validation', email: freshEmail, password: 'test1234' },
  });
  const freshToken = freshReg.data?.token;

  const badSubject = new FormData();
  badSubject.append('subject', 'Astrology');
  badSubject.append('hoursStudied', '2');
  badSubject.append('timerScreenshot', pngBlob(), 't.png');
  badSubject.append('questionScreenshot', pngBlob(), 'q.png');
  const invalid = await api('/submission/upload', { method: 'POST', token: freshToken, form: badSubject });
  check('invalid subject rejected (400)', invalid.status === 400, `got ${invalid.status}`);

  const missingShots = new FormData();
  missingShots.append('subject', 'Physics');
  missingShots.append('hoursStudied', '2');
  const noShots = await api('/submission/upload', { method: 'POST', token: freshToken, form: missingShots });
  check('missing screenshots rejected (400)', noShots.status === 400, `got ${noShots.status}`);

  const leaveFd = new FormData();
  leaveFd.append('subject', 'Other');
  leaveFd.append('hoursStudied', '0.5');
  leaveFd.append('submissionType', 'leave');
  const leave = await api('/submission/upload', { method: 'POST', token: freshToken, form: leaveFd });
  check('leave submission without screenshots accepted', leave.status === 201, `got ${leave.status}`);

  const afterLeave = await api('/auth/me', { token: freshToken });
  check('leave allowance deducted to 2', afterLeave.data?.user?.leavesRemaining === 2, `left=${afterLeave.data?.user?.leavesRemaining}`);

  const notFound = await api('/does-not-exist');
  check('unknown route returns 404', notFound.status === 404, `got ${notFound.status}`);

  // ── Summary ──
  console.log('\n' + '═'.repeat(50));
  console.log(`   RESULT: ${pass} passed, ${fail} failed`);
  console.log('═'.repeat(50) + '\n');
  process.exit(fail === 0 ? 0 : 1);
})().catch((err) => {
  console.error('\n💥 Test run crashed:', err.message);
  process.exit(1);
});
