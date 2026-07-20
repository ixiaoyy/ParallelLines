/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MATCH3_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
