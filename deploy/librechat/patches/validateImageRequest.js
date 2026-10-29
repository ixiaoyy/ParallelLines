// Compatibility adapter for LibreChat v0.8.9-rc1 (8d3da9bbb220a0a96be9330a2e1cbd385fb786d5).
// API index mounts this at /images/. The reverse proxy removes external /chat/.
// Parse the server-side path, retaining the upstream cookie/session/owner/ACL checks.
const cookie = require('cookie');
const {
  createImageAuthorizationMiddleware,
  getAppConfigOptionsFromUser,
  isEnabled,
} = require('@librechat/api');
const {
  findSession,
  getAgent,
  getAssistant,
  getUserById,
  getUserPrincipals,
  hasCapabilityForPrincipals,
  hasPermission,
} = require('~/models');
const { getAppConfig } = require('~/server/services/Config');

const getAssistantEndpointConfigs = (appConfig) =>
  [
    appConfig?.endpoints?.assistants && {
      endpoint: 'assistants',
      ...appConfig.endpoints.assistants,
    },
    appConfig?.endpoints?.azureAssistants && {
      endpoint: 'azureAssistants',
      ...appConfig.endpoints.azureAssistants,
    },
  ].filter(Boolean);

function createValidateImageRequest(config = {}) {
  const options = {
    secureImageLinks: config.secureImageLinks,
    assistantEndpoints: config.assistantEndpoints,
  };
  const deps = {
    parseCookies: cookie.parse,
    isOpenIdReuseEnabled: () => isEnabled(process.env.OPENID_REUSE_TOKENS),
    getBasePath: () => '',
    findSession,
    getAgent,
    getAssistant,
    getUserById,
    getUserPrincipals,
    hasCapabilityForPrincipals,
    hasPermission,
    getImageConfig: async ({ userId, user }) => {
      const appConfig = await getAppConfig(
        getAppConfigOptionsFromUser({ ...user, id: userId }, user.tenantId),
      );
      return {
        secureImageLinks: appConfig.secureImageLinks,
        assistantEndpoints: getAssistantEndpointConfigs(appConfig),
      };
    },
  };
  return createImageAuthorizationMiddleware(options, deps);
}
module.exports = createValidateImageRequest;
