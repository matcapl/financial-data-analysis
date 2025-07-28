const { execSync } = require('child_process');
const { put } = require('@vercel/blob');
const path = require('path');
const fs = require('fs');

module.exports = async (req, res) => {
  if (!req.files || !req.files.file) {
    return res.status(400).json({ error: 'No file uploaded' });
  }
  const file = req.files.file;
  const ext = path.extname(file.name).toLowerCase();
  if (!['.xlsx', '.pdf'].includes(ext)) {
    return res.status(400).json({ error: 'Invalid file type' });
  }

  try {
    const filePath = path.join(__dirname, '..', '..', 'data', file.name);
    await file.mv(filePath);
    const script = ext === '.xlsx' ? 'ingest_xlsx.py' : 'ingest_pdf.py';
    execSync(`python scripts/${script} ${filePath} 1`);
    const blob = await put(file.name, fs.readFileSync(filePath), { access: 'public' });
    res.json({ message: 'File ingested successfully', blobUrl: blob.url });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Ingestion failed: ' + err.message });
  }
};