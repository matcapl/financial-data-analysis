const { put } = require('@vercel/blob');
require('dotenv').config({ path: '/Users/a/repo/financial-data-analysis/.env' });

// Debug: Log VERCEL_BLOB_TOKEN
console.log('VERCEL_BLOB_TOKEN:', process.env.VERCEL_BLOB_TOKEN);

if (!process.env.VERCEL_BLOB_TOKEN) {
  console.error('Error: VERCEL_BLOB_TOKEN is not set');
  process.exit(1);
}

async function testBlobUpload() {
  try {
    const buffer = Buffer.from('Test file content');
    const blob = await put('test.txt', buffer, {
      access: 'public',
      token: process.env.VERCEL_BLOB_TOKEN
    });
    console.log('Blob uploaded:', blob.url);
  } catch (error) {
    console.error('Blob upload failed:', error.message);
    process.exit(1);
  }
}

testBlobUpload();