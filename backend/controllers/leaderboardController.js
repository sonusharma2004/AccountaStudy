// controllers/leaderboardController.js — Rankings
const User = require('../models/User');
const Submission = require('../models/Submission');
const Session = require('../models/Session');

// ── Get date range helpers ──
const getDateRange = (mode) => {
  const now = new Date();
  const today = now.toISOString().split('T')[0];

  if (mode === 'daily') {
    return { start: today, end: today };
  }
  if (mode === 'weekly') {
    const start = new Date(now);
    start.setDate(now.getDate() - now.getDay()); // Sunday
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    return {
      start: start.toISOString().split('T')[0],
      end: end.toISOString().split('T')[0],
    };
  }
  // overall — no range filter
  return null;
};

// ────────────────────────────────────────────
// @route   GET /api/leaderboard
// @access  Private
// @desc    Get leaderboard (daily | weekly | overall)
// ────────────────────────────────────────────
const getLeaderboard = async (req, res, next) => {
  try {
    const { mode = 'weekly' } = req.query;
    const range = getDateRange(mode);

    let rankData;

    if (mode === 'overall') {
      // Overall: rank by totalStudyHours
      rankData = await User.find({ role: 'student', isActive: true })
        .select('name email avatar streak longestStreak totalStudyHours totalCompleted totalFines points createdAt')
        .sort({ totalStudyHours: -1, points: -1 });

      rankData = rankData.map((u, i) => ({
        rank: i + 1,
        userId: u._id,
        name: u.name,
        email: u.email,
        avatar: u.avatar || u.name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase(),
        streak: u.streak,
        longestStreak: u.longestStreak,
        totalHours: parseFloat(u.totalStudyHours.toFixed(2)),
        totalCompleted: u.totalCompleted,
        totalFines: u.totalFines,
        points: u.points,
      }));
    } else {
      // Daily / Weekly: aggregate from submissions
      const matchFilter = {
        date: { $gte: range.start, $lte: range.end },
        status: { $in: ['completed', 'halfday'] },
      };

      const aggregated = await Submission.aggregate([
        { $match: matchFilter },
        {
          $group: {
            _id: '$userId',
            totalHours: { $sum: '$hoursStudied' },
            completedCount: {
              $sum: { $cond: [{ $eq: ['$status', 'completed'] }, 1, 0] },
            },
            halfDayCount: {
              $sum: { $cond: [{ $eq: ['$status', 'halfday'] }, 1, 0] },
            },
            totalPoints: { $sum: '$pointsAwarded' },
          },
        },
        { $sort: { totalHours: -1, totalPoints: -1 } },
      ]);

      // Populate user details
      const userIds = aggregated.map((a) => a._id);
      const users = await User.find({ _id: { $in: userIds } })
        .select('name email avatar streak');

      const userMap = {};
      users.forEach((u) => {
        userMap[u._id.toString()] = u;
      });

      rankData = aggregated.map((a, i) => {
        const user = userMap[a._id.toString()];
        return {
          rank: i + 1,
          userId: a._id,
          name: user?.name || 'Unknown',
          email: user?.email || '',
          avatar: user?.avatar || (user?.name?.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase() || '?'),
          streak: user?.streak || 0,
          totalHours: parseFloat(a.totalHours.toFixed(2)),
          completedCount: a.completedCount,
          halfDayCount: a.halfDayCount,
          points: a.totalPoints,
        };
      });
    }

    // Find requesting user's rank
    const myRank = rankData.findIndex((r) => r.userId.toString() === req.user._id.toString()) + 1;

    res.json({
      success: true,
      mode,
      myRank: myRank || null,
      total: rankData.length,
      leaderboard: rankData,
    });
  } catch (error) {
    next(error);
  }
};

module.exports = { getLeaderboard };
