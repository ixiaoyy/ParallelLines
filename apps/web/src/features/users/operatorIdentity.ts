import type { PersonaKind } from "@/entities/user/model";

export interface OperatorIdentity {
  kind: PersonaKind | null;
  label: string;
  description: string;
}

export const OPERATOR_IDENTITIES = {
  editorial: {
    kind: "editorial",
    label: "官方栏目",
    description: "该账号由平行线运营维护，用于栏目内容发布。",
  },
  automation: {
    kind: "automation",
    label: "自动账号",
    description: "该账号由平行线运营维护，用于自动化发布或辅助互动。",
  },
  fictional: {
    kind: "fictional",
    label: "创作角色",
    description: "该账号是平行线运营的创作角色，不代表独立社区成员。",
  },
} as const satisfies Record<PersonaKind, OperatorIdentity>;

const GENERIC_OPERATOR_IDENTITY: OperatorIdentity = {
  kind: null,
  label: "运营角色",
  description: "该账号由平行线运营维护。",
};

/** Recognizes supported subtype codes from an unknown API/cache value without side effects. */
export function isPersonaKind(value: unknown): value is PersonaKind {
  return value === "editorial" || value === "automation" || value === "fictional";
}

/** Returns a Boolean flag or null for missing/invalid transport data; unknown never means false. */
export function normalizePersonaFlag(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

/** Returns a known subtype only when the supplied operator flag is explicitly true. */
export function normalizePersonaKind(isPersona: unknown, kind: unknown): PersonaKind | null {
  return isPersona === true && isPersonaKind(kind) ? kind : null;
}

/**
 * Resolves public identity copy from the authoritative flag and optional subtype.
 * Unknown/member flags return null; managed accounts with unknown kinds keep the generic label.
 * This does not infer how any post was created or grant permissions.
 */
export function operatorIdentity(isPersona: unknown, kind?: unknown): OperatorIdentity | null {
  if (isPersona !== true) {
    return null;
  }
  const normalized = normalizePersonaKind(isPersona, kind);
  return normalized === null ? GENERIC_OPERATOR_IDENTITY : OPERATOR_IDENTITIES[normalized];
}
