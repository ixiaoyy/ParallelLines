'use strict';
// Singleton shared by ingress staging and the native controller's factory wrapper.
const { createStagedRefreshDelivery } = require('./staged-delivery.cjs');
const delivery = createStagedRefreshDelivery();
module.exports = {
  wrapCreateOpenIDResponseDelivery: nativeCreate => delivery.wrapFactory(nativeCreate),
  installRefreshResponseStage: (req, res, gate) => delivery.install(req, res,
    { verify: gate.verifyNativeResponse, forget: gate.forget }),
};
