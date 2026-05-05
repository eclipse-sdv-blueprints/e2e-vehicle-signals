# Integrating with the Eclipse SDV Blueprints Website

This guide explains how to add the **E2E Demo Blueprint** documentation to the [Eclipse SDV Blueprints Website](https://github.com/eclipse-sdv-blueprints/blueprints-website) (Docusaurus).

## Documentation Files

The documentation pages are located in `docs/website/` in this repository:

| File | Page Title |
| --- | --- |
| `introduction.md` | Introduction (landing page) |
| `architecture.md` | Architecture |
| `hardware.md` | Hardware Bill of Materials |
| `setup-guide.md` | Raspberry Pi 5 Setup Guide |
| `signal-mapping.md` | VSS / CAN Signal Mapping |
| `communication-workflow.md` | Communication Workflow |
| `fleet-analysis.md` | Fleet Analysis Backend |

All pages use Docusaurus frontmatter (`sidebar_position`, `title`) and Mermaid diagrams (supported via `@docusaurus/theme-mermaid` already configured on the website).

## Changes Required in `blueprints-website`

### 1. Add remote content plugins to `docusaurus.config.js`

Add the following plugin entries to the `plugins` array in `docusaurus.config.js`:

```js
[
  "docusaurus-plugin-remote-content",
  {
    name: "e2e-demo-blueprint",
    sourceBaseUrl:
      "https://raw.githubusercontent.com/chheis/eclipse-sdv-e2e-demo-blueprint/main/docs/website",
    outDir: "docs/e2e-demo-blueprint",
    documents: [
      "introduction.md",
      "architecture.md",
      "hardware.md",
      "setup-guide.md",
      "signal-mapping.md",
      "communication-workflow.md",
      "fleet-analysis.md",
    ],
    requestConfig: { responseType: "arraybuffer" },
  },
],
```

### 2. Add sidebar entry to `sidebars.js`

Add a new category inside the `items` array of the `overallSidebar`:

```js
{
  type: 'category',
  label: 'E2E Demo Blueprint',
  link: { type: 'doc', id: 'e2e-demo-blueprint/introduction' },
  items: [
    'e2e-demo-blueprint/architecture',
    'e2e-demo-blueprint/hardware',
    'e2e-demo-blueprint/setup-guide',
    'e2e-demo-blueprint/signal-mapping',
    'e2e-demo-blueprint/communication-workflow',
    'e2e-demo-blueprint/fleet-analysis',
  ],
},
```

### 3. Add footer link (optional)

In the `footer.links[0].items` array of `docusaurus.config.js`:

```js
{
  label: 'E2E Demo Blueprint',
  to: '/docs/e2e-demo-blueprint/introduction',
},
```

### 4. Add landing page card (optional)

In `src/pages/index.tsx` (or the equivalent homepage component), add a card entry:

```jsx
<BlueprintCard
  title="E2E Demo Blueprint"
  description="An end-to-end Vehicle E/E Architecture demo combining Fleet Management with a MotorBike Blinker use case using physical Arduino ECUs, CAN bus and Eclipse Ankaios + Kuksa."
  href="https://github.com/chheis/eclipse-sdv-e2e-demo-blueprint"
/>
```

## Notes

- **Mermaid diagrams**: The documentation uses Mermaid `graph` and `sequenceDiagram` syntax. The blueprints-website already has `@docusaurus/theme-mermaid` enabled.
- **No external images**: All diagrams are embedded as Mermaid code blocks, so no separate image files need to be fetched.
- **Docusaurus admonitions**: The setup guide uses `:::tip` and `:::note` admonitions which are natively supported.
- **Source URL**: Update `sourceBaseUrl` if the repository moves to the `eclipse-sdv-blueprints` GitHub organisation.
