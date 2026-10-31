/**
 * Module augmentation for extensions that register methods onto `cytoscape.Core`
 * but ship no types of their own (`cytoscape-cxtmenu`).
 *
 * This file MUST be a module (hence the top-level `import type`) — that is what makes
 * `declare module 'cytoscape'` an augmentation instead of a shadowing declaration.
 */
import type {} from 'cytoscape';
import type { CxtmenuOptions } from 'cytoscape-cxtmenu';

declare module 'cytoscape' {
  interface Core {
    /** Radial context menu — provided by the `cytoscape-cxtmenu` extension. */
    cxtmenu(options: CxtmenuOptions): Core;
  }
}
