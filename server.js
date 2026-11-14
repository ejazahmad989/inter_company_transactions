const http = require('http');
http
  .createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(`<!DOCTYPE html><html><head><title>Inter Company Transactions</title>
<style>body{font-family:sans-serif;padding:40px;background:#f8f9fa;color:#333}
pre{background:#eee;padding:12px;border-radius:4px}</style></head>
<body><h2>Inter Company Transactions (Frappe / ERPNext App)</h2>
<p>Backend Frappe app codebase active.</p></body></html>`);
  })
  .listen(3000, '0.0.0.0', () =>
    console.log('Healthcheck server listening on port 3000'),
  );
