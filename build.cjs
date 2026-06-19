const fs = require('fs');
const path = require('path');

const outDir = path.join(__dirname, 'public');
fs.mkdirSync(outDir, { recursive: true });
fs.copyFileSync(
  path.join(__dirname, 'templates', 'index.html'),
  path.join(outDir, 'index.html')
);
console.log('Built: public/index.html');
