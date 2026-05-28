// controllers/submissionController.js — Daily proof submission logic
const Submission = require('../models/Submission');
const User = require('../models/User');
const path = require('path');

// ── Helper: today's date string ──
const todayStr = () => new Date().toISOString().split('T')[0];

// ── Points per status ──
const STATUS_POINTS = { completed: 100, halfday: 40, leave: 0, fine: -20 };

// ────────────────────────────────────────────
// @route   POST /api/submission/upload
// @access  Private (student)
// @desc    Upload daily proof with 2 screenshots
// ────────────────────────────────────────────
const uploadSubmission = async (req, res, next) => {
  try {
    const userId = req.user._id;
    const today = todayStr();

    // Check if already submitted today
    const existing = await Submission.findOne({ userId, date: today });
    if (existing && existing.isVerified) {
      return res.status(409).json({
        success: false,
        message: 'Already submitted and verified for today. Cannot resubmit.',
      });
    }

    const { subject, hoursStudied, notes, submissionType } = req.body;
    const isLeave = submissionType === 'leave';
    const isHalfDay = submissionType === 'halfday';

    // For leave submissions, skip screenshot validation
    if (!isLeave) {
      if (!req.files || !req.files.timerScreenshot || !req.files.questionScreenshot) {
        return res.status(400).json({
          success: false,
          message: 'Both timer screenshot and question screenshot are required.',
        });
      }
    }

    // Check leave/halfday allowance
    const student = await User.findById(userId);
    if (isLeave && student.leavesRemaining <= 0) {
      return res.status(400).json({ success: false, message: 'No leaves remaining. You have used all 3 leaves.' });
    }
    if (isHalfDay && student.halfDaysRemaining <= 0) {
      return res.status(400).json({ success: false, message: 'No half days remaining. You have used all 3 half days.' });
    }

    if (!subject || !hoursStudied) {
      return res.status(400).json({
        success: false,
        message: 'Subject and hours studied are required.',
      });
    }

    const timerFile = isLeave ? null : req.files?.timerScreenshot?.[0];
    const questionFile = isLeave ? null : req.files?.questionScreenshot?.[0];

    // Relative paths for storage (served statically)
    const timerPath = isLeave ? 'leave/placeholder.jpg' : `timer/${timerFile.filename}`;
    const questionPath = isLeave ? 'leave/placeholder.jpg' : `questions/${questionFile.filename}`;

    let submission;

    if (existing) {
      // Update the pending submission (resubmission before verification)
      existing.subject = subject;
      existing.hoursStudied = parseFloat(hoursStudied);
      existing.notes = notes || '';
      existing.timerScreenshot = timerPath;
      existing.questionScreenshot = questionPath;
      existing.status = 'pending';
      existing.isVerified = false;
      await existing.save();
      submission = existing;
    } else {
      // Create new submission
      submission = await Submission.create({
        userId,
        date: today,
        subject,
        hoursStudied: parseFloat(hoursStudied),
        notes: notes || '',
        timerScreenshot: timerPath,
        questionScreenshot: questionPath,
      });
    }

    // Update user's totalStudyHours and deduct leave/halfday if applicable
    const userUpdate = {
      $inc: { totalStudyHours: parseFloat(hoursStudied) },
      lastStudyDate: new Date(),
    };
    if (isLeave && !existing) userUpdate.$inc.leavesRemaining = -1;
    if (isHalfDay && !existing) userUpdate.$inc.halfDaysRemaining = -1;
    await User.findByIdAndUpdate(userId, userUpdate);

    res.status(201).json({
      success: true,
      message: 'Proof submitted successfully! Admin will verify soon.',
      submission: {
        id: submission._id,
        date: submission.date,
        subject: submission.subject,
        hoursStudied: submission.hoursStudied,
        status: submission.status,
        timerScreenshot: `/uploads/${timerPath}`,
        questionScreenshot: `/uploads/${questionPath}`,
        submittedAt: submission.createdAt,
      },
    });
  } catch (error) {
    next(error);
  }
};

// ────────────────────────────────────────────
// @route   GET /api/submission/all
// @access  Private (admin)
// @desc    Get all submissions with student info + filters
// ────────────────────────────────────────────
const getAllSubmissions = async (req, res, next) => {
  try {
    const { status, date, page = 1, limit = 20 } = req.query;

    // Build query filters
    const filter = {};
    if (status && status !== 'all') filter.status = status;
    if (date) filter.date = date;

    const skip = (parseInt(page) - 1) * parseInt(limit);

    const [submissions, total] = await Promise.all([
      Submission.find(filter)
        .populate('userId', 'name email avatar streak totalStudyHours')
        .populate('verifiedBy', 'name')
        .sort({ date: -1, createdAt: -1 })
        .skip(skip)
        .limit(parseInt(limit)),
      Submission.countDocuments(filter),
    ]);

    // Count pending
    const pendingCount = await Submission.countDocuments({ status: 'pending' });

    // Format response — add full URL to screenshots
    const formatted = submissions.map((s) => ({
      id: s._id,
      student: s.userId
        ? {
            id: s.userId._id,
            name: s.userId.name,
            email: s.userId.email,
            avatar: s.userId.avatar,
            streak: s.userId.streak,
          }
        : null,
      date: s.date,
      subject: s.subject,
      hoursStudied: s.hoursStudied,
      notes: s.notes,
      timerScreenshot: s.timerScreenshot ? `/uploads/${s.timerScreenshot}` : null,
      questionScreenshot: s.questionScreenshot ? `/uploads/${s.questionScreenshot}` : null,
      status: s.status,
      adminNotes: s.adminNotes,
      isVerified: s.isVerified,
      verifiedBy: s.verifiedBy?.name || null,
      verifiedAt: s.verifiedAt,
      submittedAt: s.createdAt,
    }));

    res.json({
      success: true,
      pendingCount,
      total,
      page: parseInt(page),
      pages: Math.ceil(total / parseInt(limit)),
      submissions: formatted,
    });
  } catch (error) {
    next(error);
  }
};

// ────────────────────────────────────────────
// @route   POST /api/submission/verify
// @access  Private (admin)
// @desc    Admin sets status on a submission
// ────────────────────────────────────────────
const verifySubmission = async (req, res, next) => {
  try {
    const { submissionId, status, adminNotes } = req.body;

    if (!submissionId || !status) {
      return res.status(400).json({ success: false, message: 'submissionId and status are required.' });
    }

    const validStatuses = ['completed', 'halfday', 'leave', 'fine'];
    if (!validStatuses.includes(status)) {
      return res.status(400).json({
        success: false,
        message: `Invalid status. Must be one of: ${validStatuses.join(', ')}`,
      });
    }

    const submission = await Submission.findById(submissionId);
    if (!submission) {
      return res.status(404).json({ success: false, message: 'Submission not found.' });
    }

    const previousStatus = submission.status;

    // Update submission
    submission.status = status;
    submission.adminNotes = adminNotes || '';
    submission.verifiedBy = req.user._id;
    submission.verifiedAt = new Date();
    submission.isVerified = true;
    await submission.save(); // triggers pre-save for points

    // ── Update Student Stats ──
    const student = await User.findById(submission.userId);
    if (student) {
      // Undo previous status effect (if reVerifying)
      if (previousStatus !== 'pending' && previousStatus !== status) {
        if (previousStatus === 'completed') {
          student.totalCompleted = Math.max(0, student.totalCompleted - 1);
          student.streak = Math.max(0, student.streak - 1);
          student.points = Math.max(0, student.points - STATUS_POINTS.completed);
        } else if (previousStatus === 'halfday') {
          student.totalHalfDay = Math.max(0, student.totalHalfDay - 1);
          student.points = Math.max(0, student.points - STATUS_POINTS.halfday);
        } else if (previousStatus === 'fine') {
          student.totalFines = Math.max(0, student.totalFines - 1);
          student.streak = Math.min(student.streak + 1, student.longestStreak);
          student.points += 20; // undo fine deduction
        }
      }

      // Apply new status
      if (previousStatus !== status) {
        if (status === 'completed') {
          student.totalCompleted += 1;
          student.streak += 1;
          student.points += STATUS_POINTS.completed;
        } else if (status === 'halfday') {
          student.totalHalfDay += 1;
          student.streak += 1; // halfday still maintains streak
          student.points += STATUS_POINTS.halfday;
        } else if (status === 'leave') {
          student.totalLeave += 1;
          // Leave doesn't affect streak
        } else if (status === 'fine') {
          student.totalFines += 1;
          student.streak = 0; // Streak broken
          student.points = Math.max(0, student.points + STATUS_POINTS.fine);
        }

        // Update longest streak
        if (student.streak > student.longestStreak) {
          student.longestStreak = student.streak;
        }
      }

      await student.save();
    }

    res.json({
      success: true,
      message: `Submission verified as "${status}" for ${student?.name || 'student'}.`,
      submission: {
        id: submission._id,
        status: submission.status,
        adminNotes: submission.adminNotes,
        pointsAwarded: submission.pointsAwarded,
        verifiedAt: submission.verifiedAt,
      },
      studentUpdated: {
        streak: student?.streak,
        points: student?.points,
        totalCompleted: student?.totalCompleted,
        totalFines: student?.totalFines,
      },
    });
  } catch (error) {
    next(error);
  }
};

// ────────────────────────────────────────────
// @route   GET /api/submission/my
// @access  Private (student)
// @desc    Get current student's submission history
// ────────────────────────────────────────────
const getMySubmissions = async (req, res, next) => {
  try {
    const { limit = 30 } = req.query;

    const submissions = await Submission.find({ userId: req.user._id })
      .sort({ date: -1 })
      .limit(parseInt(limit));

    const today = todayStr();
    const todaySubmission = submissions.find((s) => s.date === today);

    const formatted = submissions.map((s) => ({
      id: s._id,
      date: s.date,
      subject: s.subject,
      hoursStudied: s.hoursStudied,
      notes: s.notes,
      timerScreenshot: s.timerScreenshot ? `/uploads/${s.timerScreenshot}` : null,
      questionScreenshot: s.questionScreenshot ? `/uploads/${s.questionScreenshot}` : null,
      status: s.status,
      adminNotes: s.adminNotes,
      isVerified: s.isVerified,
      pointsAwarded: s.pointsAwarded,
      submittedAt: s.createdAt,
      verifiedAt: s.verifiedAt,
    }));

    res.json({
      success: true,
      today: todaySubmission
        ? { submitted: true, status: todaySubmission.status, isVerified: todaySubmission.isVerified }
        : { submitted: false },
      total: formatted.length,
      submissions: formatted,
    });
  } catch (error) {
    next(error);
  }
};

// ────────────────────────────────────────────
// @route   GET /api/submission/today-status
// @access  Private
// @desc    Quick check: has the logged-in student submitted today?
// ────────────────────────────────────────────
const getTodayStatus = async (req, res, next) => {
  try {
    const today = todayStr();
    const submission = await Submission.findOne({ userId: req.user._id, date: today });

    if (!submission) {
      return res.json({ success: true, submitted: false, status: null });
    }

    res.json({
      success: true,
      submitted: true,
      status: submission.status,
      isVerified: submission.isVerified,
      hoursStudied: submission.hoursStudied,
      subject: submission.subject,
      adminNotes: submission.adminNotes,
      timerScreenshot: submission.timerScreenshot ? `/uploads/${submission.timerScreenshot}` : null,
      questionScreenshot: submission.questionScreenshot ? `/uploads/${submission.questionScreenshot}` : null,
    });
  } catch (error) {
    next(error);
  }
};

module.exports = {
  uploadSubmission,
  getAllSubmissions,
  verifySubmission,
  getMySubmissions,
  getTodayStatus,
};
