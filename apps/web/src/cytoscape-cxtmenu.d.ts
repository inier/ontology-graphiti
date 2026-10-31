/**
 * Hand-written ambient types for `cytoscape-cxtmenu` (no `@types` package is published).
 *
 * This file must stay a *global script* (no top-level import/export) so the
 * `declare module` below is treated as an ambient module declaration rather than a
 * module augmentation of a module TypeScript cannot resolve. The matching
 * `cy.cxtmenu(...)` augmentation on `cytoscape.Core` lives in `cytoscape-augment.d.ts`.
 */
declare module 'cytoscape-cxtmenu' {
  import type { Core, EdgeSingular, Ext, NodeSingular } from 'cytoscape';

  /**
   * The element a command was triggered on. `selector: 'core'` menus receive the
   * instance itself, node menus receive a node, edge menus an edge — the plugin
   * funnels all three through one `target` slot, so the shapes are merged here.
   */
  type CxtmenuTarget = Core & NodeSingular & EdgeSingular;

  interface CxtmenuEvent {
    target: CxtmenuTarget;
    /** Rendered (screen) position of the pointer, in CSS pixels. */
    renderedPosition?: { x: number; y: number };
  }

  interface CxtmenuCommand {
    /** HTML string or DOM element rendered inside the radial slot. */
    content: string | HTMLElement;
    /** Greys out the slot without removing it. */
    enabled?: boolean;
    /** Hides the slot entirely. */
    visible?: boolean;
    select?: (event: CxtmenuEvent) => void;
  }

  interface CxtmenuOptions {
    selector: 'node' | 'edge' | 'core';
    commands: CxtmenuCommand[] | ((event: CxtmenuEvent) => CxtmenuCommand[]);
    menuRadius?: number;
    activePadding?: number;
    indicatorSize?: number;
    separatorWidth?: number;
    spotlightPadding?: number;
    adaptativeNodeSpotlightRadius?: boolean;
    minSpotlightRadius?: number;
    maxSpotlightRadius?: number;
    openMenuEvents?: string;
    itemColor?: string;
    itemTextShadowColor?: string;
    zIndex?: number;
    atMouse?: boolean;
    outsideMenuCancel?: number;
  }

  const cxtmenu: Ext;
  export default cxtmenu;
  export type { CxtmenuCommand, CxtmenuEvent, CxtmenuOptions };
}
