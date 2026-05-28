// models/User.js — User schema and model
const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');

const userSchema = new mongoose.Schema(
  {
    name: {
      type: String,
      required: [true, 'Name is required'],
      trim: true,
      minlength: [2, 'Name must be at least 2 characters'],
      maxlength: [50, 'Name cannot exceed 50 characters'],
    },
    email: {
      type: String,
      required: [true, 'Email is required'],
      unique: true,
      lowercase: true,
      trim: true,
      match: [/^\S+@\S+\.\S+$/, 'Please enter a valid email'],
    },
    password: {
      type: String,
      required: [true, 'Password is required'],
      minlength: [6, 'Password must be at least 6 characters'],
      select: false, // Never return password in queries by default
    },
    role: {
      type: String,
      enum: ['student', 'admin'],
      default: 'student',
    },

    // ── Study Stats ──
    totalStudyHours: {
      type: Number,
      default: 0,
      min: 0,
    },
    streak: {
      type: Number,
      default: 0,
      min: 0,
    },
    longestStreak: {
      type: Number,
      default: 0,
    },
    lastStudyDate: {
      type: Date,
      default: null,
    },

    // ── Accountability Stats ──
    totalCompleted: {
      type: Number,
      default: 0,
    },
    totalHalfDay: {
      type: Number,
      default: 0,
    },
    totalLeave: {
      type: Number,
      default: 0,
    },
    totalFines: {
      type: Number,
      default: 0,
    },
    points: {
      type: Number,
      default: 0,
    },

    // ── Leave & Half Day Allowance ──
    leavesRemaining: {
      type: Number,
      default: 3,
    },
    halfDaysRemaining: {
      type: Number,
      default: 3,
    },

    // ── Profile ──
    avatar: {
      type: String,
      default: '',
    },
    isActive: {
      type: Boolean,
      default: true,
    },
  },
  {
    timestamps: true, // adds createdAt, updatedAt
  }
);

// ── Pre-save: hash password before saving ──
userSchema.pre('save', async function (next) {
  if (!this.isModified('password')) return next();
  const salt = await bcrypt.genSalt(12);
  this.password = await bcrypt.hash(this.password, salt);
  next();
});

// ── Instance method: compare password ──
userSchema.methods.comparePassword = async function (candidatePassword) {
  return bcrypt.compare(candidatePassword, this.password);
};

// ── Instance method: get initials for avatar ──
userSchema.methods.getInitials = function () {
  return this.name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
};

// ── Virtual: rank (computed separately via aggregation) ──
userSchema.virtual('submissions', {
  ref: 'Submission',
  localField: '_id',
  foreignField: 'userId',
});

module.exports = mongoose.model('User', userSchema);
