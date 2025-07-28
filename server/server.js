const express = require('express');
const dotenv = require('dotenv');
const { exec } = require('child_process');
const util = require('util');
const path = require('path');
const { BlobServiceClient } = require('@azure/storage-blob');
const cors = require('cors');

dotenv.config();
const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));

const blobServiceClient = BlobServiceClient.fromConnectionString(process.env.VERCEL_BLOB_TOKEN);
const containerClient = blobServiceClient.getContainerClient('financial-data');

app.post('/api/upload', async (req, res) => {
  try {
    const { file, fileType, companyId } = req.body;
    const fileName = `${Date.now()}.${fileType}`;
    const blobClient = containerClient.getBlockBlobClient(fileName);
    const buffer = Buffer.from(file, 'base64');
    await blobClient.upload(buffer, buffer.length);
    const filePath = path.join(__dirname, 'uploads', fileName);
    require('fs').writeFileSync(filePath, buffer);

    const script = fileType === 'csv' ? 'ingest_xlsx.py' : 'ingest_pdf.py';
    const command = `python ../scripts/${script} ${filePath} ${companyId}`;
    const execPromise = util.promisify(exec);
    await execPromise(command);

    res.json({ message: 'File uploaded and processed', fileName });
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

    const blobClient = containerClient.getBlockBlobClient(path.basename(reportPath));
    await blobClient.uploadFile(reportPath);
    const reportUrl = blobClient.url;

    res.json({ reportUrl });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Failed to generate report' });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));