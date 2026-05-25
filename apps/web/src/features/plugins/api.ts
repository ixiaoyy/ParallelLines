import { apiGet, apiPut } from "@/shared/api/client";

import type { PluginInfo, PluginUiExtension, PluginUpdateRequest } from "./model";

export function fetchSiteExtensions(): Promise<PluginUiExtension[]> {
  return apiGet<PluginUiExtension[]>("/site/extensions");
}

export function fetchAdminPlugins(): Promise<PluginInfo[]> {
  return apiGet<PluginInfo[]>("/admin/plugins");
}

export function updateAdminPlugin(
  pluginId: string,
  payload: PluginUpdateRequest,
): Promise<PluginInfo> {
  return apiPut<PluginInfo, PluginUpdateRequest>(
    `/admin/plugins/${encodeURIComponent(pluginId)}`,
    payload,
  );
}
