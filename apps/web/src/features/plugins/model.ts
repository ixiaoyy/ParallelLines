import type { components } from "@/shared/api/generated";

export type PluginUiExtension = components["schemas"]["PluginUiExtensionResponse"];
export type PluginInfo = components["schemas"]["PluginResponse"];
export type PluginUpdateRequest = components["schemas"]["PluginUpdateRequest"];

export function extensionLabel(extension: PluginUiExtension): string {
  const label = extension.props?.label;
  return typeof label === "string" && label.trim() ? label : extension.title;
}

export function extensionHref(extension: PluginUiExtension): string | null {
  const href = extension.props?.href;
  return typeof href === "string" && href.startsWith("/") ? href : null;
}
