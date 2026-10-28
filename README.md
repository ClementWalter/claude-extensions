# claude-extensions

**Visibility: public.**

The download page and the privacy policy of the Claude Desktop extensions built
from the `<name>-cli` repos, served by GitHub Pages at
<https://clementwalter.github.io/claude-extensions/>.

- `index.html`: what the extensions are, how to install them, one card per
  extension with its requirements, setup steps and Download button.
- `privacy/index.html`: the privacy policy every extension's manifest links to.
- `style.css`: shared styles, light and dark.

Plain HTML and CSS, no build step, no scripts, no third-party resources. Pages
serves `main` from the repository root.

Download buttons point at
`https://github.com/ClementWalter/<repo>/releases/latest/download/<repo>.mcpb`,
which each CLI repo's release workflow publishes.

## Privacy Policy

<https://clementwalter.github.io/claude-extensions/privacy/>
