require('dotenv').config();
const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const uploadRouter = require('./api/upload');
const reportRouter = require('./api/generate-report');

const app = express();
const PORT = process.env.PORT || 4000;

app.use(express.json());

// ensure upload dir exists
const uploadDir = path.join(__dirname, 'Uploads');
fs.mkdirSync(uploadDir, { recursive: true });

const storage = multer.diskStorage({
  destination: uploadDir,
  filename: (_, file, cb) => cb(null, `${Date.now()}-${file.originalname}`)
});
const upload = multer({ storage });

app.post('/api/upload', upload.single('file'), uploadRouter);
app.post('/api/generate-report', reportRouter);
app.get('/api/reports', (_, res) => {
  // simple listing
  const files = fs
    .readdirSync(path.join(__dirname, 'reports'))
    .filter(f => f.endsWith('.pdf'))
    .map(f => ({
      id: f,
      filename: f,
      url: `/reports/${f}`
    }));
  res.json(files);
});
app.use('/reports', express.static(path.join(__dirname, 'reports')));

// health
app.get('/health', (_, res) => res.json({ status: 'ok' }));

app.listen(PORT, () =>
  console.log(`✅ Server API running on port ${PORT}`)
);