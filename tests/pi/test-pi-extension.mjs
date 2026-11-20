import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '../..');
const packageJsonPath = resolve(repoRoot, 'package.json');
const extensionPath = resolve(repoRoot, '.pi/extensions/dev-workflow.ts');
const piToolsPath = resolve(repoRoot, 'skills/dev-workflow/references/pi-tools.md');

async function readPackageJson() {
  return JSON.parse(await readFile(packageJsonPath, 'utf8'));
}

async function loadExtension() {
  const handlers = new Map();
  const pi = {
    on(event, handler) {
      if (!handlers.has(event)) handlers.set(event, []);
      handlers.get(event).push(handler);
    },
  };
  const mod = await import(pathToFileURL(extensionPath).href + `?cachebust=${Date.now()}-${Math.random()}`);
  mod.default(pi);
  return { handlers };
}

function firstHandler(handlers, event) {
  const eventHandlers = handlers.get(event) ?? [];
  assert.equal(eventHandlers.length, 1, `expected one ${event} handler`);
  return eventHandlers[0];
}

async function emit(handlers, event, payload) {
  for (const handler of handlers.get(event) ?? []) {
    await handler({ type: event, ...payload }, {});
  }
}

function textOf(message) {
  if (typeof message.content === 'string') return message.content;
  return message.content
    .filter((part) => part.type === 'text')
    .map((part) => part.text)
    .join('\n');
}

test('package.json declares a pi package with skills and dev-workflow extension', async () => {
  const pkg = await readPackageJson();

  assert.equal(pkg.name, 'dev-workflow');
  assert.ok(pkg.keywords.includes('pi-package'));
  assert.deepEqual(pkg.pi.skills, ['./skills']);
  assert.deepEqual(pkg.pi.extensions, ['./.pi/extensions/dev-workflow.ts']);
});

test('extension registers Pi lifecycle hooks without overriding package skill discovery', async () => {
  const { handlers } = await loadExtension();

  assert.equal((handlers.get('resources_discover') ?? []).length, 0);
  for (const event of ['session_start', 'session_compact', 'context']) {
    assert.equal((handlers.get(event) ?? []).length, 1, `missing ${event} handler`);
  }
});

test('startup context injects dev-workflow bootstrap as one user message', async () => {
  const { handlers } = await loadExtension();
  const sessionStart = firstHandler(handlers, 'session_start');
  const context = firstHandler(handlers, 'context');

  await sessionStart({ type: 'session_start', reason: 'startup' }, {});

  const originalMessages = [
    { role: 'user', content: [{ type: 'text', text: 'Refactor legacy order cancellation' }], timestamp: 1 },
  ];
  const result = await context({ type: 'context', messages: originalMessages }, {});

  assert.equal(result.messages.length, 2);
  assert.equal(result.messages[0].role, 'user');
  assert.match(textOf(result.messages[0]), /dev-workflow bootstrap for pi/);
  assert.match(textOf(result.messages[0]), /Pi tool mapping/);
  assert.equal(result.messages[1], originalMessages[0]);

  const alreadyInjected = await context({ type: 'context', messages: result.messages }, {});
  assert.equal(alreadyInjected, undefined, 'bootstrap must not duplicate when already present');
});

test('session_compact injects bootstrap after compaction summaries', async () => {
  const { handlers } = await loadExtension();
  const sessionCompact = firstHandler(handlers, 'session_compact');
  const context = firstHandler(handlers, 'context');

  await sessionCompact({ type: 'session_compact', compactionEntry: {}, fromExtension: false }, {});

  const summary = { role: 'compactionSummary', summary: 'Prior work', tokensBefore: 100, timestamp: 1 };
  const user = { role: 'user', content: [{ type: 'text', text: 'Continue' }], timestamp: 2 };
  const result = await context({ type: 'context', messages: [summary, user] }, {});

  assert.equal(result.messages.length, 3);
  assert.equal(result.messages[0], summary);
  assert.equal(result.messages[1].role, 'user');
  assert.match(textOf(result.messages[1]), /dev-workflow bootstrap for pi/);
  assert.equal(result.messages[2], user);
});

test('pi-tools.md documents subagent and task tracking mappings', async () => {
  assert.equal(existsSync(piToolsPath), true, 'pi-tools.md should exist');
  const text = await readFile(piToolsPath, 'utf8');
  const rows = text.split('\n').filter((line) => line.startsWith('|'));
  assert.ok(rows.some((row) => /subagent/i.test(row)));
  assert.ok(rows.some((row) => /todo|task/i.test(row)));
});
