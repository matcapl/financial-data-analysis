try {
  require('dotenv').config();
} catch(e) {
  console.error('Error loading .env:', e);
}

// Import structured logging
const { logger, httpLoggerMiddleware, logError } = require('../config/logger');
const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const isVercel = process.env.VERCEL === '1';

const uploadRouter = require('./upload-improved');
const reportRouter = require('./generate-report');

const app = express();
const PORT = process.env.PORT || 4000;

app.use(express.json());

// Environment variables check
logger.info('Environment variables loaded', {
  VERCEL_BLOB_TOKEN: process.env.VERCEL_BLOB_TOKEN ? 'SET' : 'NOT SET',
  BLOB_READ_WRITE_TOKEN: process.env.BLOB_READ_WRITE_TOKEN ? 'SET' : 'NOT SET'
});


// ─── Ensure writable folders ────────────────────────────────────────────
const uploadDir = path.join(__dirname, 'Uploads');
const reportsDir = path.join(__dirname, 'reports');
const dataDir = path.join(__dirname, '..', 'data');

[uploadDir, reportsDir, dataDir].forEach(d => {
  fs.mkdirSync(d, { recursive: true });
  logger.debug('Directory created', { path: d });
});

// ─── Multer setup ───────────────────────────────────────────────────────
const storage = multer.diskStorage({
  destination: uploadDir,
  filename: (_, file, cb) => cb(null, `${Date.now()}-${file.originalname}`)
});
const upload = multer({ 
  storage,
  limits: {
    fileSize: 10 * 1024 * 1024 // 10MB limit
  },
  fileFilter: (req, file, cb) => {
    const allowedTypes = ['.xlsx', '.pdf', '.csv'];
    const ext = path.extname(file.originalname).toLowerCase();
    if (allowedTypes.includes(ext)) {
      cb(null, true);
    } else {
      cb(new Error(`Invalid file type: ${ext}. Only .xlsx, .pdf, and .csv files are allowed.`));
    }
  }
});

// Add HTTP logging middleware
app.use(httpLoggerMiddleware);

app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});

// ─── Routes ─────────────────────────────────────────────────────────────
app.post('/api/upload', upload.single('file'), uploadRouter);
app.post('/api/generate-report', reportRouter);

// Server info endpoint (for client health checks)
app.get('/api/info', (req, res) => {
  res.json({
    server_port: PORT,
    vercel: process.env.VERCEL === '1',
    python_available: process.env.VERCEL !== '1', // Python not available in Vercel
    node_env: process.env.NODE_ENV || 'development',
    timestamp: new Date().toISOString()
  });
});

// List reports endpoint
app.get('/api/reports', (req, res) => {
  try {
    const files = fs.readdirSync(reportsDir)
                    .filter(f => f.endsWith('.pdf'))
                    .map(f => ({ 
                      id: f, 
                      filename: f, 
                      url: `/reports/${f}`,
                      created: fs.statSync(path.join(reportsDir, f)).mtime
                    }))
                    .sort((a, b) => new Date(b.created) - new Date(a.created)); // Most recent first
    res.json(files);
  } catch (error) {
    logError(error, { operation: 'read_reports_directory', path: reportsDir });
    res.json([]); // Return empty array if directory doesn't exist
  }
});

// Serve report files
app.use('/reports', express.static(reportsDir));

// Data files endpoint (for debugging/testing)
app.get('/api/data-files', (req, res) => {
  try {
    const files = fs.readdirSync(dataDir)
                    .filter(f => ['.xlsx', '.pdf', '.csv'].includes(path.extname(f).toLowerCase()))
                    .map(f => ({
                      filename: f,
                      size: fs.statSync(path.join(dataDir, f)).size,
                      modified: fs.statSync(path.join(dataDir, f)).mtime
                    }));
    res.json(files);
  } catch (error) {
    logError(error, { operation: 'read_data_directory', path: dataDir });
    res.json([]);
  }
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok',
    timestamp: new Date().toISOString(),
    port: PORT,
    environment: process.env.NODE_ENV || 'development'
  });
});

// Upload file size error handler
app.use((error, req, res, next) => {
  if (error instanceof multer.MulterError) {
    if (error.code === 'LIMIT_FILE_SIZE') {
      return res.status(400).json({
        error: 'File too large',
        message: 'Please upload a file smaller than 10MB.'
      });
    }
  }
  
  if (error.message && error.message.includes('Invalid file type')) {
    return res.status(400).json({
      error: 'Invalid file type',
      message: error.message
    });
  }
  
  logError(error, { middleware: 'error_handler', url: req.originalUrl });
  res.status(500).json({ 
    error: 'Internal server error',
    message: process.env.NODE_ENV === 'production' ? 'Something went wrong' : error.message
  });
});

// 404 handler (must be last)
app.use('*', (req, res) => {
  res.status(404).json({ 
    error: 'Not found',
    path: req.originalUrl,
    available_endpoints: [
      'GET /health',
      'GET /api/info',
      'GET /api/reports',
      'GET /api/data-files',
      'POST /api/upload',
      'POST /api/generate-report'
    ]
  });
});

// ─── Start Server ──────────────────────────────────────────────────────
app.listen(PORT, () => {
  logger.info('Server started', {
    port: PORT,
    environment: process.env.NODE_ENV || 'development',
    python_available: process.env.VERCEL !== '1',
    vercel_blob: !!process.env.VERCEL_BLOB_TOKEN,
    endpoints: {
      health: `http://localhost:${PORT}/health`,
      info: `http://localhost:${PORT}/api/info`
    }
  });
  
  // Keep console logs for immediate visibility during startup
  console.log(`✅ Server API running on port ${PORT}`);
  console.log(`🔍 Health check: http://localhost:${PORT}/health`);
  console.log(`📊 Server info: http://localhost:${PORT}/api/info`);
  console.log(`🌍 Environment: ${process.env.NODE_ENV || 'development'}`);
  console.log(`🐍 Python available: ${process.env.VERCEL !== '1'}`);
});

app.use((err, req, res, next) => {
  logError(err, { handler: 'unhandled_error', url: req?.originalUrl });
  res.status(500).send(err.stack || err.toString());
});

module.exports = app;