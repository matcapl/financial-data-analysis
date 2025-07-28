const express = require('express');
const dotenv = require('dotenv');
const { exec } = require('child_process');
const util = require('util');
const path = require('path');
const { put, get } = require('@vercel/blob');
const cors = require('cors');

dotenv.config();
const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));

// Validate VERCEL_BLOB_TOKEN
if (!process.env.VERCEL_BLOB_TOKEN) {
  console.error('Error: VERCEL_BLOB_TOKEN is not set in .env');
  process.exit(1);
}

app.post('/api/upload', async (req, res) => {
  try {
    const { file, fileType, companyId } = req.body;
    const fileName = `${Date.now()}.${fileType}`;
    const buffer = Buffer.from(file, 'base64');

    // Upload to Vercel Blob
    const blob = await put(fileName, buffer, {
      access: 'public',
      token: process.env.VERCEL_BLOB_TOKEN
    });

    // Save locally for script processing
    const filePath = path.join(__dirname, 'Uploads', fileName);
    require('fs').writeFileSync(filePath, buffer);

    const script = fileType === 'csv' ? 'ingest_xlsx.py' : 'ingest_pdf.py';
    const command = `python ../scripts/${script} ${filePath} ${companyId}`;
    const execPromise = util.promisify(exec);
    await execPromise(command);

    res.json({ message: 'File uploaded and processed', fileName, url: blob.url });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Failed to process file' });
  }
});

app.post('/api/generate-report', async (req, res) => {
  try {
    const { companyId } = req.body;
    const reportPath = path.join(__dirname, 'reports', `${companyId}_report.pdf`);
    const command = `python ../scripts/report_generator.py ${companyId} ${reportPath}`;
    const execPromise = util.promisify(exec);
    await execPromise(command);

    // Upload report to Vercel Blob
    const reportBuffer = require('fs').readFileSync(reportPath);
    const blob = await put(`${companyId}_report.pdf`, reportBuffer, {
      access: 'public',
      token: process.env.VERCEL_BLOB_TOKEN
    });

    res.json({ reportUrl: blob.url });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Failed to generate report' });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));