# claude-extensions

**Visibility: public.**

The download page and the privacy policy of the Claude Desktop extensions built
from the `<name>-cli` repos, served by GitHub Pages at
<https://clementwalter.github.io/claude-extensions/>.

- `index.html`: what the extensions are, how to install them, one card per
  extension with its requirements, setup steps and Download button. **Generated:
  do not edit by hand.**
- `build.py`: rebuilds `index.html` from `template.html` and, for every public
  `<name>-cli` repo whose latest release ships `<name>-cli.mcpb`, the repo's
  `mcpb.json` (`display_name`, `description`, `long_description`, and the
  `site` block: `group`, `rank`, `needs`, `risk`). A released extension
  without a valid `site` block fails the build with the fix.
- `template.html`: the static parts of the page (intro, install steps, footer).
- `privacy/index.html`: the privacy policy every extension's manifest links to.
- `style.css`: shared styles, light and dark.

The page itself is plain HTML and CSS, with no scripts and no third-party
resources. Pages serves `main` from the repository root. The `build` workflow
regenerates and commits `index.html` every 6 hours, on demand, and whenever
`build.py` or `template.html` changes:

```console
gh workflow run build.yml -R ClementWalter/claude-extensions   # after a CLI release
uv run --script build.py            # locally; --check only verifies
uv run --script tests/test_build.py
```

Download buttons point at
`https://github.com/ClementWalter/<repo>/releases/latest/download/<repo>.mcpb`,
which each CLI repo's release workflow publishes.

## Privacy Policy

<https://clementwalter.github.io/claude-extensions/privacy/>
