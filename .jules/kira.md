# Kira's Journal — Reusable Downstream Parity Insights

## 2026-09-18 - GitHub Project Security Alerts Eventual Consistency Retry **Learning:** Eventual consistency in GitHub Project item creation can throw 'Content already exists in this project' when an item was added concurrently or index propagation is delayed. Exponential backoff retries in `findProjectItemIdEventually` prevent sync job crashes. **Action:** Retain `findProjectItemIdEventually` in `sync-security-alerts.js` for all Project v2 item additions across FullStack Template downstream applications.
