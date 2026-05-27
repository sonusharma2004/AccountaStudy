// models/Submission.js — Daily proof submission schema
const mongoose = require('mongoose');

const submissionSchema = new mongoose.Schema(
  {
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      required: [true, 'User ID is required'],
      index: true,
    },

    // ── Submission Date (YYYY-MM-DD string for easy daily lookup) ──
    date: {
      type: String, // "2025-01-15"
      required: [true, 'Date is required'],
      match: [/^\d{4}-\d{2}-\d{2}$/, 'Date must be in YYYY-MM-DD format'],
      index: true,
    },

    // ── Student Submitted Data ──
    subject: {
      type: String,
      required: [true, 'Subject is required'],
      enum: [
        'Mathematics',
        'Physics',
        'Chemistry',
        'Biology',
        'Programming',
        'History',
        'Literature',
        'Economics',
        'Other',
      ],
    },
    hoursStudied: {
      type: Number,
      required: [true, 'Hours studied is required'],
      min: [0.5, 'Minimum 0.5 hours'],
      max: [24, 'Cannot exceed 24 hours'],
    },
    notes: {
      type: String,
      default: '',
      maxlength: [500, 'Notes cannot exceed 500 characters'],
      trim: true,
    },

    // ── Screenshots (stored as file paths relative to uploads/) ──
    timerScreenshot: {
      type: String, // e.g. "timer/userId_2025-01-15_1736900000000.jpg"
      required: [true, 'Timer screenshot is required'],
    },
    questionScreenshot: {
      type: String, // e.g. "questions/userId_2025-01-15_1736900000001.jpg"
      required: [true, 'Questions screenshot is required'],
    },

    // ── Admin Verification ──
    status: {
      type: String,
      enum: ['pending', 'completed', 'halfday', 'leave', 'fine'],
      default: 'pending',
      index: true,
    },
    adminNotes: {
      type: String,
      default: '',
      maxlength: [300, 'Admin notes cannot exceed 300 characters'],
      trim: true,
    },
    verifiedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      default: null,
    },
    verifiedAt: {
      type: Date,
      default: null,
    },
    isVerified: {
      type: Boolean,
      default: false,
      index: true,
    },

    // ── Points awarded based on status ──
    pointsAwarded: {
      type: Number,
      default: 0,
    },
  },
  {
    timestamps: true,
  }
);

// ── Compound index: one submission per user per day ──
submissionSchema.index({ userId: 1, date: 1 }, { unique: true });

// ── Points mapping ──
const STATUS_POINTS = {
  completed: 100,
  halfday: 40,
  leave: 0,
  fine: -20,
  pending: 0,
};

// ── Pre-save: assign points based on status ──
submissionSchema.pre('save', function (next) {
  if (this.isModified('status')) {
    this.pointsAwarded = STATUS_POINTS[this.status] || 0;
    if (this.status !== 'pending') {
      this.isVerified = true;
      if (!this.verifiedAt) this.verifiedAt = new Date();
    }
  }
  next();
});

module.exports = mongoose.model('Submission', submissionSchema);
