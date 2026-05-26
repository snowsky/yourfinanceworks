import { describe, expect, it } from 'vitest';

import { hasLevel, PermissionLevel } from '../permissions';

describe('hasLevel', () => {
  const cases: Array<[PermissionLevel, PermissionLevel, boolean]> = [
    ['viewer', 'viewer', true],
    ['viewer', 'user', false],
    ['viewer', 'admin', false],
    ['user', 'viewer', true],
    ['user', 'user', true],
    ['user', 'admin', false],
    ['admin', 'viewer', true],
    ['admin', 'user', true],
    ['admin', 'admin', true],
  ];

  it.each(cases)(
    'hasLevel(%s, %s) === %s',
    (actual, required, expected) => {
      expect(hasLevel(actual, required)).toBe(expected);
    },
  );
});
