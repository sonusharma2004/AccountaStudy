// scripts/seed.js — Seed database with realistic test data for 3 days of testing
require('dotenv').config({ path: require('path').join(__dirname, '../.env') });
const mongoose = require('mongoose');

// Connect
mongoose.connect(process.env.MONGODB_URI || 'mongodb://localhost:27017/accountastudy')
  .then(() => console.log('✅ Connected to MongoDB for seeding...'))
  .catch(err => { console.error('❌ DB Error:', err.message); process.exit(1); });

const User = require('../models/User');
const Submission = require('../models/Submission');
const Session = require('../models/Session');

// ── Helper: date string N days ago ──
const daysAgo = (n) => {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().split('T')[0];
};

// ── Helper: random float in range ──
const rand = (min, max) => parseFloat((Math.random() * (max - min) + min).toFixed(1));

const seed = async () => {
  try {
    console.log('\n🧹 Clearing existing data...');
    await Promise.all([
      User.deleteMany({}),
      Submission.deleteMany({}),
      Session.deleteMany({}),
    ]);
    console.log('   ✓ Cleared users, submissions, sessions');

    // ══════════════════════════════════════════
    // CREATE USERS
    // ══════════════════════════════════════════
    console.log('\n👤 Creating users...');

    const usersData = [
      // Admin
      {
        name: 'Admin Sir',
        email: 'admin@school.edu',
        password: 'admin123',
        role: 'admin',
        avatar: 'AS',
      },
      // Students
      {
        name: 'Priya Sharma',
        email: 'priya@school.edu',
        password: 'pass123',
        role: 'student',
        studentType: 'fulltime',
        avatar: 'PS',
        totalStudyHours: 142.5,
        streak: 7,
        longestStreak: 12,
        totalCompleted: 18,
        totalHalfDay: 3,
        totalLeave: 1,
        totalFines: 2,
        points: 1900,
        leavesRemaining: 2,
        halfDaysRemaining: 0,
      },
      {
        name: 'Arjun Mehta',
        email: 'arjun@school.edu',
        password: 'pass123',
        role: 'student',
        studentType: 'intern',
        avatar: 'AM',
        totalStudyHours: 198.0,
        streak: 12,
        longestStreak: 15,
        totalCompleted: 24,
        totalHalfDay: 2,
        totalLeave: 0,
        totalFines: 1,
        points: 2460,
        leavesRemaining: 3,
        halfDaysRemaining: 1,
      },
      {
        name: 'Sneha Iyer',
        email: 'sneha@school.edu',
        password: 'pass123',
        role: 'student',
        studentType: 'fulltime',
        avatar: 'SI',
        totalStudyHours: 167.8,
        streak: 9,
        longestStreak: 11,
        totalCompleted: 20,
        totalHalfDay: 4,
        totalLeave: 2,
        totalFines: 3,
        points: 2140,
        leavesRemaining: 1,
        halfDaysRemaining: 0,
      },
      {
        name: 'Rahul Gupta',
        email: 'rahul@school.edu',
        password: 'pass123',
        role: 'student',
        studentType: 'intern',
        avatar: 'RG',
        totalStudyHours: 133.4,
        streak: 5,
        longestStreak: 8,
        totalCompleted: 16,
        totalHalfDay: 5,
        totalLeave: 1,
        totalFines: 5,
        points: 1750,
        leavesRemaining: 2,
        halfDaysRemaining: 0,
      },
      {
        name: 'Kavya Nair',
        email: 'kavya@school.edu',
        password: 'pass123',
        role: 'student',
        studentType: 'fulltime',
        avatar: 'KN',
        totalStudyHours: 112.9,
        streak: 3,
        longestStreak: 6,
        totalCompleted: 12,
        totalHalfDay: 4,
        totalLeave: 3,
        totalFines: 4,
        points: 1380,
        leavesRemaining: 0,
        halfDaysRemaining: 0,
      },
      // Test account — for easy login during development
      {
        name: 'Test Student',
        email: 'student@school.edu',
        password: 'pass123',
        role: 'student',
        studentType: 'fulltime',
        avatar: 'TS',
        totalStudyHours: 45.0,
        streak: 2,
        longestStreak: 5,
        totalCompleted: 5,
        totalHalfDay: 1,
        totalLeave: 0,
        totalFines: 1,
        points: 540,
        leavesRemaining: 3,
        halfDaysRemaining: 2,
      },
    ];

    const createdUsers = await User.create(usersData);
    const admin = createdUsers.find(u => u.role === 'admin');
    const students = createdUsers.filter(u => u.role === 'student');
    console.log(`   ✓ Created ${createdUsers.length} users (1 admin, ${students.length} students)`);

    // ══════════════════════════════════════════
    // CREATE SUBMISSIONS (past 3 days + today)
    // ══════════════════════════════════════════
    console.log('\n📸 Creating submissions for past 3 days...');

    const subjects = ['Mathematics', 'Physics', 'Chemistry', 'Biology', 'Programming', 'History'];
    const notesPool = [
      'Covered chapters 4-6. Solved 45 practice questions. Feeling confident about the exam.',
      'Studied integration by parts and solved 30 problems. Need to revise again tomorrow.',
      'Completed Newton\'s laws problems. Got stuck on circular motion but resolved it.',
      'Finished organic chemistry mechanisms. Drew 20 reaction pathways.',
      'Built 2 mini-projects in Python. Practised DSA problems on LeetCode.',
      'Revised World War 2 timeline. Made detailed notes with maps.',
      'Solved past papers from 2019-2022. Marked weak areas for revision.',
      'Group study session. Cleared doubts on thermodynamics with classmates.',
    ];

    // Status patterns for variety: day -3, -2, -1, today(pending)
    const studentStatusPatterns = [
      //           D-3          D-2          D-1         Today
      ['completed', 'completed', 'completed', 'pending'],  // Priya
      ['completed', 'halfday',   'completed', 'pending'],  // Arjun
      ['completed', 'completed', 'halfday',   'pending'],  // Sneha
      ['halfday',   'fine',      'completed', 'pending'],  // Rahul
      ['leave',     'completed', 'fine',      'pending'],  // Kavya
      ['fine',      'completed', 'completed', 'pending'],  // Test Student
    ];

    const submissionsToCreate = [];
    const sessionsToCreate = [];

    students.forEach((student, si) => {
      const pattern = studentStatusPatterns[si] || ['completed', 'completed', 'halfday', 'pending'];

      // Days -3 to today (0)
      [3, 2, 1, 0].forEach((daysBack, pi) => {
        const dateStr = daysAgo(daysBack);
        const status = pattern[pi];
        const hours = status === 'fine' ? 0.5 : status === 'halfday' ? rand(1.5, 3) : rand(3.5, 8);
        const subject = subjects[Math.floor(Math.random() * subjects.length)];

        submissionsToCreate.push({
          userId: student._id,
          date: dateStr,
          subject,
          hoursStudied: hours,
          notes: status === 'fine' ? '' : notesPool[Math.floor(Math.random() * notesPool.length)],
          timerScreenshot: status === 'fine' ? 'timer/placeholder.jpg' : `timer/seed_${student._id}_${dateStr}.jpg`,
          questionScreenshot: status === 'fine' ? 'questions/placeholder.jpg' : `questions/seed_${student._id}_${dateStr}.jpg`,
          status: daysBack === 0 ? 'pending' : status,  // Today = pending, others = verified
          isVerified: daysBack > 0,
          verifiedBy: daysBack > 0 ? admin._id : null,
          verifiedAt: daysBack > 0 ? new Date(Date.now() - daysBack * 86400000 + 7200000) : null,
          adminNotes: status === 'fine'
            ? 'No submission received. Fine applied.'
            : status === 'halfday'
            ? 'Partial work submitted. Half day assigned.'
            : '',
          pointsAwarded: { completed: 100, halfday: 40, leave: 0, fine: -20, pending: 0 }[
            daysBack === 0 ? 'pending' : status
          ],
        });

        // Create sessions for completed/halfday days
        if (status !== 'fine' && status !== 'leave') {
          const sessionCount = status === 'halfday' ? 1 : Math.floor(Math.random() * 2) + 1;
          const sessionDate = new Date(dateStr);

          for (let s = 0; s < sessionCount; s++) {
            const startHour = 9 + s * 3;
            const startTime = new Date(sessionDate);
            startTime.setHours(startHour, Math.floor(Math.random() * 30), 0);
            const durationSecs = Math.floor((hours / sessionCount) * 3600);
            const endTime = new Date(startTime.getTime() + durationSecs * 1000);

            sessionsToCreate.push({
              userId: student._id,
              subject,
              startTime,
              endTime,
              duration: durationSecs,
              isActive: false,
              date: dateStr,
            });
          }
        }
      });
    });

    await Submission.create(submissionsToCreate);
    console.log(`   ✓ Created ${submissionsToCreate.length} submissions`);

    await Session.create(sessionsToCreate);
    console.log(`   ✓ Created ${sessionsToCreate.length} sessions`);

    // ══════════════════════════════════════════
    // SUMMARY
    // ══════════════════════════════════════════
    console.log('\n' + '═'.repeat(50));
    console.log('✅ SEED COMPLETE — Test Data Ready');
    console.log('═'.repeat(50));
    console.log('\n🔑 LOGIN CREDENTIALS:');
    console.log('┌────────────────────────────────────────────┐');
    console.log('│  ADMIN                                     │');
    console.log('│  Email:    admin@school.edu                │');
    console.log('│  Password: admin123                        │');
    console.log('├────────────────────────────────────────────┤');
    console.log('│  STUDENT (main test account)               │');
    console.log('│  Email:    student@school.edu              │');
    console.log('│  Password: pass123                         │');
    console.log('├────────────────────────────────────────────┤');
    console.log('│  OTHER STUDENTS (all password: pass123)    │');
    console.log('│  priya@school.edu  |  arjun@school.edu     │');
    console.log('│  sneha@school.edu  |  rahul@school.edu     │');
    console.log('│  kavya@school.edu                          │');
    console.log('└────────────────────────────────────────────┘');
    console.log('\n📊 Data created:');
    console.log(`  • ${students.length} students + 1 admin`);
    console.log(`  • ${submissionsToCreate.length} submissions (3 days history + today pending)`);
    console.log(`  • ${sessionsToCreate.length} study sessions`);
    console.log('\n🚀 Start backend: npm run dev\n');

    process.exit(0);
  } catch (err) {
    console.error('\n❌ Seed failed:', err.message);
    console.error(err);
    process.exit(1);
  }
};

seed();
