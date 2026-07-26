import biomeConfig from '../../biome.json';

test('Biome leaves source formatting to Prettier', () => {
  expect(biomeConfig.formatter.enabled).toBe(false);
});
