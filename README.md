# tr4ker-scripting

Repository for the Tr4ker Tampermonkey userscripts, maintained at
[Cylae/tr4ker-scripting](https://github.com/Cylae/tr4ker-scripting) (fork of
[SaltedButch/tr4ker-scripting](https://github.com/SaltedButch/tr4ker-scripting)).
Scripts installed from the upstream URLs keep updating from upstream; to follow
this repository, reinstall them from the `Cylae` raw URLs listed below.

It provides:

- a clean `src -> dist` pipeline for the legacy scripts, with automatic `@updateURL` / `@downloadURL`,
- **PimpMyShoutbox Next** (`next/pimpmyshoutbox`), the modular successor bundled with esbuild,
- a dedicated `userscripts` publishing branch served to Tampermonkey,
- a git flow based on `main`, `develop`, `feature/*`, `release/*` and `hotfix/*`,
- Python tooling (build, metadata validation, version bump, audit) and a Node.js syntax gate that catches broken userscripts before publish.

## Structure

```text
.
├── .github/
│   ├── workflows/        CI, publication, Next release archive
│   └── rulesets/         importable GitHub rulesets (see its README)
├── meta/                 forum posts and helper snippets (not shipped)
├── next/pimpmyshoutbox/  PimpMyShoutbox Next (esbuild, tests, own README)
├── src/userscripts/      legacy userscripts (source of truth)
├── tests/                unit tests of the Python tooling
├── tools/                build, check, bump and audit scripts
├── CONTRIBUTING.md
├── Makefile
└── userscripts.json
```

- `src/userscripts/*.user.js`: legacy sources edited day to day.
- `dist/`: generated publish-ready files (`*.user.js`, `*.meta.js`, `manifest.json`), git-ignored.
- `tools/build_userscripts.py`: injects repository URLs, validates metadata (required keys, numeric `@version`, valid URLs, no duplicated singleton keys) and builds Tampermonkey artifacts.
- `tools/check_userscripts_syntax.py`: runs `node --check` on every source userscript.
- `tools/tr4ker.py`: unified CLI (doctor, list, verify, build, bump, release, clean).
- `tools/bump_version.py`: updates the `@version` of a legacy script or of `pimpmyshoutbox-next` (explicit version or `major`/`minor`/`patch`).
- `tools/audit_userscripts.py`: informational report (file size, large functions, listeners, `innerHTML`).
- `tests/`: `python3 -m unittest discover tests`.
- `RELEASE_NOTES.md`: release notes for `pimpmyshoutbox`.
- `RELEASE_NOTES_TORR9CONF.md`: release notes for `torr9conf`.
- `TR4KER_API_REFERENCE.md`, `TR4KER_MIGRATION.md`: Tr4ker API reference and migration follow-up.
- `Makefile`: optional shortcuts (`make help` lists them) for environments where `make` is available.

## Quick start

Requirements: Python 3.10+ (CI uses 3.12) and Node.js 22 (see `next/pimpmyshoutbox/.nvmrc`).

One entry point works on Windows, macOS and Linux, without `make`:

```bash
python tools/tr4ker.py doctor     # check Python, Node, npm, git and the config
python tools/tr4ker.py list --urls  # scripts, versions, Tampermonkey URLs
python tools/tr4ker.py verify     # every gate that CI runs, with a summary
python tools/tr4ker.py build --next # build dist/ (and the Next bundle)
```

| Command | Purpose |
| --- | --- |
| `doctor` | Verify the toolchain and the repository configuration |
| `list [--urls] [--json]` | Inventory of legacy scripts and PimpMyShoutbox Next |
| `check` | Metadata validation and `node --check` on every legacy script |
| `build [-s ID] [--next]` | Build `dist/`; `--next` also bundles Next |
| `verify [--skip-next] [-k]` | Tooling tests, metadata, syntax, Next tests and build |
| `audit` | Informational size/safety report of the legacy scripts |
| `bump ID <x.y.z\|major\|minor\|patch> [-n]` | Update `@version` (`-n` = dry run) |
| `release ID <x.y.z\|major\|minor\|patch>` | Bump, then run every gate |
| `clean` | Remove `dist/` folders and Python caches |

Version increments keep zero-padded segments (`3.01.21` + `patch` → `3.01.22`).
Script ids: `pimpmyshoutbox`, `torr9conf`, `pimpmyshoutbox-next`.

`make help` lists the equivalent shortcuts, and the original scripts in `tools/`
(`build_userscripts.py`, `bump_version.py`, ...) keep working unchanged:

```bash
python3 -m unittest discover tests
python3 tools/build_userscripts.py --check
python3 tools/check_userscripts_syntax.py
cd next/pimpmyshoutbox && npm ci && npm test && npm run check
```

## Tampermonkey auto-update

### Migration de PimpMyShoutbox legacy vers Next

La dernière mise à jour legacy, **3.01.21**, ajoute **(DEPRECATED)** au nom du
script et affiche une invitation à migrer vers Next. **Me rappeler plus tard**
masque l'invitation jusqu'au prochain jour du calendrier local.

Avant de migrer, exporter la configuration de l'ancien script via **Exporter
la config**, installer Next, puis désactiver **Tr4ker - PimpMyShoutbox
(DEPRECATED)** dans le tableau de bord de Tampermonkey, Greasemonkey ou
Violentmonkey. Recharger Tr4ker et utiliser **Importer une config** dans les
réglages de Next pour sélectionner le fichier JSON sauvegardé.

Le bouton **Installer maintenant** utilise l'URL raw stable du script Next :
`https://raw.githubusercontent.com/Cylae/tr4ker-scripting/userscripts/pimpmyshoutbox-next.user.js`.
Le workflow **Publish Userscripts** construit et publie les artefacts legacy et
Next ensemble depuis `main`, dans un même commit de la branche `userscripts`.
Aucune release GitHub n'est nécessaire pour diffuser cette migration.

### Publication des scripts

Published artifacts are served from the `userscripts` branch. For each source file in `src/userscripts`, the build generates:

- `dist/<script-id>.user.js`: installable script,
- `dist/<script-id>.meta.js`: lightweight metadata used by Tampermonkey update checks.

Current published scripts:

```text
https://raw.githubusercontent.com/Cylae/tr4ker-scripting/userscripts/pimpmyshoutbox.user.js
https://raw.githubusercontent.com/Cylae/tr4ker-scripting/userscripts/pimpmyshoutbox-next.user.js
https://raw.githubusercontent.com/Cylae/tr4ker-scripting/userscripts/torr9conf.user.js
```

Current metadata URLs:

```text
https://raw.githubusercontent.com/Cylae/tr4ker-scripting/userscripts/pimpmyshoutbox.meta.js
https://raw.githubusercontent.com/Cylae/tr4ker-scripting/userscripts/pimpmyshoutbox-next.meta.js
https://raw.githubusercontent.com/Cylae/tr4ker-scripting/userscripts/torr9conf.meta.js
```

Les URL legacy sont injectées automatiquement par le build Python. Les URL Next
sont déclarées dans `next/pimpmyshoutbox/metadata.user.js` et reprises dans le
bundle généré. Leur chemin reste stable lorsque la version change : seul
`@version` doit être augmenté manuellement avant publication.

Current script ids (`tools/bump_version.py`):

- `pimpmyshoutbox` (legacy, deprecated)
- `torr9conf` (legacy)
- `pimpmyshoutbox-next` (built from `next/pimpmyshoutbox`)

## Git flow

The intended branch policy is:

- `main`: production-ready source only.
- `develop`: staging branch for the next release.
- `feature/*`: new feature branches created from `develop`.
- `release/*`: release hardening branches created from `develop`.
- `hotfix/*`: urgent fixes created from `main`.
- `userscripts`: generated artifacts branch used by Tampermonkey.

Detailed release steps are documented in [CONTRIBUTING.md](CONTRIBUTING.md).

## GitHub Actions

- `CI`: runs the Python tooling tests, validates metadata, parses every userscript with `node --check`, prints the audit report, then tests and builds PimpMyShoutbox Next, on pushes and pull requests.
- `Publish Userscripts`: runs the same gates, rebuilds the legacy and Next scripts on every push to `main`, then publishes their generated artifacts to `userscripts` with a regular (never forced) commit.
- `Archive PimpMyShoutbox Next release`: optionally archives a tagged Next version in a GitHub Release; automatic updates use the stable raw URLs.

## Repository setup checklist

1. Create the `develop` branch from `main` if it does not exist yet: `git switch -c develop && git push -u origin develop`.
2. Import the rulesets from `.github/rulesets/` (see its README) to protect `main`, `userscripts` and the Next tags.
3. Install scripts in Tampermonkey from the raw `userscripts` URLs, never from `src/`.
