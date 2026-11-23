'use strict';
const net = require('node:net');

function createProxy(host, port) {
  return net.createServer(client => {
    const upstream = net.connect(port, host);
    client.on('error', () => upstream.destroy());
    client.on('close', () => upstream.destroy());
    upstream.on('error', () => client.destroy());
    client.pipe(upstream).pipe(client);
  });
}

module.exports = {createProxy};
if (require.main === module) {
  createProxy('actual', 5006).listen(5006, '0.0.0.0');
  createProxy('tweaks', 3005).listen(3005, '0.0.0.0');
}
