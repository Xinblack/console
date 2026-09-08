# Tekton Operator compatibility source policy

This scraper uses only first-party Tekton metadata.

## Compatibility evidence

`tektoncd/operator` publishes **Minimum K8S** for each Operator release series in its README, for both current and EOL releases. The scraper treats that value as an installation lower bound and expands it only through Plural's current `KUBE_VERSION`. This is not a claim that the contribution independently deployed every Operator/Kubernetes pairing.

## Exact application/chart identity

Tekton publishes two paired GitHub releases for Helm-enabled versions:

- runtime release: `vX.Y.Z`
- Helm release: `tekton-operator-X.Y.Z`

A version is included only when both stable releases exist. The newest exact paired patch is retained for each documented release series.

The current supported chart distribution is published at:

`oci://ghcr.io/tektoncd/operator/charts/tekton-operator`

Upstream documents that this OCI distribution starts at **v0.80.0**. Older Helm releases used a retired git-based installation path that no longer works, so the scraper deliberately excludes pre-0.80 releases from Plural instead of pointing them at a repository that cannot render them.

## Failure policy

The scraper fails before calling the Plural updater when the compatibility table disappears, duplicate series disagree, GitHub release data is malformed/unavailable, or no paired chart-backed releases match. Historical rows without a published Helm release are skipped rather than synthesized.

## Focused validation

```bash
cd utils/compatibility
python -m unittest tests.test_tekton_operator -v
```

Before submission, also run the live scraper with summarization disabled, schema validation, Helm rendering for retained chart versions, `git diff --check`, and a fresh upstream collision scan.
