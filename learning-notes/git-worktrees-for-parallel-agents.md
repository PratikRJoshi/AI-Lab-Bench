# Git Worktrees, Explained by Actually Using Them (and How They Unlock Multi-Agent Coding)

If you've ever stashed half-finished work so you could fix a bug on another branch, or cloned the same repo three times because you were juggling parallel features — this post is for you. Git has had a built-in solution for this since 2015 that most of us never learned: **worktrees**. And with LLM coding agents entering the picture, worktrees have gone from a niche productivity trick to the foundational primitive for running multiple agents in parallel on the same codebase without chaos.

I'll start with the mental model, work through a few small hands-on examples, and end with the multi-agent workflow that made me care about this in the first place.

## The mental model

A git repo has two parts: the **object database** (`.git/`, which stores every commit, tree, and blob) and a **working directory** (the files you actually edit). Normally it's one-to-one — one `.git/`, one working directory. A worktree lets you attach *additional* working directories to the **same** `.git/`, each checked out to a different branch or commit.

```
┌──────────────────────────────────────┐
│   .git object store (single source)  │
└────┬──────────────┬─────────────┬────┘
     │              │             │
  ┌──▼──┐       ┌──▼──┐       ┌──▼──┐
  │main │       │feat │       │bug  │
  │folder│      │folder│      │folder│
  │master│      │feat-x│      │fix-y│
  └─────┘       └─────┘       └─────┘
```

Three things fall out of that picture:

- **One object store, many checkouts.** Disk-efficient, zero re-cloning, branches stay in perfect sync automatically.
- **Each worktree is its own independent folder.** You can `cd` into it, build, run tests, keep `node_modules` warm — it's just a directory.
- **Each worktree has its own `HEAD`.** So two folders can have two different branches checked out simultaneously.

One rule you can't break: **a branch can only be checked out in one worktree at a time**. Git enforces this — try to check out `main` in a second worktree while it's live somewhere else and git will refuse. This invariant is what makes the whole model safe; without it, two folders could both claim to be "on main" and silently diverge.

### Why not just clone twice?

Fair question — two clones gives you two folders too. But they're not equivalent:

| | Two clones | Two worktrees |
|---|---|---|
| `.git/` | Duplicated (large repos: GB wasted) | Shared (MB) |
| Keeping in sync | `git fetch` in each; they drift | One `fetch` updates everywhere |
| Seeing a branch commit in the other | Push + fetch | Immediate |
| Same branch in both | Allowed → silent divergence | Refused by git |
| Config/hooks | Install twice | Install once |

The one-liner I use to remember: **two clones = two universes you keep in sync; two worktrees = one universe, two windows into it.**

Clones are still the right tool occasionally — genuinely independent remotes, dangerous history surgery, offline copies on another machine. For everything else (parallel features, reviewing PRs, running agents), worktrees win.

## A tour in four commands

Let's make the mental model concrete. Open any git repo you have lying around.

### 1. See what you have

```bash
git worktree list
```

Fresh repo? One line — the primary worktree you're standing in. Format is `<path> <commit> [<branch>]`. This is your "before" picture.

### 2. Create a new worktree

```bash
git worktree add ../myrepo-wt/feature-x -b feat/x
```

Three things happen:
1. A new folder appears at `../myrepo-wt/feature-x` containing a checkout of your current `HEAD`.
2. A new branch `feat/x` is created pointing at that commit.
3. That new worktree is now on `feat/x`; your current shell is still wherever it was.

Peek at the new folder:

```bash
ls ../myrepo-wt/feature-x/.git
```

Surprise: `.git` in the new worktree is a **file**, not a directory, containing a single line like `gitdir: /path/to/original/.git/worktrees/feature-x`. This tiny pointer is how one `.git/` serves many worktrees. Everything real (objects, refs, config) still lives in the original clone; the secondary worktree just keeps its per-worktree `HEAD`, index, and reflog tucked away in `.git/worktrees/feature-x/` over in the main clone.

### 3. Work there

```bash
cd ../myrepo-wt/feature-x
echo "new feature stub" > feature.txt
git add feature.txt && git commit -m "wip: feature stub"
```

Normal git. The commit you just made is immediately visible from the main clone:

```bash
cd -
git log feat/x --oneline -2     # shows your new commit, even though master hasn't moved
```

That's the "immediate branch visibility" superpower. In a two-clones setup you'd be `push`ing and `fetch`ing to see it.

### 4. Clean up

```bash
git worktree remove ../myrepo-wt/feature-x
git branch -d feat/x    # if merged; or -D if not
```

The folder vanishes. The branch can be deleted separately. **Never `rm -rf` a worktree folder** — git's bookkeeping would survive as a ghost and block you from reusing the name. If you ever do delete manually by accident, `git worktree prune` fixes it.

## A realistic example: parallel feature work

Say you've got two small, independent feature ideas and want to work on both without context-switching tax. With worktrees:

```bash
# from ~/Documents/myrepo (main clone)
git worktree add ../myrepo-wt/feat-readme    -b feat/readme-tweak
git worktree add ../myrepo-wt/feat-changelog -b feat/changelog-note
```

Now you have two folders, each on its own branch, each with its own install state. Open them in two editor windows if you like. Make your changes, commit in each:

```bash
cd ../myrepo-wt/feat-readme
# edit README.md, commit

cd ../feat-changelog
# edit CHANGELOG.md, commit
```

When both are done, merge both back to `main`:

```bash
cd ~/Documents/myrepo
git merge --no-ff feat/readme-tweak
git merge --no-ff feat/changelog-note
git worktree remove ../myrepo-wt/feat-readme
git worktree remove ../myrepo-wt/feat-changelog
git branch -d feat/readme-tweak feat/changelog-note
```

`--no-ff` is a stylistic choice I care about: it forces a **merge commit** even when a fast-forward is possible, preserving "this work came from a branch" as audit trail. Without it, merged work disappears into a linear history and you can't tell what was done in parallel.

The graph afterwards:

```
*   Merge branch 'feat/changelog-note'
|\
| * feat: add changelog note
* |   Merge branch 'feat/readme-tweak'
|\ \
| |/
|/|
| * feat: add readme tweak
|/
* <base commit>
```

Two diamonds. One for each parallel piece of work. Perfect.

## The punchline: multi-agent coding

Here's where this stops being a productivity tip and starts being a prerequisite. If you're running LLM coding agents — Cursor, Claude Code, Aider, whatever — and you've ever tried to run two of them "in parallel" in the same folder, you know what happens. They fight over `HEAD`. One agent's uncommitted changes clobber the other's. You can't tell whose diff is whose. It's a mess.

The fix is embarrassingly simple: **one agent per worktree**.

Each agent gets its own folder. Each folder is scoped to its own branch. The agents literally cannot see each other's work until a human merges them. Isolation is automatic because git enforces it.

### The minimum-viable recipe

One-time setup:

```bash
mkdir -p ~/Documents/myrepo-wt
```

Per parallel session (works for Cursor, Claude CLI, any editor-bound agent):

**Step 1 — Create worktrees, one per agent.**

```bash
cd ~/Documents/myrepo
git worktree add ../myrepo-wt/agent-a -b exp/agent-a
git worktree add ../myrepo-wt/agent-b -b exp/agent-b
```

**Step 2 — Launch one agent per worktree.**

Cursor:

```bash
cursor ../myrepo-wt/agent-a
cursor ../myrepo-wt/agent-b
# then Cmd+L in each and paste the agent's prompt
```

Claude CLI:

```bash
# in one terminal
cd ../myrepo-wt/agent-a && claude

# in another terminal
cd ../myrepo-wt/agent-b && claude
```

**Step 3 — Give each agent a narrow, non-overlapping task.** This is the single most important decision in the whole flow. A prompt template I've been using:

```
You are working in an isolated git worktree on branch <branch-name>.

Task: <one specific, bounded outcome>.

Constraints:
- Only modify files under <specific path or file list>.
- Do not touch any other directory or file.
- Commit with message: <exact commit message>.
```

Two agents editing the same file will manufacture a merge conflict, every time. So design disjoint scopes: Agent A owns `src/auth/`, Agent B owns `src/billing/`; Agent A edits `README.md`, Agent B writes `docs/ARCHITECTURE.md`. You get to decide the seams.

**Step 4 — Reintegrate once both finish.**

```bash
cd ~/Documents/myrepo
git merge --no-ff exp/agent-a
git merge --no-ff exp/agent-b
git worktree remove ../myrepo-wt/agent-a
git worktree remove ../myrepo-wt/agent-b
git branch -d exp/agent-a exp/agent-b
```

Same shape as the two-feature exercise above — because that's exactly what it is. The only difference is that the code was written by LLMs instead of your hands. Git doesn't know or care.

### Should the agent create its own worktree?

I keep getting asked this. It's tempting — one prompt that does everything! — but it's almost always the wrong call:

1. **Workspace-scoping.** In Cursor specifically, an agent's file-edit tool is rooted at the workspace folder the IDE was opened in. An agent that creates a sibling worktree and tries to edit files *there* will either be refused or write to the wrong place. Claude CLI is shell-based and more forgiving, but still confusing to supervise.
2. **Parameterization gets ugly.** Each parallel prompt needs a unique branch and path. Hand-editing per-agent inputs isn't easier than running two shell commands.
3. **Failure modes are opaque.** If `git worktree add` fails (branch exists, path exists, stale bookkeeping), the agent spends a dozen tool calls confused about why. Shell commands fail loud and fast; agents fail silent and slow.
4. **You lose visual discipline.** Opening a Cursor window per worktree forces you to see the separation. An agent that sets up its own worktree hides that from you — and it's exactly the thing you want to see.

**Principle**: git plumbing is cheap and reliable; asking an agent to do git plumbing is expensive and flaky. Use agents for code and shells for orchestration.

### A tiny helper to make the shell side one line

If the "run two git commands before each session" friction is what's pushing you toward agent-run setup, just automate it. Drop this in `~/.zshrc`:

```bash
agent-worktree() {
  local name="$1"
  local repo_root="$(git rev-parse --show-toplevel)"
  local repo_name="$(basename "$repo_root")"
  local wt_path="$repo_root/../${repo_name}-wt/$name"
  local branch="exp/$name"

  git -C "$repo_root" worktree add "$wt_path" -b "$branch" || return 1
  cursor "$wt_path"                       # or print `cd $wt_path && claude`
  echo "Worktree ready: $wt_path on branch $branch"
}
```

Usage:

```bash
cd ~/Documents/myrepo
agent-worktree agent-a
agent-worktree agent-b
```

One line per agent. Creates the worktree, creates the branch, opens Cursor, confirms. Write a sibling `agent-worktree-remove` for teardown. Now the "shell orchestration" side is as frictionless as the prompt-based approach would have been, with none of the fragility.

### When embedding setup in the prompt *is* reasonable

For automated batch jobs — "run 20 independent refactor tasks overnight and file a PR for each" — it's the right call. Just use Claude CLI (not a workspace-scoped editor), generate each prompt programmatically with unique branch/path params, and include explicit verify-then-abort guardrails:

```
Step 1: Run `git worktree add ../${REPO}-wt/${BRANCH} -b exp/${BRANCH}` from the repo root.
        If it fails, abort and report the error. Do not attempt to fix.
Step 2: cd ../${REPO}-wt/${BRANCH}
Step 3: Verify you're on branch exp/${BRANCH}. If not, abort.
Step 4: <actual task>
Step 5: git add -A && git commit -m "<message>"
Step 6: Report the commit SHA and exit.
```

The "abort-on-failure" discipline is critical. Agents that try to self-heal during bootstrap turn into debugging nightmares.

## Five gotchas worth learning once

These show up for everyone eventually. Read them now to skip the painful discovery phase:

1. **Untracked/ignored files don't come along.** When you create a worktree, only *tracked* content is populated. Your `node_modules/`, `.env`, `dist/`, Xcode `build/` — all stay in the original worktree. Every new worktree needs its own install/build step. Usually this is what you want: two worktrees with independent `node_modules` can build and test in parallel without collision.

2. **Hooks and `.git/config` are shared.** One `.git/` means one set of hooks, one config, one reflog. Install `pre-commit` in any worktree and it applies everywhere. Change `user.email` in one and all the others see it. (Git has `config --worktree` for a few whitelisted keys, but you rarely need it.)

3. **Never `rm -rf` a worktree folder.** The folder goes but the bookkeeping at `.git/worktrees/<name>/` lives on, keeping the name reserved and causing auto-suffixed `-2` weirdness next time. Always `git worktree remove <path>`. If you already `rm -rf`'d, run `git worktree prune` to release the ghost.

4. **Submodules need `--recurse-submodules`.** Without the flag, submodule directories in the new worktree are empty and builds fail mysteriously. Only applies if your repo has submodules.

5. **The primary worktree can't be removed.** Only *additional* worktrees. If you really need to relocate the primary, use `git worktree move`.

## A daily-driver cheatsheet

Everything you'll actually reach for:

```bash
# create with new branch
git worktree add <path> -b <newBranch> [startPoint]

# attach to existing branch
git worktree add <path> <branch>

# detached (for reviewing a ref without owning a branch)
git worktree add <path> --detach <commitOrRef>

# see them all
git worktree list

# remove cleanly
git worktree remove <path>

# force remove when dirty
git worktree remove --force <path>

# recover after accidental rm -rf
git worktree prune

# lock a worktree (e.g. on an external drive) to prevent auto-prune
git worktree lock <path>
git worktree unlock <path>
```

## Closing thought

Worktrees existed long before LLM agents did. Developers have been using them for years to juggle PR reviews, long-running feature work, and hotfix branches. But the multi-agent workflow turns them from a nice-to-have productivity trick into the default mental model for how work gets parallelized on a single repo.

The discipline is trivial: **one agent, one branch, one worktree.** The outcome is substantial: parallelism without chaos, clean merges, no lost work, audit trails that show exactly who (or what) did what. If you only take one thing away from this post — that's it.
