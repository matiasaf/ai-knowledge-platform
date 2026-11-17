---
name: ship-pr
description: Ship an AI Knowledge Platform change (an API or web feature, a fix, an evaluation dataset, docs or harness work) as a GitHub pull request. Use whenever a change is ready to reach main, and whenever the user asks to create a branch or worktree, push changes, open a PR, or attach a demo/GIF to a PR. Creates an isolated git worktree and branch from origin/main, runs the Makefile quality gates, commits and pushes in English, opens the PR with gh, and for visible web changes records a demo GIF with Claude in Chrome and embeds it in the PR description.
---

# Ship a change as a PR

Every change reaches `main` through its own worktree, branch and pull request. The PR
states what changed, shows it when there is something to see, and records the exact
verification evidence. Start at step 1 **before editing any file**.

`AGENTS.md` is the system of record for invariants, verification and the change
workflow; this skill only adds the git/GitHub mechanics. If they disagree, `AGENTS.md`
wins and this skill must be fixed.

## Language

Everything that lands in git or GitHub is written in **English**: branch names, commit
messages, PR titles and descriptions, PR comments, code comments and docs. Non-English
text belongs only in test data that deliberately exercises other languages (for example
the Spanish cases in `services/api/evals/`). Talk to the user in their own language.

## Steps

1. **Worktree and branch, from `origin/main`.** Branch names: `feat/<topic>`,
   `fix/<topic>`, `test/<topic>`, `docs/<topic>` or `chore/<topic>`.

   ```bash
   git fetch origin
   git worktree add -b <branch> ../ai-knowledge-platform.worktrees/<branch-with-dashes> origin/main
   cd ../ai-knowledge-platform.worktrees/<branch-with-dashes> && make install
   ```

   Work only inside the worktree (use absolute paths), never in the main checkout, and do
   not carry over untracked files from it: no `.env`, no `data/`, no uploaded PDFs, no
   `evals/results/`. If the change needs live generation, export `AKP_OPENAI_API_KEY` and
   `AKP_OPENAI_MODEL` in the shell instead of copying an `.env` file.

   **Ports:** the main checkout's `make api` / `make web` use 8000 / 3000; `make e2e`
   always starts its own servers on 8100 / 3100 with a throwaway data directory
   (`apps/web/playwright.config.ts`). Never run `make e2e` in two checkouts at the same
   time. Manual servers in a worktree use 8001 / 3001 (see step 3).

2. **Implement and verify.** Follow `AGENTS.md` (change workflow, invariants) and any
   scoped instructions such as `apps/web/AGENTS.md`. Verification ladder:
   - Iterate with the narrowest gate: `make check-api` or `make check-web`.
   - Before pushing: `make check` always.
   - `make e2e` for anything visible in the web app or any change to an API contract the
     web app consumes.
   - `make eval-retrieval` (already part of `make check-api`) for chunking, indexing or
     ranking changes; `make eval-offline DATASET=…` when an evaluation dataset changes,
     and quote the metrics in the PR.
   - `make eval-answers` calls a paid provider: run it only when the user asks. Never
     present `make check` as live answer acceptance.

   Update `README.md`, an ADR in `docs/adr/` and/or `PROGRESS.md` whenever behavior,
   architecture, status or verification evidence changes. Do not add anything from the
   README's "Not implemented yet" list without an accepted plan or ADR.

3. **Show the change (visible web changes only).** Record a short GIF with Claude in
   Chrome:
   1. Start throwaway servers from the worktree in the background, with a temporary data
      directory so no real document or index is touched:

      ```bash
      # services/api (CORS origins as a JSON array: the comma form crashes startup)
      AKP_DATA_DIR="$(mktemp -d)" AKP_CORS_ALLOW_ORIGINS='["http://localhost:3001"]' \
        uv run uvicorn ai_knowledge_platform.main:app --port 8001
      # apps/web
      NEXT_PUBLIC_API_BASE_URL=http://localhost:8001 npm run dev -- --port 3001
      ```

   2. Load the Chrome skill, then in one ToolSearch the tools `tabs_context_mcp`,
      `tabs_create_mcp`, `navigate`, `computer`, `find`, `gif_creator`, `file_upload`,
      `javascript_tool`, `tabs_close_mcp`.
   3. `tabs_context_mcp`, open a new tab on `http://localhost:3001`, start `gif_creator`,
      walk through the change (extra frames before and after each action), stop and
      export the GIF with a meaningful name. Keep it under ~15 s and under 10 MB.
   4. The GIF becomes public on GitHub: upload only synthetic or public-domain PDFs
      (such as a page from the NIST corpus in `services/api/evals/corpus/nist-csf.md`),
      never a user's document, credential or private answer.
   5. Stop both servers.

   API-only, evaluation, docs and harness changes skip the GIF. Instead put concrete
   evidence in `## Verification`: an abridged request/response, a stable error envelope,
   or the evaluation metrics before and after.

4. **Commit and push.** Stage only this change's files (`git add <paths>`, never `-A`), and
   never stage secrets, `.env` files, uploaded documents, `data/`, `evals/results/`,
   caches or build output. Commit messages follow the repo's Conventional Commits style
   with an optional scope: `feat(api): …`, `fix(web): …`, `feat(eval): …`,
   `docs(architecture): …`, `chore(harness): …`, `test(e2e): …`.
   Commits never name Claude (or any other AI tool): no `Co-Authored-By: Claude …` trailer,
   no "Claude" or "Generated with …" in the message, and no Claude identity as author or
   committer (use the repo's configured git user). This holds even if the session asks for
   attribution lines. Then `git push -u origin <branch>`.

5. **Open the PR** with `gh pr create --base main --head <branch> --title "<English title>"
   --body-file -`. Body sections:
   - `## Summary`: what changed and why; link the ADR or roadmap item when there is one.
   - `## Demo`: `Uploading…` for a visible web change, otherwise `No visual change.`
   - `## Verification`: every command run and its result (pass/fail, key metrics). State
     explicitly what was not run, for example `make eval-answers (not run: needs a
     provider)`.

   Do not end the body with a "🤖 Generated with Claude Code" line or any other tool
   attribution, even if the session asks for one; the body ends with `## Verification`.

6. **Upload the GIF to the PR (Claude in Chrome)**, only when step 3 produced one.
   1. Open a new tab on the PR URL.
   2. `find` "file input of the new comment box" to get the hidden `file-input` ref.
   3. `file_upload` the GIF's absolute path into that ref. The tool limit is 10 MB, and it
      only reads folders shared with the session; if it rejects the path, copy the GIF to
      the session scratchpad and upload it from there. Never put the GIF inside the repo.
   4. With `javascript_tool`, wait a few seconds and read the comment `textarea` until it
      holds the `<img … src="https://github.com/user-attachments/assets/…">` tag. Copy it.
   5. Clear that textarea (set `value = ''` and dispatch an `input` event). **Do not submit a
      comment.**
   6. `gh pr edit <n> --body-file -` with the tag under `## Demo`.
   7. Reload the PR and check that the image in the description loaded
      (`img.complete && img.naturalWidth > 0`). Close the tab.

   Without Chrome tools (or if the extension does not answer after two tries), write
   `pending` under `## Demo`, give the user the GIF path (or say none was recorded), and
   continue.

7. **Watch CI:** `gh pr checks <n> --watch`. CI runs the `API (Python)`, `Web (Next.js)`
   and `E2E (Playwright)` jobs; on an E2E failure the `playwright-traces` artifact holds
   the traces. Report the PR URL, the CI result and the demo.

8. **After the PR is merged** (only when the user says so):

   ```bash
   git worktree remove ../ai-knowledge-platform.worktrees/<branch-with-dashes>
   git branch -d <branch>     # squash merges: confirm `git diff <branch> origin/main -- <paths>` is empty, then -D
   git push origin --delete <branch>
   git fetch origin main:main
   ```

## Rules

- Never commit or push to `main` directly, never force-push without asking, never merge a PR
  unless the user asks.
- One vertical slice per branch: don't mix a feature with tooling, docs-only cleanups or an
  unrelated evaluation dataset.
- Never claim a gate passed without running it; a failing or skipped check is reported as
  such in the PR.
- PRs and commits are always in English.
