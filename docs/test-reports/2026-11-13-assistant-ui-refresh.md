# Invoice AI Assistant UI refresh

Approved direction: wider, calmer chat layout; multiline composer; clearer request and confirmation states; better mobile sizing and keyboard accessibility.

Implemented using the existing React, Radix, Tailwind and translation infrastructure:

- Accessible modal with labeled controls, focus containment/restoration and responsive fullscreen layout.
- Wider desktop conversation, simpler message cards, sender/time labels, wrapped quick actions, and a latest-message control when reading older content.
- Multiline composer: Enter sends, Shift+Enter inserts a line break, IME composition does not send prematurely.
- Pending state tracked per reply, so overlapping requests keep the header busy until all initial replies complete. Background jobs and confirmations show progress in their own cards.
- Clearer editable confirmation cards with localized action/field labels and visible errors.
- New labels and welcome copy in English, French, German and Spanish.

Validation:

- 23 focused assistant/onboarding tests pass across six files, including existing safety regressions and new dialog, keyboard, focus restoration, and concurrent-status assertions.
- New test and confirmation-card ESLint checks pass; the assistant retains existing broad typing/lint debt.
- Isolated production build of the actual assistant and styles with fixture APIs passes. This does not establish a green whole-application build.
- Independent scoped review found no blocking regression.
- Whole-application TypeScript validation still reports repository-wide errors; local validation limitations from the preceding safety PR remain applicable.
- Actual desktop/mobile screenshots and visual checks could not be completed because the browser access host is unavailable. No live provider/customer data was used.

A temporary fixture-only preview was started at http://127.0.0.1:5199. Its files are under /private/tmp/assistant-ui-preview, outside the repository. The preview is for visual inspection, not deployment.
