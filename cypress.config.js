const { defineConfig } = require('cypress')

module.exports = defineConfig({
  projectId: '3gfovh',
  chromeWebSecurity: false,
  experimentalModifyObstructiveThirdPartyCode: true,
  modifyObstructiveCode: false,
  e2e: {
    // We've imported your old cypress plugins here.
    // You may want to clean this up later by importing these.
    setupNodeEvents(on, config) {
      return require('./cypress/plugins/index.js')(on, config)
    },
    baseUrl: 'http://localhost:8000',
    specPattern: 'cypress/e2e/**/*.{js,jsx,ts,tsx}',
  },
})
