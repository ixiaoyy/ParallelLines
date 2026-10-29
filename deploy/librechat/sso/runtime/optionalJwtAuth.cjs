'use strict';
const native = require('../sso-runtime/native/optionalJwtAuth.native.cjs');
module.exports = require('../sso-runtime/runtime.cjs').wrapOptional(native);
