<script setup lang="ts">
import { onBeforeUnmount, onMounted } from "vue";
import { useRoute } from "vue-router";

import { isRecord, isStatusClient, mainAuthOrigin, statusClientOrigin, UNIFIED_AUTH_ENABLED,
  UNIFIED_MESSAGE_TYPE, UNIFIED_REFRESH_TYPE, UNIFIED_VERSION } from "@/features/auth/unified/protocol";
import { currentUnifiedState, ensurePrimarySession, listenUnifiedChanges } from "@/features/auth/unified/session";

const route = useRoute();
let disposed = false;
let running = false;
let dirty = false;
let revision = 0;
let lastRequest = 0;
let cleanup = () => {};
const client = route.query.client;
const requestId = route.query.request_id;
const valid = UNIFIED_AUTH_ENABLED && window.location.origin === mainAuthOrigin()
  && window.parent !== window && isStatusClient(client)
  && typeof requestId === "string" && /^[0-9a-f]{32}$/.test(requestId);
const parentOrigin = valid && isStatusClient(client) ? statusClientOrigin(client) : "";

/** 仅向登记父站发最小状态；权威故障必须与匿名分开，不能发送令牌或资料。 */
async function synchronize(): Promise<void> {
  if (!valid || disposed) return;
  if (running) { dirty = true; return; }
  running = true;
  const currentRevision = revision;
  let available = true;
  try { await ensurePrimarySession(); } catch { available = false; }
  running = false;
  if (disposed) return;
  if (dirty || currentRevision !== revision) { dirty = false; void synchronize(); return; }
  window.parent.postMessage({ type: UNIFIED_MESSAGE_TYPE, version: UNIFIED_VERSION, request_id: requestId,
    available, ...(available ? currentUnifiedState() : { authenticated: false, subject: null, auth_epoch: null }) }, parentOrigin);
}

function receive(event: MessageEvent<unknown>): void {
  if (!valid || event.source !== window.parent || event.origin !== parentOrigin || !isRecord(event.data)
    || event.data.type !== UNIFIED_REFRESH_TYPE || event.data.version !== 1 || event.data.request_id !== requestId
    || Date.now() - lastRequest < 1000) return;
  lastRequest = Date.now();
  void synchronize();
}

onMounted(() => {
  if (!valid) return;
  window.addEventListener("message", receive);
  cleanup = listenUnifiedChanges(() => { revision += 1; void synchronize(); });
  void synchronize();
});
onBeforeUnmount(() => { disposed = true; cleanup(); window.removeEventListener("message", receive); });
</script>

<template><span hidden aria-hidden="true">主站登录状态同步</span></template>
