export type InterfaceTheme = "system" | "light" | "colorful";

const STORAGE_KEY = "parallellines.interface_theme";
const SUPPORTED_THEMES = new Set<InterfaceTheme>(["system", "light", "colorful"]);

// Applies the user's interface theme preference to the document root.
// Key parameter: `theme` is the persisted user preference. Side effects: updates
// localStorage and the html `data-interface-theme` attribute.
export function setInterfaceTheme(theme: string): void {
  if (!isInterfaceTheme(theme)) {
    return;
  }

  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, theme);
  }
  applyInterfaceTheme(theme);
}

// Restores the browser-local interface preference during app bootstrap.
// Key parameters: none. Return value: none. Side effect: mutates the document root.
export function applyStoredInterfaceTheme(): void {
  applyInterfaceTheme(readStoredInterfaceTheme());
}

// Reads the browser-local interface preference with a safe default.
// Key parameters: none. Return value: a supported interface theme.
function readStoredInterfaceTheme(): InterfaceTheme {
  if (typeof window === "undefined") {
    return "system";
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored && isInterfaceTheme(stored) ? stored : "system";
}

// Writes the theme marker consumed by global CSS variables.
// Key parameter: `theme` is a supported preference. Side effect: mutates the document root.
function applyInterfaceTheme(theme: InterfaceTheme): void {
  if (typeof document === "undefined") {
    return;
  }

  const root = document.documentElement;
  if (theme === "system") {
    root.removeAttribute("data-interface-theme");
    return;
  }

  root.dataset.interfaceTheme = theme;
}

// Checks whether an arbitrary string is one of the supported interface themes.
// Key parameter: `theme` is an unknown user/API value. Return value: type guard.
function isInterfaceTheme(theme: string): theme is InterfaceTheme {
  return SUPPORTED_THEMES.has(theme as InterfaceTheme);
}
