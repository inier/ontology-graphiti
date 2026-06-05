# Feature Specification: Guard Card Shield Stacking

## Summary

The player can play Guard cards during battle to gain shield. Shield gained from multiple Guard cards stacks within the same turn.

## Acceptance Criteria

### AC-001

Given the player has no shield, when the player plays one Guard card that grants 5 shield, then the player should have 5 shield.

### AC-002

Given the player has no shield, when the player plays two Guard cards that each grant 5 shield, then the player should have 10 shield.

### AC-003

Given the player has played Guard cards this turn, when the turn ends, then shield expiration follows the battle shield rule defined by the feature plan.

### AC-004

The shield gain animation should be visible to the player.
