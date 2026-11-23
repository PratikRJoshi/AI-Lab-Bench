'use strict';
const assert = require('node:assert/strict');
const net = require('node:net');
const {test} = require('node:test');
const {createProxy} = require('./gateway.cjs');

async function listen(server) {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return server.address().port;
}

test('forwards each local connection only to its configured upstream', async t => {
  for (const name of ['actual', 'tweaks']) {
    const upstream = net.createServer(client => {
      client.once('data', () => client.end(name));
    });
    const upstreamPort = await listen(upstream);
    t.after(() => upstream.close());
    const proxy = createProxy('127.0.0.1', upstreamPort);
    const port = await listen(proxy);
    t.after(() => proxy.close());
    const answer = await new Promise((resolve, reject) => {
      const client = net.connect(port, '127.0.0.1', () => client.write('synthetic health request'));
      let response = '';
      client.on('data', bytes => {response += bytes.toString();});
      client.on('end', () => resolve(response));
      client.on('error', reject);
    });
    assert.equal(answer, name);
  }
});
