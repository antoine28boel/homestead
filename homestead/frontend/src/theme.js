// Behind ingress the page is framed by Home Assistant, on the same origin:
// borrow its theme colours so the page looks at home there.
const VARIABLES = {
  "--primary-color": "--hs-primary",
  "--primary-background-color": "--hs-background",
  "--card-background-color": "--hs-card",
  "--primary-text-color": "--hs-text",
  "--secondary-text-color": "--hs-text-muted",
  "--divider-color": "--hs-divider",
  "--error-color": "--hs-error",
  "--warning-color": "--hs-warning",
};

export function adoptHomeAssistantTheme() {
  let parentRoot;
  try {
    if (window.parent === window) return;
    parentRoot = window.parent.document.documentElement;
  } catch {
    return; // Another origin: keep our own colours.
  }
  const apply = () => {
    const style = window.parent.getComputedStyle(parentRoot);
    for (const [from, to] of Object.entries(VARIABLES)) {
      const value = style.getPropertyValue(from).trim();
      if (value) document.documentElement.style.setProperty(to, value);
    }
  };
  apply();
  new MutationObserver(apply).observe(parentRoot, {
    attributes: true,
    attributeFilter: ["style", "class"],
  });
}
