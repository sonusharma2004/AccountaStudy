// controllers/authController.js — Register, Login, Profile
const User = require('../models/User');
const { generateToken } = require('../middleware/auth');

// ── Helper: format user response (no password) ──
const formatUser = (user, token) => ({
  success: true,
  token,
  user: {
    id: user._id,
    name: user.name,
    email: user.email,
    role: user.role,
    studentType: user.studentType || 'fulltime',
    avatar: user.avatar || user.getInitials(),
    streak: user.streak,
    totalStudyHours: user.totalStudyHours,
    totalCompleted: user.totalCompleted,
    totalHalfDay: user.totalHalfDay,
    totalLeave: user.totalLeave,
    totalFines: user.totalFines,
    points: user.points,
    leavesRemaining: user.leavesRemaining ?? 3,
    halfDaysRemaining: user.halfDaysRemaining ?? 3,
    createdAt: user.createdAt,
  },
});

// ────────────────────────────────────────────
// @route   POST /api/auth/register
// @access  Public
// ────────────────────────────────────────────
const register = async (req, res, next) => {
  try {
    const { name, email, password, role, studentType } = req.body;

    // Basic validation
    if (!name || !email || !password) {
      return res.status(400).json({ success: false, message: 'Please provide name, email and password.' });
    }

    // Don't allow registering as admin via API (admin created via seed)
    const assignedRole = role === 'admin' ? 'student' : (role || 'student');
    const assignedType = ['intern', 'fulltime'].includes(studentType) ? studentType : 'fulltime';

    const user = await User.create({ name, email, password, role: assignedRole, studentType: assignedType });
    const token = generateToken(user._id);

    res.status(201).json(formatUser(user, token));
  } catch (error) {
    next(error);
  }
};

// ────────────────────────────────────────────
// @route   POST /api/auth/login
// @access  Public
// ────────────────────────────────────────────
const login = async (req, res, next) => {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ success: false, message: 'Please provide email and password.' });
    }

    // Select password explicitly (it's hidden by default)
    const user = await User.findOne({ email: email.toLowerCase().trim() }).select('+password');

    if (!user || !(await user.comparePassword(password))) {
      return res.status(401).json({ success: false, message: 'Invalid email or password.' });
    }

    if (!user.isActive) {
      return res.status(403).json({ success: false, message: 'Account deactivated. Contact admin.' });
    }

    const token = generateToken(user._id);
    res.json(formatUser(user, token));
  } catch (error) {
    next(error);
  }
};

// ────────────────────────────────────────────
// @route   GET /api/auth/me
// @access  Private
// ────────────────────────────────────────────
const getMe = async (req, res, next) => {
  try {
    const user = await User.findById(req.user._id);
    res.json({
      success: true,
      user: {
        id: user._id,
        name: user.name,
        email: user.email,
        role: user.role,
        studentType: user.studentType || 'fulltime',
        avatar: user.avatar || user.getInitials(),
        streak: user.streak,
        longestStreak: user.longestStreak,
        totalStudyHours: parseFloat(user.totalStudyHours.toFixed(2)),
        totalCompleted: user.totalCompleted,
        totalHalfDay: user.totalHalfDay,
        totalLeave: user.totalLeave,
        totalFines: user.totalFines,
        points: user.points,
        leavesRemaining: user.leavesRemaining ?? 3,
        halfDaysRemaining: user.halfDaysRemaining ?? 3,
        lastStudyDate: user.lastStudyDate,
        createdAt: user.createdAt,
      },
    });
  } catch (error) {
    next(error);
  }
};

// ────────────────────────────────────────────
// @route   PUT /api/auth/update-profile
// @access  Private
// ────────────────────────────────────────────
const updateProfile = async (req, res, next) => {
  try {
    const { name } = req.body;
    const updates = {};
    if (name) updates.name = name.trim();

    const user = await User.findByIdAndUpdate(req.user._id, updates, {
      new: true,
      runValidators: true,
    });

    res.json({ success: true, user });
  } catch (error) {
    next(error);
  }
};

module.exports = { register, login, getMe, updateProfile };
