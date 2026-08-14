const SIDES = ['you', 'enemy'];
const TYPES = ['battle', 'scout', 'citystats'];
const CLASSES = ['Infantry', 'Lancer', 'Marksman'];

function requireSide(side) {
  if (!SIDES.includes(side)) throw new Error(`invalid side: ${side}`);
}

function requireType(type) {
  if (!TYPES.includes(type)) throw new Error(`invalid type: ${type}`);
}

export function createFlow({ genTable = {} } = {}) {
  const typeState = { you: 'scout', enemy: 'scout' };
  const shotState = { you: [], enemy: [] };

  function setSideType(side, type) {
    requireSide(side);
    requireType(type);
    if (side === 'enemy' && type === 'citystats') {
      throw new Error('enemy cannot use citystats');
    }
    typeState[side] = type;
  }

  function pickKind(kind) {
    requireType(kind);
    const presets = {
      scout: { you: 'scout', enemy: 'scout' },
      citystats: { you: 'citystats', enemy: 'scout' },
      battle: { you: 'battle', enemy: 'battle' },
    };
    typeState.you = presets[kind].you;
    typeState.enemy = presets[kind].enemy;
  }

  function addShot(side, shotId) {
    requireSide(side);
    shotState[side].push(shotId);
  }

  function removeShot(side, shotId) {
    requireSide(side);
    shotState[side] = shotState[side].filter((existing) => existing !== shotId);
  }

  function isCovered(side) {
    if (shotState[side].length > 0) return true;
    const other = side === 'you' ? 'enemy' : 'you';
    return typeState[other] === 'battle' && shotState[other].length > 0;
  }

  function coverage() {
    const you = isCovered('you');
    const enemy = isCovered('enemy');
    return { you, enemy, complete: you && enemy };
  }

  function defaultHeroes(gen) {
    const generation = genTable[gen];
    return Object.fromEntries(CLASSES.map((cls) => [cls, generation?.[cls] ?? null]));
  }

  return {
    pickKind,
    setSideType,
    addShot,
    removeShot,
    coverage,
    defaultHeroes,
    types: () => ({ ...typeState }),
    shots: (side) => {
      requireSide(side);
      return [...shotState[side]];
    },
  };
}
