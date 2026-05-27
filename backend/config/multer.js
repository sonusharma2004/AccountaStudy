// config/multer.js — File upload configuration using Multer
const multer = require('multer');
const path = require('path');
const fs = require('fs');

// Ensure upload directories exist
const ensureDir = (dir) => {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
};
ensureDir('./uploads/timer');
ensureDir('./uploads/questions');

// Storage engine — saves files with original name + timestamp
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    // Route by field name
    if (file.fieldname === 'timerScreenshot') {
      cb(null, './uploads/timer');
    } else if (file.fieldname === 'questionScreenshot') {
      cb(null, './uploads/questions');
    } else {
      cb(null, './uploads');
    }
  },
  filename: (req, file, cb) => {
    // Format: userId_date_timestamp.ext
    const userId = req.user ? req.user.id : 'unknown';
    const date = new Date().toISOString().split('T')[0];
    const ext = path.extname(file.originalname).toLowerCase();
    cb(null, `${userId}_${date}_${Date.now()}${ext}`);
  },
});

// File type filter — only allow images
const fileFilter = (req, file, cb) => {
  const allowedTypes = /jpeg|jpg|png|gif|webp/;
  const ext = allowedTypes.test(path.extname(file.originalname).toLowerCase());
  const mime = allowedTypes.test(file.mimetype);
  if (ext && mime) {
    cb(null, true);
  } else {
    cb(new Error('Only image files are allowed (jpeg, jpg, png, gif, webp)'), false);
  }
};

const upload = multer({
  storage,
  fileFilter,
  limits: {
    fileSize: parseInt(process.env.MAX_FILE_SIZE) || 10 * 1024 * 1024, // 10MB
  },
});

module.exports = upload;
