const path = require('path');

test('eslint config uses the Create React App presets', () => {
  const configPath = path.resolve(__dirname, '../../.eslintrc.js');
  const eslintConfig = require(configPath);

  expect(eslintConfig.extends).toEqual(['react-app', 'react-app/jest']);
});
