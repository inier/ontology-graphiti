# Implementation Handoff Rules

The generate command must produce enough implementation guidance for `/speckit.implement`.

## The handoff must include

- target test project
- feature files
- scenario-to-step-class suggestions
- test support objects
- architecture rules
- implementation patterns (Given/When/Then examples showing Application boundary calls replacing `PendingStepException()`)
- expected test state transitions (skipped → passed)
- suggested task insertions
- verification command

## The handoff must not

- implement production code
- generate full step definitions
- install packages automatically
- modify Presentation-layer components
