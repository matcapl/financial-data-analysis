const express = require('express');
    const dotenv = require('dotenv');
    const { exec } = require('child_process');
    const util = require('util');
    const path = require('path');
    const fs = require('fs');
    const { put } = require('@vercel/blob');
    const cors = require('cors');

    if (process.env.NODE_ENV !== 'production') {
      dotenv.config({ path: '/Users/a/repo/financial-data-analysis/.env' });
    }

    console.log('Environment variables loaded:');
    console.log('VERCEL_BLOB_TOKEN:', process.env.VERCEL_BLOB_TOKEN ? '[REDACTED]' : 'undefined');
    console.log('DB_HOST:', process.env.DB_HOST);
    console.log('DB_NAME:', process.env.DB_NAME);
    console.log('DB_USER:', process.env.DB_USER);
    console.log('DB_PORT:', process.env.DB_PORT);

    if (!process.env.VERCEL_BLOB_TOKEN) {
      console.error('Error: VERCEL_BLOB_TOKEN is not set in .env');
      process.exit(1);
    }

    const app = express();
    app.use(cors());
    app.use(express.json({ limit: '50mb' }));

    app.post('/api/upload', async (req, res) => {
      try {
        const { file, fileType, companyId } = req.body;
        if (!file || !fileType || !companyId) {
          throw new Error('Missing required fields: file, fileType, or companyId');
        }
        if (!['csv', 'pdf'].includes(fileType)) {
          throw new Error('Invalid fileType, must be csv or pdf');
        }

        const fileName = `${Date.now()}.${fileType}`;
        const buffer = Buffer.from(file, 'base64');
        const uploadsDir = path.join(__dirname, 'Uploads');
        if (!fs.existsSync(uploadsDir)) {
          fs.mkdirSync(uploadsDir, { recursive: true });
        }
        const filePath = path.join(uploadsDir, fileName);
        fs.writeFileSync(filePath, buffer);

        const blob = await put(fileName, buffer, {
          access: 'public',
          token: process.env.VERCEL_BLOB_TOKEN,
        });

        const script = fileType === 'csv' ? 'ingest_xlsx.py' : 'ingest_pdf.py';
        const command = `python ../scripts/${script} ${filePath} ${companyId}`;
        const execPromise = util.promisify(exec);
        const { stdout, stderr } = await execPromise(command);
        console.log('Script output:', stdout);
        if (stderr) console.error('Script error:', stderr);

        res.json({ message: 'File uploaded and processed', fileName, url: blob.url });
      } catch (error) {
        console.error('Upload error:', error.message, error.stack);
        res.status(500).json({ error: `Failed to process file: ${error.message}` });
      }
    });

    app.post('/api/generate-report', async (req, res) => {
      try {
        const { companyId } = req.body;
        if (!companyId) {
          throw new Error('Missing companyId');
        }

        const reportPath = path.join(__dirname, 'reports', `${companyId}_report.pdf`);
        const reportsDir = path.join(__dirname, 'reports');
        if (!fs.existsSync(reportsDir)) {
          fs.mkdirSync(reportsDir, { recursive: true });
        }

        const command = `python ../scripts/report_generator.py ${companyId} ${reportPath}`;
        const execPromise = util.promisify(exec);
        const { stdout, stderr } = await execPromise(command);
        console.log('Report script output:', stdout);
        if (stderr) console.error('Report script error:', stderr);

        const reportBuffer = fs.readFileSync(reportPath);
        const blob = await put(`${companyId}_report.pdf`, reportBuffer, {
          access: 'public',
          token: process.env.VERCEL_BLOB_TOKEN,
        });

        res.json({ reportUrl: blob.url });
      } catch (error) {
        console.error('Report generation error:', error.message, error.stack);
        res.status(500).json({ error: `Failed to generate report: ${error.message}` });
      }
    });

    const PORT = process.env.PORT || 3001;
    app.listen(PORT, () => console.log(`Server running on port ${PORT}`));