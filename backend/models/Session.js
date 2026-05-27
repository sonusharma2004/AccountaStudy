// models/Session.js — Individual study timer sessions
const mongoose = require('mongoose');

const sessionSchema = new mongoose.Schema(
  {
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      required: true,
      index: true,
    },
    subject: {
      type: String,
      required: true,
      enum: [
        'Mathematics', 'Physics', 'Chemistry', 'Biology',
        'Programming', 'History', 'Literature', 'Economics', 'Other',
      ],
    },
    startTime: {
      type: Date,
      required: true,
    },
    endTime: {
      type: Date,
      default: null,
    },
    duration: {
      type: Number, // in seconds
      default: 0,
      min: 0,
    },
    isActive: {
      type: Boolean,
      default: true, // true = session in progress
      index: true,
    },
    date: {
      type: String, // "YYYY-MM-DD" for easy grouping
      index: true,
    },
  },
  { timestamps: true }
);

// ── Pre-save: set date string and duration ──
sessionSchema.pre('save', function (next) {
  if (!this.date) {
    this.date = this.startTime.toISOString().split('T')[0];
  }
  if (this.endTime && this.startTime) {
    this.duration = Math.floor((this.endTime - this.startTime) / 1000);
  }
  next();
});

module.exports = mongoose.model('Session', sessionSchema);
