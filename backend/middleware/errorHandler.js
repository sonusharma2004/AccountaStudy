// middleware/errorHandler.js — Centralized error handling
const errorHandler = (err, req, res, next) => {
  let statusCode = err.statusCode || 500;
  let message = err.message || 'Internal Server Error';

  // Mongoose: bad ObjectId
  if (err.name === 'CastError') {
    message = `Resource not found. Invalid: ${err.path}`;
    statusCode = 404;
  }

  // Mongoose: duplicate key (e.g. same email, or same date submission)
  if (err.code === 11000) {
    const field = Object.keys(err.keyValue)[0];
    if (field === 'email') {
      message = 'An account with this email already exists.';
    } else if (field === 'userId' || err.keyPattern?.userId) {
      message = 'You have already submitted proof for today. One submission per day allowed.';
    } else {
      message = `Duplicate value for field: ${field}`;
    }
    statusCode = 409;
  }

  // Mongoose: validation error
  if (err.name === 'ValidationError') {
    const messages = Object.values(err.errors).map((e) => e.message);
    message = messages.join('. ');
    statusCode = 400;
  }

  // Multer: file too large
  if (err.code === 'LIMIT_FILE_SIZE') {
    message = 'File too large. Maximum size is 10MB.';
    statusCode = 400;
  }

  // Multer: wrong file type
  if (err.message && err.message.includes('Only image files')) {
    statusCode = 400;
  }

  // Log in dev
  if (process.env.NODE_ENV === 'development') {
    console.error('❌ ERROR:', err);
  }

  res.status(statusCode).json({
    success: false,
    message,
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack }),
  });
};

module.exports = errorHandler;
