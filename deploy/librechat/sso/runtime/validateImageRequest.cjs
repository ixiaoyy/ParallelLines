'use strict';
const nativeFactory = require('../sso-runtime/native/validateImageRequest.native.cjs');
const runtime = require('../sso-runtime/runtime.cjs');
module.exports = function createValidateImageRequest(config = {}) {
  return runtime.image(nativeFactory(config));
};
