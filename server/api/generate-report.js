const { execSync } = require('child_process');
const { put } = require('@vercel/blob');
const path = require('path');
const fs = require('fs');

module.exports = async (req, res) => {
  const { company_id } = req.body;
  if (!company_id) {
    return res.status(400).json({ error: 'Missing company_id' });
  }

  try {
    const outputPath = path.join(__dirname, '..', '..', 'reports', `report_${company_id}_${Date.now()}.pdf`);
    execSync(`python scripts/report_generator.py ${company_id} ${outputPath}`);
    const blob = await put(path.basename(outputPath), fs.readFileSync(outputPath), { access: 'public' });
    res.json({ message: 'Report generated successfully', reportPath: blob.url });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Report generation failed: ' + err.message });
  }
};