const fs = require('fs');
fs.copyFileSync('templates/index.html', 'index.html');
console.log('Built: templates/index.html -> index.html');
