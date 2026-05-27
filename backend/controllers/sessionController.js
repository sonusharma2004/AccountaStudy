// controllers/sessionController.js — Study timer session management
const Session = require('../models/Session');
const User = require('../models/User');

const todayStr = () => new Date().toISOString().split('T')[0];

// ────────────────────────────────────────────
// @route   POST /api/session/start
// @access  Private
// @desc    Start a new study session
// ────────────────────────────────────────────
const startSession = async (req, res, next) => {
  try {
    const userId = req.user._id;
    const { subject } = req.body;

    if (!subject) {
      return res.status(400).json({ success: false, message: 'Subject is required.' });
    }

    // Check: no active session already running
    const activeSession = await Session.findOne({ userId, isActive: true });
    if (activeSession) {
      return res.status(409).json({
        success: false,
        message: 'You already have an active session. Stop it before starting a new one.',
        session: { id: activeSession._id, subject: activeSession.subject, startTime: activeSession.startTime },
      });
    }

    const session = await Session.create({
      userId,
      subject,
      startTime: new Date(),
      date: todayStr(),
      isActive: true,
    });

    res.status(201).json({
      success: true,
      message: `Session started for ${subject}. Stay focused!`,
      session: {
        id: session._id,
        subject: session.subject,
        startTime: session.startTime,
        date: session.date,
      },
    });
  } catch (error) {
    next(error);
  }
};

// ────────────────────────────────────────────
// @route   POST /api/session/stop
// @access  Private
// @desc    Stop the active session and save duration
// ────────────────────────────────────────────
const stopSession = async (req, res, next) => {
  try {
    const userId = req.user._id;
    const { sessionId } = req.body; // optional: specify which session to stop

    let session;
    if (sessionId) {
      session = await Session.findOne({ _id: sessionId, userId, isActive: true });
    } else {
      session = await Session.findOne({ userId, isActive: true });
    }

    if (!session) {
      return res.status(404).json({ success: false, message: 'No active session found.' });
    }

    const endTime = new Date();
    const durationSeconds = Math.floor((endTime - session.startTime) / 1000);
    const durationHours = durationSeconds / 3600;

    session.endTime = endTime;
    session.duration = durationSeconds;
    session.isActive = false;
    await session.save();

    // Update user's total study hours
    await User.findByIdAndUpdate(userId, {
      $inc: { totalStudyHours: durationHours },
      lastStudyDate: endTime,
    });

    res.json({
      success: true,
      message: 'Session completed!',
      session: {
        id: session._id,
        subject: session.subject,
        startTime: session.startTime,
        endTime: session.endTime,
        duration: durationSeconds,
        durationFormatted: formatDuration(durationSeconds),
        date: session.date,
      },
    });
  } catch (error) {
    next(error);
  }
};

// ────────────────────────────────────────────
// @route   GET /api/session/user
// @access  Private
// @desc    Get user's sessions (today or all)
// ────────────────────────────────────────────
const getUserSessions = async (req, res, next) => {
  try {
    const userId = req.user._id;
    const { date, limit = 20 } = req.query;

    const filter = { userId, isActive: false };
    if (date) filter.date = date;

    const sessions = await Session.find(filter)
      .sort({ startTime: -1 })
      .limit(parseInt(limit));

    // Today summary
    const today = todayStr();
    const todaySessions = sessions.filter((s) => s.date === today);
    const todayTotal = todaySessions.reduce((sum, s) => sum + s.duration, 0);

    // Active session (if any)
    const activeSession = await Session.findOne({ userId, isActive: true });

    res.json({
      success: true,
      active: activeSession
        ? {
            id: activeSession._id,
            subject: activeSession.subject,
            startTime: activeSession.startTime,
            elapsedSeconds: Math.floor((Date.now() - activeSession.startTime) / 1000),
          }
        : null,
      todaySummary: {
        totalSeconds: todayTotal,
        totalFormatted: formatDuration(todayTotal),
        sessionCount: todaySessions.length,
      },
      sessions: sessions.map((s) => ({
        id: s._id,
        subject: s.subject,
        startTime: s.startTime,
        endTime: s.endTime,
        duration: s.duration,
        durationFormatted: formatDuration(s.duration),
        date: s.date,
      })),
    });
  } catch (error) {
    next(error);
  }
};

// ── Format seconds to "Xh Ym" ──
const formatDuration = (seconds) => {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

module.exports = { startSession, stopSession, getUserSessions };
