## Description

<!--
Explain WHAT this PR does and WHY. Link to the issue it resolves.
-->

Closes #<!-- issue number -->

---

## Type of change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] New node handler (`n8n-nodes-base.*` or `@n8n/n8n-nodes-langchain.*`)
- [ ] Breaking change (fix or feature that causes existing behaviour to change)
- [ ] Documentation update
- [ ] Refactor / code quality (no functional change)
- [ ] CI / tooling

---

## Changes made

<!--
Bullet-point summary of what changed. Be specific about files/modules touched.
-->

-
-

---

## Testing

<!--
Describe how you tested this change.
-->

- [ ] Added / updated unit tests in `backend/tests/`
- [ ] All existing tests pass (`pytest backend/tests/ -v`)
- [ ] Tested manually with a real n8n workflow JSON
- [ ] Frontend build succeeds (`npm run build` in `frontend/`)

**Test workflow used** (paste JSON or link to Gist):

---

## For new node handlers

<!-- Fill this section in if your PR adds a new handler class. -->

- **Node type string**: `n8n-nodes-base.`
- **Operations supported**: 
- **Packages added to generated `requirements.txt`**:
- [ ] Handler is registered in `backend/handlers/__init__.py`
- [ ] Handler follows the `NodeHandler` protocol (generate / supported_operations / required_packages)
- [ ] Generated code maintains the `list[dict]` data-flow contract (`{"json": {...}}`)
- [ ] Unsupported paths emit a TODO stub rather than raising an exception

---

## Screenshots / output diff

<!-- If applicable, paste the before/after generated Python output or a UI screenshot. -->

---

## Checklist

- [ ] My code follows the style guidelines (`black`, `isort`, PEP 8, TypeScript strict)
- [ ] I added my changes to `CHANGELOG.md` under `[Unreleased]`
- [ ] I updated documentation if behaviour changed
- [ ] I have no unresolved merge conflicts
