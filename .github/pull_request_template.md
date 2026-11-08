## Summary

- Describe the functional change
- Mention the impacted userscript ids (`pimpmyshoutbox`, `torr9conf`, `pimpmyshoutbox-next`)

## Checks

- [ ] `make verify` passes (or: `python3 -m unittest discover tests`, `python3 tools/build_userscripts.py --check`, `python3 tools/check_userscripts_syntax.py`, and `npm test && npm run check` in `next/pimpmyshoutbox`)
- [ ] The userscript `@version` was bumped if the published behavior changed
- [ ] Documentation was updated if the behavior, tooling or structure changed
- [ ] The branch naming matches the git flow (`feature/*`, `release/*`, `hotfix/*`)
