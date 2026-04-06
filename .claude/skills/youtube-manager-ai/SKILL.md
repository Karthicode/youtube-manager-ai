```markdown
# youtube-manager-ai Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the core development patterns and conventions used in the `youtube-manager-ai` TypeScript codebase. You'll learn how to structure files, write and organize code, follow commit conventions, and understand the project's approach to testing. This guide will help you contribute code that fits seamlessly with the existing repository style.

## Coding Conventions

### File Naming
- Use **camelCase** for all file names.
  - Example: `videoManager.ts`, `youtubeApiClient.ts`

### Import Style
- Use **relative imports** for modules within the project.
  - Example:
    ```typescript
    import { fetchVideos } from './videoManager';
    ```

### Export Style
- Use **named exports** for all exported functions, classes, or variables.
  - Example:
    ```typescript
    // In videoManager.ts
    export function fetchVideos() { ... }
    ```

### Commit Messages
- Follow the **Conventional Commits** specification.
- Use the `chore` prefix for maintenance and non-feature commits.
  - Example: `chore: update dependencies to latest versions`

## Workflows

### Code Contribution
**Trigger:** When adding new features or fixing bugs  
**Command:** `/contribute`

1. Create a new branch from `main`.
2. Write your code following the coding conventions above.
3. Add or update tests as needed.
4. Commit your changes using a conventional commit message (e.g., `chore: fix video fetch error`).
5. Push your branch and open a pull request.

### Dependency Management
**Trigger:** When updating or adding dependencies  
**Command:** `/update-dependencies`

1. Run the package manager to add or update dependencies.
   - Example: `npm install <package-name>` or `npm update`
2. Commit changes with a message like `chore: update <package-name> to vX.Y.Z`.
3. Push your changes and open a pull request if required.

### Testing
**Trigger:** Before merging or releasing code  
**Command:** `/test`

1. Identify test files matching the `*.test.*` pattern.
2. Run the test suite using the project's test runner (framework unknown; try `npm test` or similar).
3. Ensure all tests pass before merging.

## Testing Patterns

- Test files follow the `*.test.*` naming convention (e.g., `videoManager.test.ts`).
- The specific testing framework is not detected, but standard TypeScript testing practices apply.
- Place tests alongside the code or in a dedicated `tests` directory.
- Example test file name: `youtubeApiClient.test.ts`

## Commands
| Command              | Purpose                                      |
|----------------------|----------------------------------------------|
| /contribute          | Start the code contribution workflow         |
| /update-dependencies | Update or add project dependencies           |
| /test                | Run the test suite for the codebase          |
```