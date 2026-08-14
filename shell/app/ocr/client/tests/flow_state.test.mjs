import test from 'node:test';
import assert from 'node:assert/strict';
import { createFlow } from '../flow_state.mjs';

test('S1 presets per spec', () => {
  const f = createFlow();
  f.pickKind('citystats');
  assert.deepEqual(f.types(), { you: 'citystats', enemy: 'scout' });
  f.pickKind('battle');
  assert.deepEqual(f.types(), { you: 'battle', enemy: 'battle' });
});
test('enemy can never be citystats', () => {
  const f = createFlow();
  assert.throws(() => f.setSideType('enemy', 'citystats'));
});
test('battle-with-shot covers both; own shot takes precedence', () => {
  const f = createFlow();
  f.pickKind('battle');
  f.addShot('you', 's1');
  assert.deepEqual(f.coverage(), { you: true, enemy: true, complete: true });
  f.setSideType('enemy', 'scout');          // enemy switches to its own scout shot
  assert.equal(f.coverage().enemy, true);   // still covered by the battle shot until...
  f.addShot('enemy', 's2');                 // ...own shot exists — precedence, still covered
  assert.equal(f.coverage().complete, true);
});
test('type changes never clear uploads', () => {
  const f = createFlow();
  f.pickKind('scout');
  f.addShot('you', 'a'); f.addShot('enemy', 'b');
  f.setSideType('you', 'citystats');
  assert.equal(f.shots('you').length, 1);
  assert.equal(f.shots('enemy').length, 1);
});
test('two-side without both shots is incomplete', () => {
  const f = createFlow();
  f.pickKind('scout');
  f.addShot('you', 'a');
  assert.deepEqual(f.coverage(), { you: true, enemy: false, complete: false });
});
test('hero defaulting from gen, never guessed', () => {
  const f = createFlow({ genTable: { 15: { Infantry: 'Hank', Lancer: 'Estrella', Marksman: 'Viveca' } } });
  assert.deepEqual(f.defaultHeroes(15), { Infantry: 'Hank', Lancer: 'Estrella', Marksman: 'Viveca' });
  assert.deepEqual(f.defaultHeroes(99), { Infantry: null, Lancer: null, Marksman: null });
});
