// controllers/adminController.js — Admin management actions
const User = require('../models/User');
const Submission = require('../models/Submission');
const Session = require('../models/Session');

// ────────────────────────────────────────────
// @route   GET /api/admin/users
// @access  Admin
// @desc    Get all students with stats
// ────────────────────────────────────────────
const getAllUsers = async (req, res, next) => {
  try {
    const { search } = req.query;
    const filter = { role: 'student' };
    if (search) {
      filter.$or = [
        { name: { $regex: search, $options: 'i' } },
        { email: { $regex: search, $options: 'i' } },
      ];
    }

    const users = await User.find(filter)
      .select('-password')
      .sort({ totalStudyHours: -1 });

    // Get today's submission status for each student
    const today = new Date().toISOString().split('T')[0];
    const todaySubmissions = await Submission.find({ date: today }).select('userId status isVerified');
    const todayMap = {};
    todaySubmissions.forEach((s) => {
      todayMap[s.userId.toString()] = { status: s.status, isVerified: s.isVerified };
    });

    const data = users.map((u) => ({
      id: u._id,
      name: u.name,
      email: u.email,
      avatar: u.avatar || u.name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase(),
      streak: u.streak,
      longestStreak: u.longestStreak,
      totalStudyHours: parseFloat(u.totalStudyHours.toFixed(2)),
      totalCompleted: u.totalCompleted,
      totalHalfDay: u.totalHalfDay,
      totalLeave: u.totalLeave,
      totalFines: u.totalFines,
      points: u.points,
      isActive: u.isActive,
      lastStudyDate: u.lastStudyDate,
      todayStatus: todayMap[u._id.toString()] || { status: 'none', isVerified: false },
      joinedAt: u.createdAt,
    }));

    res.json({ success: true, total: data.length, users: data });
  } catch (error) {
    next(error);
  }
};

// ────────────────────────────────────────────
// @route   DELETE /api/admin/user/:id
// @access  Admin
// ────────────────────────────────────────────
const deleteUser = async (req, res, next) => {
  try {
    const user = await User.findById(req.params.id);
    if (!user) return res.status(404).json({ success: false, message: 'User not found.' });
    if (user.role === 'admin') return res.status(403).json({ success: false, message: 'Cannot delete admin.' });

    // Delete user + all their data
    await Promise.all([
      User.findByIdAndDelete(req.params.id),
      Submission.deleteMany({ userId: req.params.id }),
      Session.deleteMany({ userId: req.params.id }),
    ]);

    res.json({ success: true, message: `${user.name} and all their data removed.` });
  } catch (error) {
    next(error);
  }
};

// ────────────────────────────────────────────
// @route   PUT /api/admin/user/:id/toggle
// @access  Admin
// @desc    Activate / Deactivate student account
// ────────────────────────────────────────────
const toggleUserStatus = async (req, res, next) => {
  try {
    const user = await User.findById(req.params.id);
    if (!user) return res.status(404).json({ success: false, message: 'User not found.' });

    user.isActive = !user.isActive;
    await user.save();

    res.json({
      success: true,
      message: `Account ${user.isActive ? 'activated' : 'deactivated'} for ${user.name}`,
      isActive: user.isActive,
    });
  } catch (error) {
    next(error);
  }
};

// ────────────────────────────────────────────
// @route   GET /api/admin/stats
// @access  Admin
// @desc    System-wide dashboard stats
// ────────────────────────────────────────────
const getSystemStats = async (req, res, next) => {
  try {
    const today = new Date().toISOString().split('T')[0];

    const [
      totalStudents,
      totalSubmissions,
      todaySubmissions,
      pendingVerifications,
      totalSessions,
    ] = await Promise.all([
      User.countDocuments({ role: 'student', isActive: true }),
      Submission.countDocuments(),
      Submission.countDocuments({ date: today }),
      Submission.countDocuments({ status: 'pending' }),
      Session.countDocuments({ isActive: false }),
    ]);

    // Status breakdown for today
    const todayBreakdown = await Submission.aggregate([
      { $match: { date: today } },
      { $group: { _id: '$status', count: { $sum: 1 } } },
    ]);
    const breakdown = { completed: 0, halfday: 0, leave: 0, fine: 0, pending: 0 };
    todayBreakdown.forEach((b) => { breakdown[b._id] = b.count; });

    // Total study hours across all students
    const hoursAgg = await User.aggregate([
      { $match: { role: 'student' } },
      { $group: { _id: null, total: { $sum: '$totalStudyHours' } } },
    ]);
    const totalHours = hoursAgg[0]?.total || 0;

    res.json({
      success: true,
      stats: {
        totalStudents,
        totalSubmissions,
        todaySubmissions,
        pendingVerifications,
        totalSessions,
        totalStudyHours: parseFloat(totalHours.toFixed(2)),
        today: breakdown,
      },
    });
  } catch (error) {
    next(error);
  }
};

// ────────────────────────────────────────────
// @route   GET /api/admin/analytics
// @access  Admin
// @desc    Analytics data for all students
// ────────────────────────────────────────────
const getAnalytics = async (req, res, next) => {
  try {
    const { days = 30 } = req.query;
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - parseInt(days));
    const startStr = startDate.toISOString().split('T')[0];

    // Daily submission counts by status
    const dailyTrend = await Submission.aggregate([
      { $match: { date: { $gte: startStr } } },
      {
        $group: {
          _id: { date: '$date', status: '$status' },
          count: { $sum: 1 },
          hours: { $sum: '$hoursStudied' },
        },
      },
      { $sort: { '_id.date': 1 } },
    ]);

    res.json({ success: true, dailyTrend });
  } catch (error) {
    next(error);
  }
};

module.exports = { getAllUsers, deleteUser, toggleUserStatus, getSystemStats, getAnalytics };
