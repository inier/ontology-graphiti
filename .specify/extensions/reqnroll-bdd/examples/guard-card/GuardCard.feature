@infrastructure
Feature: Guard Card Shield Stacking
  The player can play Guard cards during battle to gain shield.
  Shield gained from multiple Guard cards stacks within the same turn.

  Rule: Guard cards add shield when played

    @AC-001
    Scenario: Playing one Guard card grants shield
      Given the player has 0 shield
      And the player has 1 Guard card in hand
      When the player plays the Guard card
      Then the player should have 5 shield

    @AC-002
    Scenario: Playing two Guard cards stacks shield
      Given the player has 0 shield
      And the player has 2 Guard cards in hand
      When the player plays both Guard cards
      Then the player should have 10 shield
      And both Guard cards should be in the discard pile
