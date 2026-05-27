// config/db.js — MongoDB connection via Mongoose
const mongoose = require('mongoose');

const connectDB = async () => {
  try {
    const conn = await mongoose.connect(process.env.MONGODB_URI, {
      // These options are defaults in Mongoose 8+ but explicit for clarity
    });
    console.log(`✅ MongoDB Connected: ${conn.connection.host}`);
  } catch (error) {
    console.error(`❌ MongoDB Connection Error: ${error.message}`);
    process.exit(1);
  }
};

// Log connection events
mongoose.connection.on('disconnected', () => {
  console.warn('⚠️  MongoDB disconnected');
});
mongoose.connection.on('reconnected', () => {
  console.log('🔄 MongoDB reconnected');
});

module.exports = connectDB;
