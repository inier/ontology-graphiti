/**
 * Anti-corruption layer between the registry REST DTOs (`registryApi`) and the
 * view models used by `registryStore` / designer pages.
 *
 * The backend registry endpoints return a flat `{ id, ... }` envelope, while the
 * store speaks `{ type_id | link_id | action_type_id, ... }`. Mapping explicitly
 * here keeps both sides honest: no `as any`, no double casts, and the DTO change
 * would surface as a compile error in exactly one place.
 */
import type { ActionType, LinkType, ObjectType, ValidationResult } from './registryApi';
import type {
  ActionTypeDefinition,
  LinkTypeDefinition,
  ObjectTypeDefinition,
} from '../stores/ontologyStore';
import type { ConsistencyResult } from '../stores/registryStore';

/** Normalise a list response; tolerates a wrapped `{ items: [] }` envelope. */
export function toList<T>(result: unknown): T[] {
  if (Array.isArray(result)) return result;
  if (result && typeof result === 'object') {
    for (const value of Object.values(result)) {
      if (Array.isArray(value)) return value;
    }
  }
  return [];
}

export function toObjectTypeDefinition(dto: ObjectType): ObjectTypeDefinition {
  return { ...dto, type_id: dto.id };
}

export function toLinkTypeDefinition(dto: LinkType): LinkTypeDefinition {
  return { ...dto, link_id: dto.id };
}

export function toActionTypeDefinition(dto: ActionType): ActionTypeDefinition {
  return { ...dto, action_type_id: dto.id };
}

/** `/validate` answers `{ valid, errors, warnings }`; the store surfaces `issues`. */
export function toConsistencyResult(result: ValidationResult): ConsistencyResult {
  return {
    valid: result.valid,
    issues: result.errors ?? [],
    warnings: result.warnings ?? [],
  };
}
