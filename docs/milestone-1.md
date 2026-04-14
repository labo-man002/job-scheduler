# Milestone 1 - MVP Foundation and Hero Surface Runway

## Milestone Goal
Create the technical and product foundation required for parallel work across backend, frontend, and platform, while proving the first operator-facing path of the MVP.

## Why this milestone exists
The immediate need is not feature breadth.
It is to create a stable spine for the project so:
- backend semantics are defined clearly
- frontend work can start against stable contracts and fixtures
- platform/devops work has a concrete runtime target
- the first hero demo story becomes buildable rather than speculative

## Milestone Success Criteria
Milestone 1 is successful if the project has:
- a clear MVP architecture and product boundary
- a canonical snapshot contract
- fixture/replay data for parallel development
- a first normalized ingestion path from Slurm
- first overview/topology API contracts
- the first frontend hero shell
- GitHub issues cleanly split for the three contributors

## Scope

### Included
- architecture documentation
- snapshot contract definition
- mock/replay fixtures
- reference Slurm environment setup work
- normalized backend domain model v1
- cluster overview API shape
- topology surface API shape
- hero UI shell and layout
- initial allocation/placement semantics
- initial queue explanation / fragmentation / scarcity semantics

### Explicitly not included
- advanced production deployment
- control-plane mutation workflows
- multi-cluster support
- 3D visualization
- deep RBAC/billing/admin workflows

## Planned Workstreams

### Workstream A - Product and architecture
- lock the MVP product cut
- lock the reference architecture
- document team ownership boundaries
- define the first hero demo story

### Workstream B - Contracts and fixtures
- define `ClusterSnapshot v0`
- create fixture scenarios
- support replay-driven frontend and demo work

### Workstream C - Backend semantic spine
- ingest Slurm state
- normalize canonical entities
- expose cluster overview and topology surfaces
- start allocation, placement, queue explanation, and fragmentation semantics

### Workstream D - Frontend hero shell
- create the operator screen shell
- connect queue/topology/drilldown/insights layout
- prepare the UI to consume fixture-driven and live data

### Workstream E - Platform and devex
- local/dev stack
- consistent environment setup
- CI/CD baseline
- demo/replay support

## Issue Set for Milestone 1
1. Stand up Slurm Docker reference environment
2. Define normalized backend domain model v1
3. Implement `ClusterSnapshot v0` contract + fixtures
4. Implement cluster overview API
5. Implement topology surface normalized API
6. Build hero UI shell and layout
7. Implement allocation drilldown and placement summary v1
8. Implement queue explanation + fragmentation/scarcity v1

## Suggested Ownership

### Khalil
- domain model
- snapshot contract
- Slurm ingestion/normalization
- placement/fragmentation semantics
- pending explanation semantics

### Web developer
- hero shell
- topology surface rendering
- queue panel and drilldowns
- filters, state composition, cross-highlighting

### Cloud/DevOps engineer
- reference environment automation
- local/dev stack
- containers / compose
- CI/CD baseline
- replay/demo environment support

## Recommended milestone order
1. Architecture + snapshot contract
2. Fixtures + replay mode
3. Reference environment + backend normalization
4. Overview/topology API surfaces
5. Hero UI shell
6. Derived explanation/fragmentation layer

## Expected Outcome at Milestone End
By the end of Milestone 1, the repo should support a credible internal demo where:
- the operator can load a cluster view
- queue state and topology are visible together
- one pending-job explanation path exists
- fragmentation/placeability is visible at least in v1 form
- backend/frontend/platform contributors are no longer blocked on missing structure
